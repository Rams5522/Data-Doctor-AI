import os
import sys
import tempfile
import pytest
from fastapi.testclient import TestClient

# Add the backend directory to the path so we can import app modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.main import app
from app.db.session import SessionLocal, engine, get_db
from app.db.models import Base

# Create the tables in the test database
Base.metadata.create_all(bind=engine)

# Override the get_db dependency
def override_get_db():
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

def test_profiling_endpoint():
    # First upload a dataset
    csv_content = """employee_id,first_name,last_name,department,salary,hire_date
1001,John,Doo,Engineering,75000,2020-01-15
1002,Jane,Smith,Marketing,68000,2019-03-22
1003,Bob,Johnson,Engineering,82000,2021-07-10
1004,Alice,Brown,Sales,65000,2020-11-05
1005,Charlie,Wilson,Engineering,79000,2021-02-18"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(csv_content)
        temp_file_path = f.name

    try:
        with open(temp_file_path, 'rb') as f:
            upload_response = client.post(
                "/api/datasets/upload",
                files={"file": ("test.csv", f, "text/csv")},
                data={"name": "Test Dataset", "description": "A test dataset"}
            )

        assert upload_response.status_code == 200
        upload_data = upload_response.json()
        dataset_id = upload_data["dataset_id"]

        # Now trigger profiling
        profile_response = client.post(f"/api/profiling/{dataset_id}/analyze")
        assert profile_response.status_code == 200
        profile_data = profile_response.json()
        assert "message" in profile_data
        assert profile_data["message"] == "Dataset analysis completed"
        assert "profile_id" in profile_data
        assert "dataset_id" in profile_data
        assert profile_data["dataset_id"] == dataset_id

        # Get the profiling results
        get_profile_response = client.get(f"/api/profiling/{dataset_id}/profile")
        assert get_profile_response.status_code == 200
        get_profile_data = get_profile_response.json()
        assert "dataset_id" in get_profile_data
        assert "version_id" in get_profile_data
        assert "profile_data" in get_profile_data
        assert "profile_summary" in get_profile_data

        # Check that we have column profiles
        profile_info = get_profile_data["profile_data"]
        assert "dataset_info" in profile_info
        assert "column_profiles" in profile_info
        assert profile_info["dataset_info"]["num_rows"] == 5
        assert profile_info["dataset_info"]["num_columns"] == 6

        # Check column profiles exist
        column_profiles = profile_info["column_profiles"]
        assert "employee_id" in column_profiles
        assert "first_name" in column_profiles
        assert "salary" in column_profiles

        # Check numeric column stats for salary
        salary_profile = column_profiles["salary"]
        assert "mean" in salary_profile
        assert "median" in salary_profile
        assert "min" in salary_profile
        assert "max" in salary_profile
        assert salary_profile["missing_count"] == 0
        assert salary_profile["missing_percent"] == 0.0

    finally:
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)


def test_visualization_endpoint():
    csv_content = """id,age,score,department
1,25,85.5,Engineering
2,30,90.0,Marketing
3,35,78.2,Engineering
4,40,92.4,Sales
5,28,88.0,Marketing"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(csv_content)
        temp_file_path = f.name

    try:
        with open(temp_file_path, 'rb') as f:
            upload_response = client.post(
                "/api/datasets/upload",
                files={"file": ("test_viz.csv", f, "text/csv")},
                data={"name": "Viz Test Dataset", "description": "Testing visualization endpoint"}
            )

        assert upload_response.status_code == 200
        upload_data = upload_response.json()
        dataset_id = upload_data["dataset_id"]
        version_id = upload_data["version_id"]

        # Call the visualization endpoint directly under /api/profiling/
        viz_response = client.get(f"/api/profiling/{dataset_id}/versions/{version_id}/visualization-data")
        assert viz_response.status_code == 200
        viz_data = viz_response.json()

        assert "overview" in viz_data
        assert viz_data["overview"]["total_records"] == 5
        assert "clean_records" in viz_data["overview"]
        assert "quality_percentage" in viz_data["overview"]

        assert "column_distributions" in viz_data
        col_names = [c["name"] for c in viz_data["column_distributions"]]
        assert "age" in col_names
        assert "score" in col_names
        assert "department" in col_names

        # Age distribution
        age_col = next(c for c in viz_data["column_distributions"] if c["name"] == "age")
        assert len(age_col["distribution"]) > 0
        assert "label" in age_col["distribution"][0]
        assert "count" in age_col["distribution"][0]
        assert "percentage" in age_col["distribution"][0]

        # Correlations between numeric columns
        assert "correlations" in viz_data
        corr_pairs = viz_data["correlations"]
        assert len(corr_pairs) > 0
        for p in corr_pairs:
            assert "column" in p
            assert "correlated_with" in p
            assert "value" in p
            assert -1.0 <= p["value"] <= 1.0

        # Check alias under /api/datasets/
        alias_response = client.get(f"/api/datasets/{dataset_id}/versions/{version_id}/visualization-data")
        assert alias_response.status_code == 200
        alias_data = alias_response.json()
        assert alias_data["overview"]["total_records"] == 5

    finally:
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)


if __name__ == "__main__":
    test_profiling_endpoint()
    test_visualization_endpoint()
    print("All profiling and visualization tests passed!")
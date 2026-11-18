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

def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_upload_dataset():
    # Create a temporary CSV file
    csv_content = """employee_id,first_name,last_name,department,salary,hire_date
1001,John,Doo,Engineering,75000,2020-01-15
1002,Jane,Smith,Marketing,68000,2019-03-22
1003,Bob,Johnson,Engineering,82000,2021-07-10"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(csv_content)
        temp_file_path = f.name

    try:
        with open(temp_file_path, 'rb') as f:
            response = client.post(
                "/api/datasets/upload",
                files={"file": ("test.csv", f, "text/csv")},
                data={"name": "Test Dataset", "description": "A test dataset"}
            )

        assert response.status_code == 200
        data = response.json()
        assert "dataset_id" in data
        assert "version_id" in data
        assert data["name"] == "Test Dataset"
        assert data["description"] == "A test dataset"
        assert data["version_number"] == 1

        # Clean up uploaded file
        if os.path.exists(data.get("storage_path", "")):
            os.remove(data["storage_path"])

    finally:
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)

def test_list_datasets():
    response = client.get("/api/datasets/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_get_dataset():
    # First upload a dataset
    csv_content = """employee_id,first_name,last_name
1001,John,Doo
1002,Jane,Smith"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(csv_content)
        temp_file_path = f.name

    try:
        with open(temp_file_path, 'rb') as f:
            upload_response = client.post(
                "/api/datasets/upload",
                files={"file": ("test2.csv", f, "text/csv")},
                data={"name": "Test Dataset 2", "description": "Another test"}
            )

        assert upload_response.status_code == 200
        upload_data = upload_response.json()
        dataset_id = upload_data["dataset_id"]

        # Now get the dataset
        get_response = client.get(f"/api/datasets/{dataset_id}")
        assert get_response.status_code == 200
        get_data = get_response.json()
        assert get_data["id"] == dataset_id
        assert get_data["name"] == "Test Dataset 2"

        # Clean up
        if os.path.exists(get_data.get("latest_version", {}).get("storage_path", "")):
            os.remove(get_data["latest_version"]["storage_path"])

    finally:
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)

if __name__ == "__main__":
    test_health_check()
    test_upload_dataset()
    test_list_datasets()
    test_get_dataset()
    print("All tests passed!")
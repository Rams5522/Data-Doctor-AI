from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
import pandas as pd
import numpy as np
from app.services.profiling import ProfilingService
from app.db.session import get_db
from app.db.models import Dataset, DatasetVersion

router = APIRouter()
profiling_service = ProfilingService()

@router.post("/{dataset_id}/analyze")
async def analyze_dataset(
    dataset_id: int,
    version_id: int = Query(None),
    db: Session = Depends(get_db)
):
    """Trigger profiling and analysis of a dataset"""
    # Get dataset
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # Get version
    if version_id is None:
        version = db.query(DatasetVersion)\
            .filter(DatasetVersion.dataset_id == dataset_id)\
            .order_by(DatasetVersion.version_number.desc())\
            .first()
    else:
        version = db.query(DatasetVersion)\
            .filter(DatasetVersion.id == version_id)\
            .first()

    if not version:
        raise HTTPException(status_code=404, detail="Dataset version not found")

    # Check if file exists
    import os
    if not os.path.exists(version.storage_path):
        raise HTTPException(status_code=404, detail="Dataset file not found")

    # Run profiling
    profile_result = profiling_service.profile_dataset(version.storage_path, getattr(version, 'format_metadata', None))

    # Format-aware profiling ensures consistent parsing for repaired datasets.

    # Keep one current profile per dataset version so repeated analysis does not create stale rows.
    from app.db.models import DatasetProfile
    db.query(DatasetProfile).filter(DatasetProfile.dataset_id == dataset_id, DatasetProfile.version_id == version.id).delete(synchronize_session=False)
    db.commit()
    dataset_profile = DatasetProfile(
        dataset_id=dataset_id,
        version_id=version.id,
        profile_data=profile_result
    )
    db.add(dataset_profile)
    db.commit()
    db.refresh(dataset_profile)

    # Create audit event
    from app.db.models import AuditEvent
    audit_event = AuditEvent(
        dataset_id=dataset_id,
        event_type="analyze",
        event_data={
            "version_id": version.id,
            "profile_summary": profiling_service.get_profile_summary(profile_result)
        }
    )
    db.add(audit_event)
    db.commit()

    return {
        "message": "Dataset analysis completed",
        "dataset_id": dataset_id,
        "version_id": version.id,
        "profile_id": dataset_profile.id,
        "profile_summary": profiling_service.get_profile_summary(profile_result)
    }

@router.get("/{dataset_id}/profile")
async def get_dataset_profile(
    dataset_id: int,
    version_id: int = Query(None),
    db: Session = Depends(get_db)
):
    """Get profiling results for a dataset"""
    # Get dataset
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # Get version
    if version_id is None:
        version = db.query(DatasetVersion)\
            .filter(DatasetVersion.dataset_id == dataset_id)\
            .order_by(DatasetVersion.version_number.desc())\
            .first()
    else:
        version = db.query(DatasetVersion)\
            .filter(DatasetVersion.id == version_id)\
            .first()

    if not version:
        raise HTTPException(status_code=404, detail="Dataset version not found")

    # Get profile
    from app.db.models import DatasetProfile
    profile = db.query(DatasetProfile)\
        .filter(DatasetProfile.dataset_id == dataset_id)\
        .filter(DatasetProfile.version_id == version.id)\
        .first()

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found for this version")

    return {
        "dataset_id": dataset_id,
        "version_id": version.id,
        "profile_data": profile.profile_data,
        "profile_summary": profiling_service.get_profile_summary(profile.profile_data),
        "created_at": profile.created_at.isoformat() if profile.created_at else None
    }

@router.get("/{dataset_id}/columns/{column_name}")
async def get_column_profile(
    dataset_id: int,
    column_name: str,
    version_id: int = Query(None),
    db: Session = Depends(get_db)
):
    """Get profiling results for a specific column"""
    # Get dataset
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # Get version
    if version_id is None:
        version = db.query(DatasetVersion)\
            .filter(DatasetVersion.dataset_id == dataset_id)\
            .order_by(DatasetVersion.version_number.desc())\
            .first()
    else:
        version = db.query(DatasetVersion)\
            .filter(DatasetVersion.id == version_id)\
            .first()

    if not version:
        raise HTTPException(status_code=404, detail="Dataset version not found")

    # Get profile
    from app.db.models import DatasetProfile
    profile = db.query(DatasetProfile)\
        .filter(DatasetProfile.dataset_id == dataset_id)\
        .filter(DatasetProfile.version_id == version.id)\
        .first()

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found for this version")

    column_profile = profile.profile_data.get("column_profiles", {}).get(column_name)
    if not column_profile:
        raise HTTPException(status_code=404, detail=f"Column '{column_name}' not found in profile")

    return {
        "dataset_id": dataset_id,
        "version_id": version.id,
        "column_name": column_name,
        "column_profile": column_profile
    }


@router.get("/{dataset_id}/versions/{version_id}/visualization-data")
async def get_visualization_data(
    dataset_id: int,
    version_id: int,
    db: Session = Depends(get_db)
):
    """Get visualization data for a dataset version - combines profiling, quality issues, and correlations"""
    # Get dataset
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # Get version
    version = db.query(DatasetVersion)\
        .filter(DatasetVersion.id == version_id)\
        .filter(DatasetVersion.dataset_id == dataset_id)\
        .first()
    if not version:
        raise HTTPException(status_code=404, detail="Dataset version not found")

    # Initialize response structure
    viz_data = {}

    import os
    if not os.path.exists(version.storage_path):
        raise HTTPException(status_code=404, detail="Dataset file not found")

    # Read dataset safely across CSV, XLSX, XLS, and JSON formats
    try:
        from app.services.tabular_format import read_tabular
        frame = read_tabular(version.storage_path, getattr(version, 'format_metadata', None))
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Unable to read dataset for visualization: {exc}")

    total_records = len(frame) if frame is not None else 0

    viz_data["overview"] = {
        "total_records": int(total_records),
        "clean_records": int(total_records),
        "dirty_records": 0,
        "quality_percentage": 100.0
    }

    # Sample for fast computation if the dataset is large
    sample_frame = frame.sample(n=10000, random_state=42) if total_records > 10000 else frame

    # Add column distributions for visualization
    viz_data["column_distributions"] = []

    for col_name in sample_frame.columns:
        series = sample_frame[col_name]
        distribution = []
        numeric = pd.api.types.is_numeric_dtype(series)
        if numeric and series.notna().any():
            values = pd.to_numeric(series, errors="coerce").dropna()
            if not values.empty:
                n_bins = 10
                counts, edges = np.histogram(values, bins=n_bins)
                total = max(len(values), 1)
                distribution = [
                    {
                        "label": f"{edges[i]:.1f} - {edges[i+1]:.1f}",
                        "value": round(float((edges[i] + edges[i + 1]) / 2), 4),
                        "count": int(count),
                        "percentage": round(float(count / total * 100), 2)
                    }
                    for i, count in enumerate(counts)
                ]
        else:
            counts = series.value_counts(dropna=False).head(10)
            total = max(len(series), 1)
            distribution = [
                {
                    "label": "Null/Missing" if pd.isna(value) else str(value)[:22],
                    "value": None if pd.isna(value) else str(value),
                    "count": int(count),
                    "percentage": round(float(count / total * 100), 2)
                }
                for value, count in counts.items()
            ]

        viz_data["column_distributions"].append({
            "name": str(col_name),
            "data_type": str(series.dtype),
            "distribution": distribution
        })

    # Get quality issues data
    from app.db.models import QualityFinding
    findings = db.query(QualityFinding)\
        .filter(QualityFinding.dataset_id == dataset_id)\
        .filter(QualityFinding.version_id == version_id)\
        .all()

    if findings:
        dirty_records = sum(f.affected_count for f in findings)
        clean_records = max(0, total_records - dirty_records)

        viz_data["overview"]["clean_records"] = int(clean_records)
        viz_data["overview"]["dirty_records"] = int(dirty_records)
        viz_data["overview"]["quality_percentage"] = (clean_records / total_records * 100) if total_records > 0 else 100.0

        issue_types = {}
        for f in findings:
            issue_type = (f.issue_type or 'unknown').replace('_', ' ').title()
            if issue_type not in issue_types:
                issue_types[issue_type] = {"count": 0, "total": 0}
            issue_types[issue_type]["count"] += 1
            issue_types[issue_type]["total"] += (f.affected_count or 0)

        viz_data["quality_issues"] = {
            "issue_types": [
                {
                    "type": issue_type,
                    "count": data["count"],
                    "total_issues": len(findings)
                }
                for issue_type, data in issue_types.items()
            ],
            "total_issues": len(findings),
            "severity_distribution": [
                {
                    "level": "high",
                    "count": len([f for f in findings if (f.severity or '').lower() == "high"]),
                    "percentage": (len([f for f in findings if (f.severity or '').lower() == "high"]) / len(findings) * 100) if findings else 0
                },
                {
                    "level": "medium",
                    "count": len([f for f in findings if (f.severity or '').lower() == "medium"]),
                    "percentage": (len([f for f in findings if (f.severity or '').lower() == "medium"]) / len(findings) * 100) if findings else 0
                },
                {
                    "level": "low",
                    "count": len([f for f in findings if (f.severity or '').lower() == "low"]),
                    "percentage": (len([f for f in findings if (f.severity or '').lower() == "low"]) / len(findings) * 100) if findings else 0
                }
            ]
        }
    else:
        viz_data["quality_issues"] = {
            "issue_types": [],
            "total_issues": 0,
            "severity_distribution": []
        }

    # Calculate correlations from the actual source data (sampled if > 10,000 rows for speed)
    viz_data["correlations"] = []
    numeric_frame = sample_frame.select_dtypes(include=[np.number])
    if not numeric_frame.empty and len(numeric_frame.columns) > 1:
        cols_to_corr = numeric_frame.columns[:30]
        correlation = numeric_frame[cols_to_corr].corr(numeric_only=True)
        for column in correlation.columns:
            for correlated_with in correlation.columns:
                if column != correlated_with:
                    value = correlation.loc[column, correlated_with]
                    if pd.notna(value):
                        viz_data["correlations"].append({
                            "column": str(column),
                            "correlated_with": str(correlated_with),
                            "value": round(float(value), 4)
                        })

    return viz_data

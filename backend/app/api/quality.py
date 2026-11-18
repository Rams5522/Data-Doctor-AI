from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.services.dataset import DatasetService
from app.db.session import get_db
from app.db.models import Dataset, DatasetVersion, QualityFinding
from app.quality.checks import QualityCheckService
from app.services.tabular_format import read_tabular
from app.db.models import DatasetProfile
from typing import Dict, Any
from app.db.models import DatasetVersion as DV

# read_tabular will honor stored format metadata when present.
import pandas as pd

router = APIRouter()
quality_service = QualityCheckService()

@router.post("/{dataset_id}/detect")
async def detect_quality_issues(
    dataset_id: int,
    version_id: int = Query(None),
    db: Session = Depends(get_db)
):
    """Detect quality issues in a dataset"""
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

    # Read the dataset
    if not version.storage_path:
        raise HTTPException(status_code=404, detail="Dataset version has no storage file")
    df = read_tabular(version.storage_path, getattr(version, 'format_metadata', None))

    # Run quality checks
    findings = quality_service.run_all_checks(df)

    # Detection is idempotent: replace findings for this dataset version rather than appending duplicates.
    db.query(QualityFinding).filter(
        QualityFinding.dataset_id == dataset_id,
        QualityFinding.version_id == version.id
    ).delete(synchronize_session=False)
    db.commit()

    # Save findings to database
    saved_findings = []
    for finding in findings:
        # Create a unique finding ID if not already present
        if "finding_id" not in finding or not finding["finding_id"]:
            import hashlib
            finding_str = str(sorted(finding.items()))
            finding["finding_id"] = hashlib.md5(finding_str.encode()).hexdigest()[:12]

        db_finding = QualityFinding(
            dataset_id=dataset_id,
            version_id=version.id,
            finding_id=finding["finding_id"],
            issue_type=finding["issue_type"],
            severity=finding["severity"],
            affected_columns=finding["affected_columns"],
            affected_count=finding["affected_count"],
            affected_percent=finding["affected_percent"],
            evidence=finding["evidence"],
            possible_causes=finding.get("possible_causes", []),
            recommended_next_action=finding.get("recommended_next_action", ""),
            validation_status="pending"
        )
        db.add(db_finding)
        saved_findings.append(db_finding)

    db.commit()

    # Refresh to get IDs
    for finding in saved_findings:
        db.refresh(finding)

    # Create audit event
    from app.db.models import AuditEvent
    audit_event = AuditEvent(
        dataset_id=dataset_id,
        event_type="quality_check",
        event_data={
            "version_id": version.id,
            "findings_count": len(saved_findings),
            "issue_types": list(set([f.issue_type for f in saved_findings]))
        }
    )
    db.add(audit_event)
    db.commit()

    return {
        "message": f"Quality check completed. Found {len(saved_findings)} issues.",
        "dataset_id": dataset_id,
        "version_id": version.id,
        "findings": [
            {
                "id": f.id,
                "finding_id": f.finding_id,
                "issue_type": f.issue_type,
                "severity": f.severity,
                "affected_columns": f.affected_columns,
                "affected_count": f.affected_count,
                "affected_percent": f.affected_percent,
                "evidence": f.evidence,
                "possible_causes": f.possible_causes,
                "recommended_next_action": f.recommended_next_action,
                "validation_status": f.validation_status,
                "created_at": f.created_at.isoformat() if f.created_at else None
            }
            for f in saved_findings
        ]
    }

@router.get("/{dataset_id}/findings")
async def get_quality_findings(
    dataset_id: int,
    version_id: int = Query(None),
    issue_type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """Get quality findings for a dataset"""
    # Get dataset
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # Build query
    query = db.query(QualityFinding).filter(QualityFinding.dataset_id == dataset_id)

    if version_id is not None:
        query = query.filter(QualityFinding.version_id == version_id)

    if issue_type is not None:
        query = query.filter(QualityFinding.issue_type == issue_type)

    if severity is not None:
        query = query.filter(QualityFinding.severity == severity)

    # Get total count
    total = query.count()

    # Get findings with pagination
    findings = query.offset(skip).limit(limit).all()

    return {
        "dataset_id": dataset_id,
        "version_id": version_id,
        "total": total,
        "skip": skip,
        "limit": limit,
        "findings": [
            {
                "id": f.id,
                "finding_id": f.finding_id,
                "issue_type": f.issue_type,
                "severity": f.severity,
                "affected_columns": f.affected_columns,
                "affected_count": f.affected_count,
                "affected_percent": f.affected_percent,
                "evidence": f.evidence,
                "possible_causes": f.possible_causes,
                "recommended_next_action": f.recommended_next_action,
                "validation_status": f.validation_status,
                "created_at": f.created_at.isoformat() if f.created_at else None
            }
            for f in findings
        ]
    }

@router.get("/findings/{finding_id}")
async def get_finding_details(
    finding_id: int,
    db: Session = Depends(get_db)
):
    """Get details of a specific finding"""
    finding = db.query(QualityFinding).filter(QualityFinding.id == finding_id).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    return {
        "id": finding.id,
        "finding_id": finding.finding_id,
        "dataset_id": finding.dataset_id,
        "version_id": finding.version_id,
        "issue_type": finding.issue_type,
        "severity": finding.severity,
        "affected_columns": finding.affected_columns,
        "affected_count": finding.affected_count,
        "affected_percent": finding.affected_percent,
        "evidence": finding.evidence,
        "possible_causes": finding.possible_causes,
        "recommended_next_action": finding.recommended_next_action,
        "validation_status": finding.validation_status,
        "created_at": finding.created_at.isoformat() if finding.created_at else None
    }

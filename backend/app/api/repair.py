"""
API endpoints for repair functionality.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from app.services.dataset import DatasetService
from app.services.repair import get_repair_service
from app.db.session import get_db
from app.db.models import Dataset, DatasetVersion, QualityFinding, RepairCandidate, ValidationResult

router = APIRouter()

@router.post("/{dataset_id}/versions/{version_id}/findings/{finding_id}/candidates")
async def generate_repair_candidates(
    dataset_id: int,
    version_id: int,
    finding_id: int,
    db: Session = Depends(get_db)
):
    """Generate repair candidates for a specific quality finding."""
    # Verify dataset exists
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # Verify version exists
    version = db.query(DatasetVersion).filter(
        DatasetVersion.id == version_id,
        DatasetVersion.dataset_id == dataset_id
    ).first()
    if not version:
        raise HTTPException(status_code=404, detail="Dataset version not found")

    # Verify finding exists
    finding = db.query(QualityFinding).filter(
        QualityFinding.id == finding_id,
        QualityFinding.dataset_id == dataset_id,
        QualityFinding.version_id == version_id
    ).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Quality finding not found")

    # Generate candidates
    repair_service = get_repair_service(db)
    candidates = repair_service.generate_repair_candidates(dataset_id, version_id, finding_id)

    # Save candidates to database
    saved_candidates = []
    for candidate in candidates:
        db_candidate = repair_service.save_repair_candidate(dataset_id, version_id, candidate)
        saved_candidates.append(db_candidate)

    return {
        "dataset_id": dataset_id,
        "version_id": version_id,
        "finding_id": finding_id,
        "candidates_generated": len(saved_candidates),
        "candidates": [
            {
                "id": c.id,
                "candidate_id": c.candidate_id,
                "operation": c.operation,
                "parameters": c.parameters,
                "description": c.description,
                "issue_type": c.issue_type,
                "created_at": c.created_at.isoformat() if c.created_at else None
            }
            for c in saved_candidates
        ]
    }

@router.get("/{dataset_id}/versions/{version_id}/findings/{finding_id}/candidates")
async def list_repair_candidates(
    dataset_id: int,
    version_id: int,
    finding_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List repair candidates for a specific quality finding."""
    # Verify dataset exists
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # Verify version exists
    version = db.query(DatasetVersion).filter(
        DatasetVersion.id == version_id,
        DatasetVersion.dataset_id == dataset_id
    ).first()
    if not version:
        raise HTTPException(status_code=404, detail="Dataset version not found")

    # Get candidates
    candidates = db.query(RepairCandidate).filter(
        RepairCandidate.dataset_id == dataset_id,
        RepairCandidate.version_id == version_id,
        RepairCandidate.finding_id == finding_id
    ).offset(skip).limit(limit).all()

    total = db.query(RepairCandidate).filter(
        RepairCandidate.dataset_id == dataset_id,
        RepairCandidate.version_id == version_id,
        RepairCandidate.finding_id == finding_id
    ).count()

    return {
        "dataset_id": dataset_id,
        "version_id": version_id,
        "finding_id": finding_id,
        "total": total,
        "skip": skip,
        "limit": limit,
        "candidates": [
            {
                "id": c.id,
                "candidate_id": c.candidate_id,
                "operation": c.operation,
                "parameters": c.parameters,
                "description": c.description,
                "issue_type": c.issue_type,
                "created_at": c.created_at.isoformat() if c.created_at else None
            }
            for c in candidates
        ]
    }

@router.post("/repair-candidates/{candidate_id}/validate")
async def validate_repair_candidate(
    candidate_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Validate a repair candidate."""
    # Get the candidate
    candidate = db.query(RepairCandidate).filter(RepairCandidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Repair candidate not found")

    # Validate the candidate (run in background for potentially long-running operations)
    repair_service = get_repair_service(db)

    # For now, run synchronously - in production we might want to use background tasks
    # for long validations, but for MVP we'll keep it simple
    validation_result = repair_service.validate_repair_candidate(
        candidate.dataset_id,
        candidate.version_id,
        {
            "candidate_id": candidate.candidate_id,
            "finding_id": candidate.finding_id,
            "dataset_id": candidate.dataset_id,
            "version_id": candidate.version_id,
            "operation": candidate.operation,
            "parameters": candidate.parameters,
            "description": candidate.description,
            "issue_type": candidate.issue_type
        }
    )

    # Save validation result
    db_validation = repair_service.save_validation_result(candidate_id, validation_result)

    return {
        "validation_id": db_validation.id,
        "candidate_id": candidate_id,
        "execution_status": db_validation.execution_status,
        "validation_status": db_validation.validation_status,
        "metrics": db_validation.metrics,
        "issues_before_after": db_validation.issues_before_after,
        "warnings": db_validation.warnings,
        "errors": db_validation.errors,
        "operation_description": db_validation.operation_description,
        "validated_at": db_validation.validated_at.isoformat() if db_validation.validated_at else None
    }

@router.post("/repair-candidates/{candidate_id}/approve")
async def approve_repair_candidate(
    candidate_id: int,
    approved_by: str = "system",
    db: Session = Depends(get_db)
):
    """Approve a repair candidate and create a new dataset version."""
    # Get the candidate
    candidate = db.query(RepairCandidate).filter(RepairCandidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Repair candidate not found")

    # Approve the repair
    repair_service = get_repair_service(db)
    try:
        result = repair_service.approve_repair(
            candidate.dataset_id,
            candidate.version_id,
            candidate_id,
            approved_by
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/repair-candidates/{candidate_id}/reject")
async def reject_repair_candidate(
    candidate_id: int,
    rejected_by: str = "system",
    db: Session = Depends(get_db)
):
    """Reject a repair candidate."""
    # Get the candidate
    candidate = db.query(RepairCandidate).filter(RepairCandidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Repair candidate not found")

    # Reject the repair
    repair_service = get_repair_service(db)
    result = repair_service.reject_repair(
        candidate.dataset_id,
        candidate.version_id,
        candidate_id,
        rejected_by
    )
    return result

@router.post("/versions/{version_id}/rollback")
async def rollback_to_version(
    version_id: int,
    rolled_back_by: str = "system",
    db: Session = Depends(get_db)
):
    """Rollback to a previous dataset version."""
    # Get the version
    version = db.query(DatasetVersion).filter(DatasetVersion.id == version_id).first()
    if not version:
        raise HTTPException(status_code=404, detail="Dataset version not found")

    # Perform rollback
    repair_service = get_repair_service(db)
    try:
        result = repair_service.rollback_to_version(
            version.dataset_id,
            version_id,
            rolled_back_by
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/{dataset_id}/repair-history")
async def get_repair_history(
    dataset_id: int,
    db: Session = Depends(get_db)
):
    """Get repair history for a dataset."""
    # Verify dataset exists
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # Get history
    repair_service = get_repair_service(db)
    history = repair_service.get_repair_history(dataset_id)

    return {
        "dataset_id": dataset_id,
        "history": history
    }

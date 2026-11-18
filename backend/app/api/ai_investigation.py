"""
API endpoints for AI-powered investigations.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from app.services.ai_investigation import ai_investigation_service, InvestigationType
from app.services.llm_service import llm_service
from app.db.session import get_db
from app.db.models import Dataset, DatasetVersion, QualityFinding


router = APIRouter()


# Pydantic models
class InvestigationRequest(BaseModel):
    dataset_id: int
    version_id: int
    investigation_type: str
    user_query: str


class InvestigationResponse(BaseModel):
    dataset_id: int
    version_id: int
    investigation_type: str
    user_query: str
    analysis: str
    recommendations: List[str]
    evidence: List[dict]
    knowledge_base_articles: List[dict]
    similar_repairs: List[dict]
    dataset_context: dict
    status: str
    error: Optional[str] = None
    completed_at: str


class LLMStatusResponse(BaseModel):
    available: bool
    provider: str
    model: str
    available_models: List[str]


class LLMReloadResponse(BaseModel):
    provider: str
    model: str


class LLMConfigUpdate(BaseModel):
    provider: Optional[str] = None  # ollama, openai, or groq
    model: Optional[str] = None
    ollama_base_url: Optional[str] = None
    openai_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None


@router.post("/investigate", response_model=InvestigationResponse)
async def run_investigation(request: InvestigationRequest):
    """Run an AI-powered investigation on a dataset."""
    # Validate investigation type
    try:
        investigation_type = InvestigationType(request.investigation_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid investigation_type. Valid options: {[t.value for t in InvestigationType]}"
        )

    # Verify dataset exists
    db = next(get_db())
    try:
        dataset = db.query(Dataset).filter(Dataset.id == request.dataset_id).first()
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")

        version = db.query(DatasetVersion).filter(
            DatasetVersion.id == request.version_id,
            DatasetVersion.dataset_id == request.dataset_id
        ).first()
        if not version:
            raise HTTPException(status_code=404, detail="Dataset version not found")

        # Check if there are quality findings
        findings_count = db.query(QualityFinding).filter(
            QualityFinding.dataset_id == request.dataset_id,
            QualityFinding.version_id == request.version_id
        ).count()

        if findings_count == 0:
            raise HTTPException(
                status_code=400,
                detail="No quality findings available for this dataset version. Run quality check first."
            )

    finally:
        db.close()

    # Run investigation
    try:
        result = ai_investigation_service.run_investigation(
            dataset_id=request.dataset_id,
            version_id=request.version_id,
            investigation_type=request.investigation_type,
            user_query=request.user_query
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Investigation failed: {str(e)}")


@router.get("/investigation-types")
async def list_investigation_types():
    """List available investigation types."""
    return {
        "types": [
            {
                "id": InvestigationType.ROOT_CAUSE.value,
                "name": "Root Cause Analysis",
                "description": "Identify underlying causes of data quality issues",
                "icon": "🔍"
            },
            {
                "id": InvestigationType.PATTERN_ANALYSIS.value,
                "name": "Pattern Analysis",
                "description": "Discover patterns in data quality issues across columns",
                "icon": "📊"
            },
            {
                "id": InvestigationType.ANOMALY_DETECTION.value,
                "name": "Anomaly Detection",
                "description": "Identify unusual data patterns and outliers",
                "icon": "⚠️"
            },
            {
                "id": InvestigationType.IMPACT_ASSESSMENT.value,
                "name": "Impact Assessment",
                "description": "Analyze potential business impact of data issues",
                "icon": "📉"
            },
            {
                "id": InvestigationType.REPAIR_RECOMMENDATION.value,
                "name": "Repair Recommendation",
                "description": "Get AI-powered repair strategy recommendations",
                "icon": "🔧"
            }
        ]
    }


@router.get("/llm/status", response_model=LLMStatusResponse)
async def get_llm_status():
    """Get LLM provider status and available models."""
    return LLMStatusResponse(
        available=llm_service.is_available(),
        provider=llm_service.provider,
        model=llm_service.model,
        available_models=llm_service.get_available_models()
    )


@router.post("/llm/reload", response_model=LLMReloadResponse)
async def reload_llm_configuration():
    """Reload LLM settings from backend/.env without restarting the API."""
    return llm_service.reload_configuration()


@router.post("/llm/test")
async def test_llm_connection(prompt: str = "Say hello"):
    """Test LLM connection with a simple prompt."""
    if not llm_service.is_available():
        raise HTTPException(
            status_code=503,
            detail=f"LLM provider '{llm_service.provider}' not available. Check configuration."
        )

    try:
        response = llm_service.generate(
            prompt=prompt,
            system_prompt="You are a helpful assistant.",
            temperature=0.3,
            max_tokens=100
        )
        return {"response": response, "provider": llm_service.provider, "model": llm_service.model}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM test failed: {str(e)}")


@router.get("/datasets/{dataset_id}/versions/{version_id}/investigation-context")
async def get_investigation_context(
    dataset_id: int,
    version_id: int,
    db: Session = Depends(get_db)
):
    """Get context information needed for investigations."""
    # Verify dataset and version
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    version = db.query(DatasetVersion).filter(
        DatasetVersion.id == version_id,
        DatasetVersion.dataset_id == dataset_id
    ).first()
    if not version:
        raise HTTPException(status_code=404, detail="Dataset version not found")

    # Get findings
    findings = db.query(QualityFinding).filter(
        QualityFinding.dataset_id == dataset_id,
        QualityFinding.version_id == version_id
    ).all()

    findings_list = []
    for f in findings:
        findings_list.append({
            "id": f.id,
            "finding_id": f.finding_id,
            "issue_type": f.issue_type,
            "severity": f.severity,
            "affected_columns": f.affected_columns or [],
            "affected_count": f.affected_count,
            "affected_percent": f.affected_percent,
            "evidence": f.evidence or {},
            "recommended_next_action": f.recommended_next_action or ""
        })

    # Get profiling info
    from app.db.models import DatasetProfile
    profile = db.query(DatasetProfile).filter(
        DatasetProfile.dataset_id == dataset_id,
        DatasetProfile.version_id == version_id
    ).first()

    profile_summary = {}
    if profile:
        from app.services.profiling import ProfilingService
        profiling_service = ProfilingService()
        profile_summary = profiling_service.get_profile_summary(profile.profile_data)

    return {
        "dataset_id": dataset_id,
        "dataset_name": dataset.name,
        "version_id": version_id,
        "version_number": version.version_number,
        "version_type": version.version_type,
        "findings_count": len(findings_list),
        "findings": findings_list,
        "profile_summary": profile_summary,
        "available_investigation_types": [t.value for t in InvestigationType]
    }
from fastapi import APIRouter
from app.api import datasets, profiling, quality, repair, knowledge_base, ai_investigation

api_router = APIRouter()

# Include routers
api_router.include_router(datasets.router, prefix="/datasets", tags=["datasets"])
api_router.include_router(profiling.router, prefix="/profiling", tags=["profiling"])
api_router.include_router(quality.router, prefix="/quality", tags=["quality"])
api_router.include_router(repair.router, prefix="/repair", tags=["repair"])
api_router.include_router(knowledge_base.router, prefix="/knowledge-base", tags=["knowledge-base"])
api_router.include_router(ai_investigation.router, prefix="/ai-investigation", tags=["ai-investigation"])

"""
API endpoints for Knowledge Base (ChromaDB vector store).
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from app.services.knowledge_base import knowledge_base_service
from app.db.session import get_db


router = APIRouter()


# Pydantic models
class ArticleCreate(BaseModel):
    title: str
    content: str
    category: str
    tags: Optional[List[str]] = None
    metadata: Optional[dict] = None


class ArticleUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None


class ArticleResponse(BaseModel):
    id: str
    title: str
    content: str
    category: str
    tags: List[str]
    created_at: str
    updated_at: str
    similarity: Optional[float] = None


class SearchRequest(BaseModel):
    query: str
    category: Optional[str] = None
    limit: int = 10
    min_similarity: float = 0.3


@router.post("/articles", response_model=ArticleResponse)
async def create_article(article: ArticleCreate):
    """Add a new article to the knowledge base."""
    try:
        result = knowledge_base_service.add_article(
            title=article.title,
            content=article.content,
            category=article.category,
            tags=article.tags,
            metadata=article.metadata
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create article: {str(e)}")


@router.get("/articles", response_model=List[ArticleResponse])
async def search_articles(
    query: str = Query(..., description="Search query"),
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(10, ge=1, le=50),
    min_similarity: float = Query(0.3, ge=0.0, le=1.0)
):
    """Search articles by semantic similarity."""
    try:
        results = knowledge_base_service.search_articles(
            query=query,
            category=category,
            limit=limit,
            min_similarity=min_similarity
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/articles/{article_id}", response_model=ArticleResponse)
async def get_article(article_id: str):
    """Get a specific article by ID."""
    article = knowledge_base_service.get_article(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article


@router.put("/articles/{article_id}", response_model=ArticleResponse)
async def update_article(article_id: str, article: ArticleUpdate):
    """Update an existing article."""
    result = knowledge_base_service.update_article(
        article_id=article_id,
        title=article.title,
        content=article.content,
        category=article.category,
        tags=article.tags
    )
    if not result:
        raise HTTPException(status_code=404, detail="Article not found")
    return result


@router.delete("/articles/{article_id}")
async def delete_article(article_id: str):
    """Delete an article."""
    success = knowledge_base_service.delete_article(article_id)
    if not success:
        raise HTTPException(status_code=404, detail="Article not found")
    return {"message": "Article deleted successfully"}


@router.get("/categories")
async def list_categories():
    """List all categories with article counts."""
    try:
        categories = knowledge_base_service.list_categories()
        return {"categories": categories}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list categories: {str(e)}")


@router.post("/initialize")
async def initialize_knowledge_base():
    """Initialize the knowledge base with default articles."""
    try:
        articles = knowledge_base_service.initialize_default_knowledge()
        return {
            "message": f"Initialized knowledge base with {len(articles)} articles",
            "articles": articles
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Initialization failed: {str(e)}")


# Repair Memory Endpoints

@router.post("/repair-memory")
async def store_approved_repair(
    finding_type: str,
    operation: str,
    parameters: dict,
    dataset_context: dict,
    validation_metrics: dict,
    outcome: str = "success"
):
    """Store an approved repair for future reference."""
    try:
        repair_id = knowledge_base_service.store_approved_repair(
            finding_type=finding_type,
            operation=operation,
            parameters=parameters,
            dataset_context=dataset_context,
            validation_metrics=validation_metrics,
            outcome=outcome
        )
        return {"repair_id": repair_id, "message": "Repair stored successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to store repair: {str(e)}")


@router.get("/repair-memory")
async def find_similar_repairs(
    finding_type: str = Query(..., description="Type of quality issue"),
    num_rows: int = Query(0, description="Number of rows in dataset"),
    num_cols: int = Query(0, description="Number of columns in dataset"),
    version_type: str = Query("original", description="Dataset version type"),
    limit: int = Query(5, ge=1, le=20)
):
    """Find similar approved repairs for context-aware recommendations."""
    try:
        dataset_context = {
            "num_rows": num_rows,
            "num_cols": num_cols,
            "version_type": version_type
        }
        repairs = knowledge_base_service.find_similar_repairs(
            finding_type=finding_type,
            dataset_context=dataset_context,
            limit=limit
        )
        return {"repairs": repairs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to find similar repairs: {str(e)}")
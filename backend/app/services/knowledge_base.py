"""
Knowledge Base Service using ChromaDB for vector storage and semantic search.
Stores data quality patterns, repair strategies, and best practices.
"""

import os
import json
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime

from app.core.config import settings


class KnowledgeBaseService:
    """Service for managing knowledge base with ChromaDB vector store."""

    def __init__(self):
        self.persist_directory = settings.CHROMA_PERSIST_DIRECTORY
        self._client = None
        self._embedding_model = None
        self._articles_collection = None
        self._repair_memory_collection = None

    @property
    def client(self):
        if self._client is None:
            import chromadb
            from chromadb.config import Settings
            os.makedirs(self.persist_directory, exist_ok=True)
            self._client = chromadb.PersistentClient(
                path=self.persist_directory,
                settings=Settings(anonymized_telemetry=False)
            )
        return self._client

    @property
    def embedding_model(self):
        if self._embedding_model is None:
            from sentence_transformers import SentenceTransformer
            self._embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        return self._embedding_model

    @property
    def articles_collection(self):
        if self._articles_collection is None:
            self._articles_collection = self.client.get_or_create_collection(
                name="knowledge_base_articles",
                metadata={"description": "Data quality patterns and repair strategies"}
            )
        return self._articles_collection

    @property
    def repair_memory_collection(self):
        if self._repair_memory_collection is None:
            self._repair_memory_collection = self.client.get_or_create_collection(
                name="approved_repairs",
                metadata={"description": "Approved repair operations for context-aware recommendations"}
            )
        return self._repair_memory_collection

    def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using sentence transformer."""
        return self.embedding_model.encode(text).tolist()

    def add_article(self,
                    title: str,
                    content: str,
                    category: str,
                    tags: Optional[List[str]] = None,
                    metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Add an article to the knowledge base."""
        article_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        # Combine title and content for embedding
        full_text = f"{title}\n\n{content}"
        embedding = self._generate_embedding(full_text)

        # Prepare metadata
        article_metadata = {
            "title": title,
            "category": category,
            "tags": json.dumps(tags or []),
            "created_at": now,
            "updated_at": now,
            **(metadata or {})
        }

        # Add to collection
        self.articles_collection.add(
            ids=[article_id],
            documents=[full_text],
            embeddings=[embedding],
            metadatas=[article_metadata]
        )

        result = {
            "id": article_id,
            "title": title,
            "content": content,
            "category": category,
            "tags": tags or [],
            "created_at": now,
            "updated_at": now
        }
        if metadata:
            result.update(metadata)
        return result

    def search_articles(self,
                        query: str,
                        category: Optional[str] = None,
                        limit: int = 10,
                        min_similarity: float = 0.3) -> List[Dict[str, Any]]:
        """Search articles by semantic similarity."""
        query_embedding = self._generate_embedding(query)

        # Build where clause for category filter
        where = {}
        if category and category != "all":
            where["category"] = category

        results = self.articles_collection.query(
            query_embeddings=[query_embedding],
            n_results=limit,
            where=where if where else None,
            include=["documents", "metadatas", "distances"]
        )

        articles = []
        if results["ids"] and results["ids"][0]:
            for i, article_id in enumerate(results["ids"][0]):
                distance = results["distances"][0][i]
                # ChromaDB's "cosine" distance returns squared Euclidean distance for normalized vectors:
                # distance = 2 - 2*cosine_similarity
                # So cosine_similarity = 1 - distance/2
                similarity = 1 - distance / 2

                if similarity >= min_similarity:
                    metadata = results["metadatas"][0][i]
                    articles.append({
                        "id": article_id,
                        "title": metadata.get("title", ""),
                        "content": results["documents"][0][i],
                        "category": metadata.get("category", ""),
                        "tags": json.loads(metadata.get("tags", "[]")),
                        "created_at": metadata.get("created_at", ""),
                        "updated_at": metadata.get("updated_at", ""),
                        "similarity": round(similarity, 3)
                    })

        return articles

    def get_article(self, article_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific article by ID."""
        results = self.articles_collection.get(
            ids=[article_id],
            include=["documents", "metadatas"]
        )

        if results["ids"] and results["ids"][0]:
            metadata = results["metadatas"][0]
            return {
                "id": article_id,
                "title": metadata.get("title", ""),
                "content": results["documents"][0],
                "category": metadata.get("category", ""),
                "tags": json.loads(metadata.get("tags", "[]")),
                "created_at": metadata.get("created_at", ""),
                "updated_at": metadata.get("updated_at", "")
            }
        return None

    def update_article(self,
                       article_id: str,
                       title: Optional[str] = None,
                       content: Optional[str] = None,
                       category: Optional[str] = None,
                       tags: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """Update an existing article."""
        existing = self.get_article(article_id)
        if not existing:
            return None

        new_title = title or existing["title"]
        new_content = content or existing["content"]
        new_category = category or existing["category"]
        new_tags = tags or existing["tags"]

        # Re-embed if content changed
        full_text = f"{new_title}\n\n{new_content}"
        embedding = self._generate_embedding(full_text)

        # Update metadata
        metadata = {
            "title": new_title,
            "category": new_category,
            "tags": json.dumps(new_tags),
            "created_at": existing["created_at"],
            "updated_at": datetime.now().isoformat()
        }

        self.articles_collection.update(
            ids=[article_id],
            documents=[full_text],
            embeddings=[embedding],
            metadatas=[metadata]
        )

        return {**existing, "title": new_title, "content": new_content,
                "category": new_category, "tags": new_tags,
                "updated_at": metadata["updated_at"]}

    def delete_article(self, article_id: str) -> bool:
        """Delete an article."""
        try:
            self.articles_collection.delete(ids=[article_id])
            return True
        except Exception:
            return False

    def list_categories(self) -> List[Dict[str, Any]]:
        """List all categories with article counts."""
        results = self.articles_collection.get(include=["metadatas"])
        categories = {}
        for metadata in results["metadatas"]:
            cat = metadata.get("category", "uncategorized")
            categories[cat] = categories.get(cat, 0) + 1

        return [
            {"id": cat, "name": cat.replace("_", " ").title(), "count": count}
            for cat, count in sorted(categories.items())
        ]

    # Repair Memory Methods

    def store_approved_repair(self,
                              finding_type: str,
                              operation: str,
                              parameters: Dict[str, Any],
                              dataset_context: Dict[str, Any],
                              validation_metrics: Dict[str, Any],
                              outcome: str = "success") -> str:
        """Store an approved repair for future reference."""
        repair_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        # Create a descriptive text for embedding
        text = f"Issue: {finding_type}. Repair: {operation}. Parameters: {json.dumps(parameters)}. Context: {json.dumps(dataset_context)}. Outcome: {outcome}"
        embedding = self._generate_embedding(text)

        metadata = {
            "finding_type": finding_type,
            "operation": operation,
            "parameters": json.dumps(parameters),
            "dataset_context": json.dumps(dataset_context),
            "validation_metrics": json.dumps(validation_metrics),
            "outcome": outcome,
            "created_at": now
        }

        self.repair_memory_collection.add(
            ids=[repair_id],
            documents=[text],
            embeddings=[embedding],
            metadatas=[metadata]
        )

        return repair_id

    def find_similar_repairs(self,
                             finding_type: str,
                             dataset_context: Dict[str, Any],
                             limit: int = 5) -> List[Dict[str, Any]]:
        """Find similar approved repairs for context-aware recommendations."""
        query_text = f"Issue: {finding_type}. Context: {json.dumps(dataset_context)}"
        query_embedding = self._generate_embedding(query_text)

        results = self.repair_memory_collection.query(
            query_embeddings=[query_embedding],
            n_results=limit,
            include=["documents", "metadatas", "distances"]
        )

        repairs = []
        if results["ids"] and results["ids"][0]:
            for i, repair_id in enumerate(results["ids"][0]):
                distance = results["distances"][0][i]
                # ChromaDB's "cosine" distance returns squared Euclidean distance for normalized vectors:
                # distance = 2 - 2*cosine_similarity
                # So cosine_similarity = 1 - distance/2
                similarity = 1 - distance / 2

                metadata = results["metadatas"][0][i]
                repairs.append({
                    "id": repair_id,
                    "finding_type": metadata.get("finding_type", ""),
                    "operation": metadata.get("operation", ""),
                    "parameters": json.loads(metadata.get("parameters", "{}")),
                    "dataset_context": json.loads(metadata.get("dataset_context", "{}")),
                    "validation_metrics": json.loads(metadata.get("validation_metrics", "{}")),
                    "outcome": metadata.get("outcome", ""),
                    "created_at": metadata.get("created_at", ""),
                    "similarity": round(similarity, 3)
                })

        return repairs

    def initialize_default_knowledge(self) -> List[Dict[str, Any]]:
        """Initialize the knowledge base with default articles."""
        default_articles = [
            {
                "title": "Handling Missing Values in Numerical Columns",
                "content": """Missing values in numerical columns are one of the most common data quality issues.

                **Common Strategies:**
                1. **Global Median Imputation** - Replace missing values with the column's median. Robust to outliers.
                2. **Global Mean Imputation** - Replace with mean. Simple but sensitive to outliers.
                3. **Group-based Imputation** - Use median/mean within groups (e.g., by department, region). Preserves group differences.
                4. **Missing Indicator** - Add a binary column indicating which values were missing, then impute.

                **When to use which:**
                - Use global median for general-purpose imputation
                - Use group median when the column varies significantly by category
                - Always add missing indicator when missingness might be informative (MNAR - Missing Not At Random)

                **Validation Gates:**
                - Check that imputed values don't create new outliers
                - Verify distribution shape is preserved
                - Ensure no data leakage in group-based imputation""",
                "category": "data_quality",
                "tags": ["missing_values", "imputation", "numerical"]
            },
            {
                "title": "Detecting and Handling Duplicate Rows",
                "content": """Duplicate rows can arise from data entry errors, system integration issues, or batch processing duplicates.

                **Types of Duplicates:**
                - **Exact duplicates** - All columns identical
                - **Key-based duplicates** - Same identifier but different other values
                - **Near duplicates** - Similar but not identical (typos, formatting)

                **Strategies:**
                1. **Keep First** - Retain the first occurrence (default)
                2. **Keep Last** - Retain the most recent (if timestamp available)
                3. **Remove All** - Drop all rows in duplicate groups
                4. **Merge** - Combine information from duplicates

                **Best Practices:**
                - Always profile duplicates before removal
                - Check if duplicates represent real repeated measurements
                - Use key columns (IDs) for deduplication when available
                - Document the deduplication strategy used""",
                "category": "data_quality",
                "tags": ["duplicates", "deduplication", "data_cleaning"]
            },
            {
                "title": "Standardizing Categorical Data",
                "content": """Categorical data often has inconsistencies due to manual entry, different sources, or legacy systems.

                **Common Issues:**
                - Case variations: "Engineering", "engineering", "ENGINEERING"
                - Whitespace: " Engineering", "Engineering ", "Engineering"
                - Abbreviations: "Eng", "Eng.", "Engineering"
                - Spelling variants: "Marketting" vs "Marketing"

                **Standardization Strategies:**
                1. **Trim Whitespace** - Remove leading/trailing spaces
                2. **Case Normalization** - Lowercase, UPPERCASE, or Title Case
                3. **Value Mapping** - Explicit mapping of variants to canonical values
                4. **Fuzzy Matching** - Use string similarity for near-duplicates

                **Validation:**
                - Check unique value count before/after
                - Verify no valid categories were merged incorrectly
                - Ensure referential integrity with related tables""",
                "category": "data_quality",
                "tags": ["categorical", "standardization", "cleaning"]
            },
            {
                "title": "Date Parsing and Normalization",
                "content": """Date columns frequently have mixed formats, especially when data comes from multiple sources or regions.

                **Common Date Formats:**
                - ISO 8601: YYYY-MM-DD (recommended standard)
                - US: MM/DD/YYYY
                - European: DD/MM/YYYY
                - With times: YYYY-MM-DD HH:MM:SS
                - Various separators: /, -, .

                **Strategy:**
                1. **Detect format** - Sample valid dates to infer format
                2. **Parse with explicit format** - Use pd.to_datetime with format parameter
                3. **Normalize to ISO** - Convert all to YYYY-MM-DD
                4. **Flag unparseable** - Convert failures to NaT (missing)

                **Validation:**
                - Check date ranges are reasonable
                - Verify no future dates where impossible
                - Ensure start_date <= end_date for date pairs
                - Check for impossible dates (Feb 30, etc.)""",
                "category": "data_quality",
                "tags": ["dates", "parsing", "normalization"]
            },
            {
                "title": "Outlier Detection and Treatment",
                "content": """Outliers can be genuine extreme values or data errors. Treatment depends on context.

                **Detection Methods:**
                1. **IQR Method** - Values beyond Q1-1.5*IQR or Q3+1.5*IQR
                2. **Z-Score** - Values beyond 3 standard deviations
                3. **Percentile Capping** - Cap at 1st/99th percentiles

                **Treatment Options:**
                - **Flag only** - Add outlier indicator column, keep values
                - **Cap/Winsorize** - Replace with boundary values
                - **Remove** - Delete outlier rows (use cautiously)
                - **Transform** - Log/sqrt transform to reduce skew

                **Best Practices:**
                - Always investigate before treating
                - Document which method and thresholds used
                - Consider domain knowledge (e.g., salary outliers might be executives)
                - Flagging is often safer than removing""",
                "category": "data_quality",
                "tags": ["outliers", "detection", "treatment"]
            },
            {
                "title": "Business Rule Validation",
                "content": """Business rules encode domain knowledge that data must satisfy.

                **Common Rule Types:**
                - **Range constraints**: age 0-120, percentage 0-100
                - **Cross-field**: end_date >= start_date, total = sum(parts)
                - **Conditional**: if status='active' then email must exist
                - **Uniqueness**: employee_id must be unique

                **Implementation:**
                - Define rules in configuration (not code)
                - Run as part of quality checks
                - Provide clear error messages
                - Track rule violations over time

                **Repair Strategies:**
                - Make violating fields missing, then impute
                - Cap values to valid ranges
                - Swap fields if order violation (start/end date)
                - Require manual review for complex violations""",
                "category": "repair_strategies",
                "tags": ["business_rules", "validation", "constraints"]
            },
            {
                "title": "Type Conversion Strategies",
                "content": """Mixed types in a column often indicate data quality issues or schema changes.

                **Detection:**
                - Check dtype consistency after loading
                - Sample non-null values for type variety

                **Conversion Approaches:**
                1. **To Numeric** - pd.to_numeric(errors='coerce'), then handle NaN
                2. **To Datetime** - pd.to_datetime with format inference
                3. **To String** - Safe fallback, preserves all data
                4. **To Category** - For low-cardinality strings

                **Validation:**
                - Check conversion success rate
                - Verify no precision loss for numeric
                - Ensure datetime parsing didn't create invalid dates""",
                "category": "repair_strategies",
                "tags": ["type_conversion", "schema", "data_types"]
            }
        ]

        added = []
        for article in default_articles:
            result = self.add_article(**article)
            added.append(result)

        return added


# Singleton instance
knowledge_base_service = KnowledgeBaseService()
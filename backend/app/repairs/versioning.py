"""Immutable, format-preserving dataset version storage."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

import pandas as pd

from app.core.config import BACKEND_DIR
from app.services.tabular_format import capture_format_metadata, format_from_path, verify_round_trip, write_tabular


class DatasetVersioningService:
    """Create verified immutable artifacts without changing the source version."""

    def __init__(self, storage_dir: Optional[str] = None):
        self.storage_dir = Path(storage_dir) if storage_dir else BACKEND_DIR / "storage" / "dataset_versions"
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def save_version(
        self,
        df: pd.DataFrame,
        dataset_id: int,
        parent_version_id: Optional[int] = None,
        version_type: str = "repaired",
        description: str = "",
        format_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Serialize and round-trip verify a new version in the parent file format."""
        metadata = dict(format_metadata or {"format": "csv"})
        file_format = metadata.get("format")
        if not file_format:
            raise ValueError("A source file format is required to save a repaired version")

        artifact_id = uuid4().hex
        filename = f"dataset_{dataset_id}_{artifact_id}.{file_format}"
        final_path = self.storage_dir / filename
        temporary_path = self.storage_dir / f".{filename}.tmp"

        try:
            # Keep the final extension on the temporary file because writer engines infer it.
            temporary_path = self.storage_dir / f".{artifact_id}.{file_format}.tmp.{file_format}"
            write_tabular(df, str(temporary_path), metadata)
            round_trip = verify_round_trip(df, str(temporary_path), metadata)
            os.replace(temporary_path, final_path)
            content_hash = self._compute_file_hash(str(final_path))
        except Exception:
            if temporary_path.exists():
                temporary_path.unlink()
            if final_path.exists():
                final_path.unlink()
            raise

        return {
            "storage_path": str(final_path),
            "version_type": version_type,
            "content_hash": content_hash,
            "parent_version_id": parent_version_id,
            "description": description,
            "file_format": file_format,
            "format_metadata": metadata,
            **round_trip,
        }

    def _compute_file_hash(self, file_path: str) -> str:
        digest = hashlib.sha256()
        with open(file_path, "rb") as source:
            for chunk in iter(lambda: source.read(4096), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def verify_file_integrity(self, file_path: str, expected_hash: str) -> bool:
        return self._compute_file_hash(file_path) == expected_hash


versioning_service = DatasetVersioningService()

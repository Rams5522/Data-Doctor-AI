import os
import hashlib
import pandas as pd
from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session
from app.db.models import Dataset, DatasetVersion
from app.core.config import settings, BACKEND_DIR
from app.services.tabular_format import capture_format_metadata, read_tabular
from datetime import datetime
import uuid

class DatasetService:
    def __init__(self, db: Session):
        self.db = db
        self.upload_dir = str(BACKEND_DIR / "storage" / "uploads")
        self.versions_dir = str(BACKEND_DIR / "storage" / "dataset_versions")

        # Create directories if they don't exist
        os.makedirs(self.upload_dir, exist_ok=True)
        os.makedirs(self.versions_dir, exist_ok=True)

    def validate_file(self, file: UploadFile):
        """Validate uploaded file"""
        # Tabular datasets can be repaired while preserving their format.
        extension = os.path.splitext(file.filename or "")[1].lower()
        if extension not in {'.csv', '.xlsx', '.xls', '.json'}:
            raise HTTPException(status_code=400, detail="Supported data formats are CSV, XLSX, XLS, and JSON")

        # Check file size
        file.file.seek(0, 2)  # Seek to end
        file_size = file.file.tell()
        file.file.seek(0)  # Reset to beginning

        max_size_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
        if file_size > max_size_bytes:
            raise HTTPException(
                status_code=400,
                detail=f"File size exceeds maximum allowed size of {settings.MAX_UPLOAD_MB} MB"
            )

        # Check if file is empty
        if file_size == 0:
            raise HTTPException(status_code=400, detail="File is empty")

        return True

    def save_original_file(self, file: UploadFile, dataset_id: int) -> str:
        """Save the original uploaded file and return the file path"""
        # Generate a unique filename
        file_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"{dataset_id}_{uuid.uuid4()}{file_extension}"
        file_path = os.path.join(self.upload_dir, unique_filename)

        # Save the file
        with open(file_path, "wb") as buffer:
            content = file.file.read()
            buffer.write(content)

        return file_path

    def compute_content_hash(self, file_path: str) -> str:
        """Compute SHA256 hash of file content"""
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()

    def create_dataset_record(self, name: str, description: str = None) -> Dataset:
        """Create a new dataset record"""
        dataset = Dataset(name=name, description=description)
        self.db.add(dataset)
        self.db.commit()
        self.db.refresh(dataset)
        return dataset

    def create_first_version(self, dataset_id: int, file_path: str, content_hash: str) -> DatasetVersion:
        """Create the first version of a dataset with its source format metadata."""
        format_metadata = capture_format_metadata(file_path)
        version = DatasetVersion(
            dataset_id=dataset_id,
            version_number=1,
            storage_path=file_path,
            version_type="original",
            content_hash=content_hash,
            file_format=format_metadata["format"],
            format_metadata=format_metadata,
            artifact_status="committed"
        )
        self.db.add(version)
        self.db.commit()
        self.db.refresh(version)
        return version

    def upload_dataset(self, file: UploadFile, name: str, description: str = None) -> dict:
        """Handle complete dataset upload process"""
        # Validate file
        self.validate_file(file)

        if not name or not name.strip():
            raise HTTPException(status_code=400, detail="Dataset name is required")

        # Parse before creating database records so malformed uploads cannot create empty datasets.
        try:
            position = file.file.tell()
            extension = os.path.splitext(file.filename or "")[1].lower()
            if extension == '.json':
                pd.read_json(file.file)
            elif extension in {'.xlsx', '.xls'}:
                pd.read_excel(file.file)
            else:
                pd.read_csv(file.file)
            file.file.seek(position)
        except Exception as exc:
            file.file.seek(0)
            raise HTTPException(status_code=400, detail=f"Unable to read dataset: {exc}")

        # Create dataset record only after the upload has been validated.
        dataset = self.create_dataset_record(name.strip(), description)

        # Save original file
        file_path = self.save_original_file(file, dataset.id)

        # Compute content hash
        content_hash = self.compute_content_hash(file_path)

        # Create first version
        version = self.create_first_version(dataset.id, file_path, content_hash)

        # Create audit event
        self._create_audit_event(
            dataset.id,
            "upload",
            {
                "filename": file.filename,
                "size": os.path.getsize(file_path),
                "content_hash": content_hash
            }
        )

        return {
            "dataset_id": dataset.id,
            "version_id": version.id,
            "name": dataset.name,
            "description": dataset.description,
            "version_number": version.version_number,
            "content_hash": content_hash,
            "upload_timestamp": dataset.created_at.isoformat()
        }

    def _create_audit_event(self, dataset_id: int, event_type: str, event_data: dict):
        """Create an audit event"""
        from app.db.models import AuditEvent
        audit_event = AuditEvent(
            dataset_id=dataset_id,
            event_type=event_type,
            event_data=event_data
        )
        self.db.add(audit_event)
        self.db.commit()

    def get_dataset(self, dataset_id: int) -> Dataset:
        """Get dataset by ID"""
        dataset = self.db.query(Dataset).filter(Dataset.id == dataset_id).first()
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")
        return dataset

    def list_datasets(self, skip: int = 0, limit: int = 100) -> list:
        """List datasets with pagination"""
        return self.db.query(Dataset).offset(skip).limit(limit).all()

    def delete_dataset(self, dataset_id: int):
        """Delete dataset and associated files"""
        dataset = self.get_dataset(dataset_id)

        # Delete all version files
        versions = self.db.query(DatasetVersion).filter(DatasetVersion.dataset_id == dataset_id).all()
        for version in versions:
            if os.path.exists(version.storage_path):
                os.remove(version.storage_path)

        # Delete audit events
        self.db.query(AuditEvent).filter(AuditEvent.dataset_id == dataset_id).delete()

        # Delete findings
        self.db.query(QualityFinding).filter(QualityFinding.dataset_id == dataset_id).delete()

        # Delete profiles
        self.db.query(DatasetProfile).filter(DatasetProfile.dataset_id == dataset_id).delete()

        # Delete versions
        self.db.query(DatasetVersion).filter(DatasetVersion.dataset_id == dataset_id).delete()

        # Delete dataset
        self.db.delete(dataset)
        self.db.commit()

    def _read_tabular(self, path: str, nrows=None, format_metadata: dict = None):
        return read_tabular(path, format_metadata, nrows=nrows)

    def get_dataset_preview(self, dataset_id: int, version_id: int = None, limit: int = 100) -> dict:
        """Get a preview of the dataset"""
        if version_id is None:
            # Get the latest version
            version = self.db.query(DatasetVersion)\
                .filter(DatasetVersion.dataset_id == dataset_id)\
                .order_by(DatasetVersion.version_number.desc())\
                .first()
        else:
            version = self.db.query(DatasetVersion)\
                .filter(DatasetVersion.id == version_id)\
                .first()

        if not version:
            raise HTTPException(status_code=404, detail="Dataset version not found")

        if not os.path.exists(version.storage_path):
            raise HTTPException(status_code=404, detail="Dataset file not found")

        df = self._read_tabular(version.storage_path, nrows=limit, format_metadata=getattr(version, 'format_metadata', None))

        total_rows = len(self._read_tabular(version.storage_path, format_metadata=getattr(version, 'format_metadata', None)))

        return {
            "columns": df.columns.tolist(),
            "data": df.fillna("").to_dict(orient="records"),  # Replace NaN with empty string for JSON
            "total_rows": total_rows,
            "preview_rows": len(df),
            "version_id": version.id,
            "version_number": version.version_number
        }

# Import AuditEvent here to avoid circular import
from app.db.models import AuditEvent, QualityFinding, DatasetProfile
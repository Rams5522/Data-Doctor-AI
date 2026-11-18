from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import FileResponse, StreamingResponse
from io import BytesIO
import json
import re
import pandas as pd
from sqlalchemy.orm import Session
from typing import List, Optional
import os
from app.services.dataset import DatasetService
from app.db.session import get_db
from app.db.models import Dataset, DatasetVersion
from app.services.tabular_format import MEDIA_TYPES, format_from_path
from app.services.tabular_format import capture_format_metadata
from app.core.config import BACKEND_DIR

router = APIRouter()

@router.post("/upload")
async def upload_dataset(
    file: UploadFile = File(...),
    name: str = Form(...),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Upload a new dataset"""
    dataset_service = DatasetService(db)
    result = dataset_service.upload_dataset(file, name, description)
    return result

@router.get("/", response_model=List[dict])
async def list_datasets(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """List all datasets"""
    dataset_service = DatasetService(db)
    datasets = dataset_service.list_datasets(skip, limit)

    result = []
    for dataset in datasets:
        # Get latest version
        latest_version = db.query(DatasetVersion)\
            .filter(DatasetVersion.dataset_id == dataset.id)\
            .order_by(DatasetVersion.version_number.desc())\
            .first()

        result.append({
            "id": dataset.id,
            "name": dataset.name,
            "description": dataset.description,
            "created_at": dataset.created_at.isoformat() if dataset.created_at else None,
            "updated_at": dataset.updated_at.isoformat() if dataset.updated_at else None,
            "latest_version": {
                "id": latest_version.id if latest_version else None,
                "version_number": latest_version.version_number if latest_version else None,
                "version_type": latest_version.version_type if latest_version else None,
                "file_format": latest_version.file_format if latest_version else None,
                "format_metadata": latest_version.format_metadata if latest_version else None
            } if latest_version else None
        })

    return result

@router.get("/{dataset_id}")
async def get_dataset(
    dataset_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific dataset"""
    dataset_service = DatasetService(db)
    dataset = dataset_service.get_dataset(dataset_id)

    # Get latest version
    latest_version = db.query(DatasetVersion)\
        .filter(DatasetVersion.dataset_id == dataset.id)\
        .order_by(DatasetVersion.version_number.desc())\
        .first()

    return {
        "id": dataset.id,
        "name": dataset.name,
        "description": dataset.description,
        "created_at": dataset.created_at.isoformat() if dataset.created_at else None,
        "updated_at": dataset.updated_at.isoformat() if dataset.updated_at else None,
        "latest_version": {
            "id": latest_version.id if latest_version else None,
            "version_number": latest_version.version_number if latest_version else None,
            "storage_path": latest_version.storage_path if latest_version else None,
            "version_type": latest_version.version_type if latest_version else None,
            "content_hash": latest_version.content_hash if latest_version else None,
            "created_at": latest_version.created_at.isoformat() if latest_version.created_at else None
        } if latest_version else None
    }

@router.delete("/{dataset_id}")
async def delete_dataset(
    dataset_id: int,
    db: Session = Depends(get_db)
):
    """Delete a dataset"""
    dataset_service = DatasetService(db)
    dataset_service.delete_dataset(dataset_id)
    return {"message": "Dataset deleted successfully"}

@router.get("/{dataset_id}/versions")
async def get_dataset_versions(
    dataset_id: int,
    db: Session = Depends(get_db)
):
    """Get all versions of a dataset"""
    dataset_service = DatasetService(db)
    dataset = dataset_service.get_dataset(dataset_id)

    versions = db.query(DatasetVersion)\
        .filter(DatasetVersion.dataset_id == dataset_id)\
        .order_by(DatasetVersion.version_number.desc())\
        .all()

    result = []
    for version in versions:
        result.append({
            "id": version.id,
            "version_number": version.version_number,
            "storage_path": version.storage_path,
            "version_type": version.version_type,
            "content_hash": version.content_hash,
            "parent_version_id": version.parent_version_id,
            "created_at": version.created_at.isoformat() if version.created_at else None,
            "created_by": version.created_by,
            "file_format": version.file_format,
            "format_metadata": version.format_metadata
        })

    return result

@router.get("/{dataset_id}/preview")
async def get_dataset_preview(
    dataset_id: int,
    version_id: Optional[int] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """Get a preview of the dataset"""
    dataset_service = DatasetService(db)
    preview = dataset_service.get_dataset_preview(dataset_id, version_id, limit)
    return preview

@router.get("/{dataset_id}/versions/{version_id}/download")
async def download_dataset_version(
    dataset_id: int,
    version_id: int,
    db: Session = Depends(get_db)
):
    """Download an immutable dataset version using its stored format."""
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    version = db.query(DatasetVersion).filter(
        DatasetVersion.id == version_id,
        DatasetVersion.dataset_id == dataset_id
    ).first()
    if not version or not os.path.isfile(version.storage_path):
        raise HTTPException(status_code=404, detail="Dataset version file not found")

    file_format = version.file_format
    if not file_format:
        try:
            file_format = format_from_path(version.storage_path)
        except Exception:
            file_format = version.storage_path.lower().rsplit('.', 1)[-1]

    ext = file_format
    media_type = MEDIA_TYPES.get(file_format, "application/octet-stream")

    safe_name = re.sub(r'[^A-Za-z0-9_-]+', '_', dataset.name).strip('_') if dataset else f'dataset_{dataset_id}'
    filename = f"{safe_name}_v{version.version_number}.{ext}"

    return FileResponse(
        version.storage_path,
        media_type=media_type,
        filename=filename
    )

@router.get("/{dataset_id}/export")
async def export_dataset(dataset_id: int, format: str = Query("csv"), version_id: Optional[int] = Query(None), db: Session = Depends(get_db)):
    allowed = {"csv", "xlsx", "json", "pdf"}
    if format not in allowed:
        raise HTTPException(status_code=400, detail="format must be csv, xlsx, json, or pdf")
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    version = db.query(DatasetVersion).filter(DatasetVersion.dataset_id == dataset_id, DatasetVersion.id == version_id).first() if version_id else db.query(DatasetVersion).filter(DatasetVersion.dataset_id == dataset_id).order_by(DatasetVersion.version_number.desc()).first()
    if not version or not os.path.isfile(version.storage_path):
        raise HTTPException(status_code=404, detail="Dataset version file not found")
    # Use stored format metadata when available
    file_format = version.file_format
    if not file_format:
        try:
            file_format = format_from_path(version.storage_path)
        except Exception:
            file_format = version.storage_path.lower().rsplit('.', 1)[-1]

    metadata = version.format_metadata or capture_format_metadata(version.storage_path)

    if file_format == 'json':
        df = pd.read_json(version.storage_path, orient=metadata.get('orient', 'records'))
    elif file_format in {'xls', 'xlsx'}:
        df = pd.read_excel(version.storage_path, sheet_name=metadata.get('sheet_name', 0))
    else:
        df = pd.read_csv(
            version.storage_path,
            encoding=metadata.get('encoding', 'utf-8'),
            sep=metadata.get('delimiter', ','),
            quotechar=metadata.get('quotechar', '"')
        )
    output = BytesIO()
    if format == 'csv':
        output.write(df.to_csv(index=False).encode('utf-8-sig'))
        media = 'text/csv'
    elif format == 'json':
        output.write(df.to_json(orient='records', date_format='iso').encode('utf-8'))
        media = 'application/json'
    elif format == 'xlsx':
        df.to_excel(output, index=False)
        media = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    else:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib import colors
        doc = SimpleDocTemplate(output, pagesize=letter)
        rows = [list(df.columns)] + df.head(100).fillna('').astype(str).values.tolist()
        table = Table(rows, repeatRows=1)
        table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1769ff')), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white), ('GRID', (0, 0), (-1, -1), 0.25, colors.grey), ('FONTSIZE', (0, 0), (-1, -1), 7)]))
        doc.build([Paragraph(f'{dataset.name} — Version {version.version_number}', __import__('reportlab.lib.styles', fromlist=['getSampleStyleSheet']).getSampleStyleSheet()['Title']), Paragraph(f'{len(df)} rows × {len(df.columns)} columns. Report preview limited to 100 rows.', __import__('reportlab.lib.styles', fromlist=['getSampleStyleSheet']).getSampleStyleSheet()['Normal']), Spacer(1, 12), table])
        media = 'application/pdf'
    output.seek(0)
    safe_name = re.sub(r'[^A-Za-z0-9_-]+', '_', dataset.name).strip('_') or 'dataset'
    return StreamingResponse(output, media_type=media, headers={'Content-Disposition': f'attachment; filename="{safe_name}_v{version.version_number}.{format}"'})

@router.get("/{dataset_id}/versions/{version_id}/visualization-data")
async def get_dataset_visualization_data(
    dataset_id: int,
    version_id: int,
    db: Session = Depends(get_db)
):
    """Alias for visualization-data under datasets prefix"""
    from app.api.profiling import get_visualization_data
    return await get_visualization_data(dataset_id=dataset_id, version_id=version_id, db=db)


@router.get("/{dataset_id}/profile")
async def get_dataset_profile(
    dataset_id: int,
    version_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """Compatibility alias for the profiling API."""
    from app.api.profiling import get_dataset_profile as profiling_endpoint
    return await profiling_endpoint(dataset_id, version_id, db)

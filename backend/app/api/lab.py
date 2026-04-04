"""Lab asset management API endpoints"""

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.models.database import LabAsset, get_db
from app.models.schemas import LabAssetResponse
from app.services.lab_analyst import lab_analyst

router = APIRouter(prefix="/lab", tags=["lab"])


@router.post("/projects/{project_id}/upload", response_model=LabAssetResponse)
async def upload_lab_asset(
    project_id: str,
    file: UploadFile = File(...),
    name: str = Form(...),
    asset_type: str = Form(...),
    db: Session = Depends(get_db)
):
    """Upload and analyze a lab asset (image/CSV/code)
    
    For images, this triggers Gemini Vision analysis automatically.
    """
    
    # Validate asset type
    if asset_type not in ["image", "data", "code"]:
        raise HTTPException(status_code=400, detail="Invalid asset type")
    
    # Process asset using Lab Analyst
    lab_asset = await lab_analyst.ingest_lab_asset(
        project_id=project_id,
        file=file,
        asset_type=asset_type,
        name=name,
        db=db
    )
    
    return lab_asset


@router.get("/projects/{project_id}", response_model=List[LabAssetResponse])
async def list_lab_assets(
    project_id: str,
    db: Session = Depends(get_db)
):
    """Get all lab assets for a project"""
    
    assets = db.query(LabAsset).filter(
        LabAsset.project_id == project_id
    ).order_by(LabAsset.created_at.desc()).all()
    
    return assets


@router.post("/assets/{asset_id}/reanalyze")
async def reanalyze_asset(
    asset_id: str,
    custom_prompt: str = Form(None),
    db: Session = Depends(get_db)
):
    """Re-analyze an asset with optional custom prompt"""
    
    asset = db.query(LabAsset).filter(LabAsset.id == asset_id).first()
    
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    new_description = await lab_analyst.reanalyze_asset(
        asset=asset,
        custom_prompt=custom_prompt,
        db=db
    )
    
    return {
        "asset_id": asset_id,
        "ai_description": new_description
    }


@router.delete("/assets/{asset_id}")
async def delete_lab_asset(
    asset_id: str,
    db: Session = Depends(get_db)
):
    """Delete a lab asset"""
    
    asset = db.query(LabAsset).filter(LabAsset.id == asset_id).first()
    
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    # Delete file from disk
    from pathlib import Path
    file_path = Path(asset.file_path)
    if file_path.exists():
        file_path.unlink()
    
    # Delete from database
    db.delete(asset)
    db.commit()
    
    return {"message": "Asset deleted successfully"}

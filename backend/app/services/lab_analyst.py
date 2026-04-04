"""Lab Analyst Service - Multimodal asset processing with Gemini Vision"""

from pathlib import Path
from typing import Optional
import aiofiles
from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.ai_client import ai_client
from app.core.config import settings
from app.models.database import LabAsset


class LabAnalystService:
    """Service for processing and analyzing lab assets (images, CSV, code)"""
    
    @staticmethod
    async def save_upload(
        file: UploadFile,
        project_id: str
    ) -> Path:
        """Save uploaded file to disk"""
        
        # Create upload directory for project
        upload_dir = settings.upload_path / project_id / "lab"
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate unique filename
        file_path = upload_dir / file.filename
        
        # Handle duplicates
        counter = 1
        while file_path.exists():
            stem = Path(file.filename).stem
            suffix = Path(file.filename).suffix
            file_path = upload_dir / f"{stem}_{counter}{suffix}"
            counter += 1
        
        # Save file
        async with aiofiles.open(file_path, 'wb') as f:
            content = await file.read()
            await f.write(content)
        
        return file_path
    
    @staticmethod
    async def ingest_lab_asset(
        project_id: str,
        file: UploadFile,
        asset_type: str,
        name: str,
        db: Session
    ) -> LabAsset:
        """Process and analyze a lab asset
        
        Args:
            project_id: ID of the project
            file: Uploaded file
            asset_type: Type of asset ("image", "data", "code")
            name: Display name for the asset
            db: Database session
            
        Returns:
            Created LabAsset instance with AI description
        """
        
        # Save file to disk
        file_path = await LabAnalystService.save_upload(file, project_id)
        
        # Analyze if image
        ai_description: Optional[str] = None
        
        if asset_type == "image":
            ai_description = await ai_client.analyze_image(
                file_path,
                prompt="""Provide a detailed scientific description of this figure or chart.

Identify:
1. Type of visualization (line graph, bar chart, scatter plot, etc.)
2. Axes labels and units
3. Key trends or patterns
4. Notable data points or outliers
5. Any statistical significance markers

Format your response as a concise paragraph suitable for referencing in academic writing."""
            )
        
        elif asset_type == "data":
            # For CSV/data files, provide basic metadata
            ai_description = f"Data file: {name}. Contains tabular data suitable for analysis."
        
        # Create database record
        lab_asset = LabAsset(
            project_id=project_id,
            name=name,
            asset_type=asset_type,
            file_path=str(file_path),
            ai_description=ai_description,
            file_size=file_path.stat().st_size if file_path.exists() else None,
            mime_type=file.content_type
        )
        
        db.add(lab_asset)
        db.commit()
        db.refresh(lab_asset)
        
        return lab_asset
    
    @staticmethod
    async def reanalyze_asset(
        asset: LabAsset,
        custom_prompt: Optional[str] = None,
        db: Session = None
    ) -> str:
        """Re-analyze an existing asset with optional custom prompt"""
        
        if asset.asset_type != "image":
            return asset.ai_description or "Asset is not an image"
        
        prompt = custom_prompt or """Provide a detailed scientific description of this figure."""
        
        new_description = await ai_client.analyze_image(
            asset.file_path,
            prompt=prompt
        )
        
        # Update database
        if db:
            asset.ai_description = new_description
            db.commit()
        
        return new_description


# Global service instance
lab_analyst = LabAnalystService()

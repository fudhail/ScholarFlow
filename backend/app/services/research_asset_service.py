"""Research asset service for student-owned experimental artifacts."""

from pathlib import Path
from typing import Optional

import aiofiles
from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.ai_client import ai_client
from app.core.config import settings
from app.models.database import ResearchAsset


class ResearchAssetService:
    """Persist and lightly analyze research assets used for original paper writing."""

    @staticmethod
    async def save_upload(file: UploadFile, project_id: str) -> Path:
        upload_dir = settings.upload_path / project_id / "research"
        upload_dir.mkdir(parents=True, exist_ok=True)

        file_path = upload_dir / file.filename
        counter = 1
        while file_path.exists():
            stem = Path(file.filename).stem
            suffix = Path(file.filename).suffix
            file_path = upload_dir / f"{stem}_{counter}{suffix}"
            counter += 1

        async with aiofiles.open(file_path, "wb") as handle:
            content = await file.read()
            await handle.write(content)

        return file_path

    @staticmethod
    async def ingest_research_asset(
        project_id: str,
        file: UploadFile,
        asset_type: str,
        name: str,
        db: Session,
        description: Optional[str] = None,
        methodology_note: Optional[str] = None,
        section_hint: Optional[str] = None,
    ) -> ResearchAsset:
        file_path = await ResearchAssetService.save_upload(file, project_id)

        ai_analysis: Optional[str] = None
        if asset_type == "my_figure":
            ai_analysis = await ai_client.analyze_image(
                file_path,
                prompt="""Analyze this research figure as the student's own experimental result.

Identify:
1. What the figure appears to show
2. The key trend, comparison, or signal
3. Any visible outliers or notable observations
4. How it might support a Results or Discussion section

Respond as concise academic analysis that can support paper drafting."""
            )
        elif asset_type == "experiment_data":
            ai_analysis = f"Student-owned dataset '{name}' uploaded for original-results drafting."
        elif asset_type == "methodology":
            ai_analysis = f"Methodology artifact '{name}' uploaded to support methods writing."
        elif asset_type == "my_code":
            ai_analysis = f"Code artifact '{name}' uploaded to support reproducibility and methods description."
        elif asset_type == "my_table":
            ai_analysis = f"Table artifact '{name}' uploaded to support results presentation."

        asset = ResearchAsset(
            project_id=project_id,
            name=name,
            asset_type=asset_type,
            description=description,
            file_path=str(file_path),
            methodology_note=methodology_note,
            section_hint=section_hint,
            ai_analysis=ai_analysis,
            file_size=file_path.stat().st_size if file_path.exists() else None,
            mime_type=file.content_type,
        )

        db.add(asset)
        db.commit()
        db.refresh(asset)
        return asset


research_asset_service = ResearchAssetService()

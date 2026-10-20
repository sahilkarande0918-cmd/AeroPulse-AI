from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.common import Page, iso, paginate
from app.config import settings
from app.database import get_db
from app.models import IngestionBatch, User
from app.security import audit, require
from app.services import ingestion

router = APIRouter(tags=["ingestion"])
SAMPLES = Path(__file__).resolve().parents[3] / "data" / "samples"


def batch_out(b: IngestionBatch) -> dict:
    return {"id": b.id, "created_at": iso(b.created_at), "source_type": b.source_type, "source_name": b.source_name,
            "filename": b.filename, "mapping_version": b.mapping_version, "content_hash": b.content_hash,
            "accepted": b.accepted, "updated": b.updated, "duplicates": b.duplicates, "conflicts": b.conflicts,
            "rejected": b.rejected, "report": b.report}


@router.post("/ingestion/{source}", status_code=201)
async def ingest(source: str, file: UploadFile = File(...), source_name: str = Form("MANUAL-UPLOAD", max_length=64,
                                                                                   pattern=r"^[A-Za-z0-9_\-]+$"),
                 db: Session = Depends(get_db), user: User = Depends(require("ingest"))):
    if source not in ingestion.SOURCE_TYPES:
        raise HTTPException(404, f"Unknown source type. Use one of {list(ingestion.SOURCE_TYPES)}")
    name = Path(file.filename or "upload").name
    if not name.lower().endswith((".csv", ".json")):
        raise HTTPException(422, "Only .csv and .json files are accepted")
    content = await file.read(settings.max_upload_bytes + 1)
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(413, f"File exceeds {settings.max_upload_bytes} bytes")
    batch, already = ingestion.ingest(db, source, name, content, source_name, user.id)
    if not already:
        audit(db, user.username, "ingestion.import", "ingestion_batch", batch.id,
              {k: getattr(batch, k) for k in ("source_type", "source_name", "filename", "accepted", "updated",
                                              "duplicates", "conflicts", "rejected", "content_hash")})
    db.commit()
    return {**batch_out(batch), "already_imported": already}


@router.get("/ingestion/batches")
def list_batches(page: Page = Depends(), db: Session = Depends(get_db), _: User = Depends(require("read"))):
    return paginate(db, select(IngestionBatch).order_by(IngestionBatch.id.desc()), page, batch_out)


@router.get("/ingestion/mapping")
def mapping(_: User = Depends(require("read"))):
    return ingestion.MAPPING


@router.get("/ingestion/samples")
def list_samples(_: User = Depends(require("read"))):
    return {"items": sorted(p.name for p in SAMPLES.glob("*") if p.suffix in (".csv", ".json"))}


@router.get("/ingestion/samples/{name}")
def sample(name: str, _: User = Depends(require("read"))):
    p = (SAMPLES / name).resolve()
    if p.parent != SAMPLES.resolve() or not p.is_file():
        raise HTTPException(404, "Sample not found")
    return FileResponse(p, filename=p.name)

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.common import iso
from app.database import get_db
from app.models import Part, User, WorkOrder
from app.security import audit, require

router = APIRouter(tags=["parts"])


def parts_view(db: Session) -> list[dict]:
    """Inventory with reserved stock derived from open, non-rejected work orders (never stored separately)."""
    wos = db.scalars(select(WorkOrder).where(WorkOrder.status.in_(("open", "scheduled", "in_progress")),
                                             WorkOrder.approval_state != "rejected")).all()
    out = []
    for p in db.scalars(select(Part).order_by(Part.part_number)):
        users = [(w, x["qty"]) for w in wos for x in w.parts if x["part_number"] == p.part_number]
        reserved = sum(q for _, q in users)
        available = p.on_hand - reserved
        out.append({
            "part_number": p.part_number, "name": p.name, "unit": p.unit, "on_hand": p.on_hand, "reserved": reserved,
            "available": available, "reorder_threshold": p.reorder_threshold, "replenishment_qty": p.replenishment_qty,
            "replenishment_eta": iso(p.replenishment_eta), "lead_time_days": p.lead_time_days,
            "shortage": available < 0, "below_reorder": p.on_hand < p.reorder_threshold,
            "affected_work_orders": [{"code": w.code, "aircraft": w.aircraft.tail, "title": w.title, "qty": q,
                                      "approval_state": w.approval_state} for w, q in users],
        })
    return out


class PartPatch(BaseModel):
    on_hand: int | None = Field(None, ge=0, le=100000)
    reorder_threshold: int | None = Field(None, ge=0, le=100000)
    replenishment_qty: int | None = Field(None, ge=0, le=100000)
    replenishment_eta: datetime | None = None
    clear_replenishment: bool = False
    reason: str = Field(min_length=3, max_length=500)


@router.get("/parts")
def list_parts(db: Session = Depends(get_db), _: User = Depends(require("read"))):
    items = parts_view(db)
    return {"items": items, "total": len(items), "limit": len(items), "offset": 0}


@router.patch("/parts/{part_number}")
def update_part(part_number: str, body: PartPatch, db: Session = Depends(get_db),
                user: User = Depends(require("inventory:write"))):
    p = db.scalar(select(Part).where(Part.part_number == part_number))
    if not p:
        raise HTTPException(404, "Part not found")
    if body.replenishment_eta and body.replenishment_eta.tzinfo is None:
        raise HTTPException(422, "replenishment_eta must include a timezone offset")
    before = {"on_hand": p.on_hand, "reorder_threshold": p.reorder_threshold, "replenishment_qty": p.replenishment_qty,
              "replenishment_eta": iso(p.replenishment_eta)}
    for k in ("on_hand", "reorder_threshold", "replenishment_qty", "replenishment_eta"):
        v = getattr(body, k)
        if v is not None:
            setattr(p, k, v)
    if body.clear_replenishment:
        p.replenishment_eta, p.replenishment_qty = None, 0
    audit(db, user.username, "inventory.update", "part", p.part_number,
          {"before": before, "after": {k: (iso(getattr(p, k)) if k.endswith("eta") else getattr(p, k)) for k in before},
           "reason": body.reason})
    db.commit()
    return next(x for x in parts_view(db) if x["part_number"] == p.part_number)

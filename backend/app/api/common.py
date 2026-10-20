from fastapi import Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session


class Page:
    def __init__(self, limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0)):
        self.limit, self.offset = limit, offset


def paginate(db: Session, stmt, page: Page, serialize) -> dict:
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    items = db.scalars(stmt.limit(page.limit).offset(page.offset)).all()
    return {"items": [serialize(i) for i in items], "total": total, "limit": page.limit, "offset": page.offset}


def iso(dt):
    return dt.isoformat() if dt else None

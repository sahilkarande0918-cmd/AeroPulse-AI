"""Local demo authentication (bcrypt + JWT), backend-enforced role permissions, audit hash chain.

Production path: replace /api/auth/login with the organisation's OIDC provider and map its
group claims to the same roles; `require()` stays unchanged.
"""
import hashlib
import json
import time
from collections import defaultdict, deque
from datetime import timedelta

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db, utcnow
from app.models import AuditEvent, User

ROLES = ("admin", "officer", "technician", "analyst")
PERMISSIONS = {
    "read": {"admin", "officer", "technician", "analyst"},
    "audit:read": {"admin", "officer", "analyst"},
    "ingest": {"admin", "officer"},
    "inventory:write": {"admin", "officer"},
    "plan": {"admin", "officer"},
    "approve": {"admin", "officer"},
    "scenario:run": {"admin", "officer", "analyst"},
    "workorder:progress": {"admin", "officer", "technician"},
    "admin": {"admin"},
}

bearer = HTTPBearer(auto_error=False)


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_password(pw: str, hashed: str) -> bool:
    return bcrypt.checkpw(pw.encode(), hashed.encode())


def create_token(user: User) -> str:
    payload = {"sub": user.username, "role": user.role, "exp": utcnow() + timedelta(minutes=settings.jwt_expire_minutes)}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")


def current_user(cred: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if cred is None:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = jwt.decode(cred.credentials, settings.jwt_secret_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid or expired token") from None
    user = db.scalar(select(User).where(User.username == payload.get("sub")))
    if not user or not user.active:
        raise HTTPException(401, "User inactive or unknown")
    return user


def require(permission: str):
    def dep(user: User = Depends(current_user)) -> User:
        if user.role not in PERMISSIONS[permission]:
            raise HTTPException(403, f"Role '{user.role}' lacks permission '{permission}'")
        return user
    return dep


# ponytail: in-process sliding window, per instance; move to a shared store if running several replicas.
_attempts: dict[str, deque] = defaultdict(deque)


def rate_limit_login(request: Request, username: str, limit: int = 10, window_s: int = 300):
    key = f"{request.client.host if request.client else '?'}:{username}"
    q, now = _attempts[key], time.monotonic()
    while q and now - q[0] > window_s:
        q.popleft()
    if len(q) >= limit:
        raise HTTPException(429, "Too many login attempts; try again later")
    q.append(now)


def audit(db: Session, actor: str, action: str, entity_type: str, entity_id, details: dict | None = None) -> AuditEvent:
    """Append an audit event chained to the previous one by SHA-256 (tamper-evident, not tamper-proof)."""
    prev = db.scalar(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(1))
    prev_hash = prev.hash if prev else "0" * 64
    ts = utcnow()
    body = json.dumps({"ts": ts.isoformat(), "actor": actor, "action": action, "entity_type": entity_type,
                       "entity_id": str(entity_id), "details": details or {}}, sort_keys=True, default=str)
    ev = AuditEvent(created_at=ts, actor=actor, action=action, entity_type=entity_type, entity_id=str(entity_id),
                    details=json.loads(body)["details"], prev_hash=prev_hash,
                    hash=hashlib.sha256((prev_hash + body).encode()).hexdigest())
    db.add(ev)
    db.flush()
    return ev


def verify_audit_chain(db: Session) -> dict:
    prev = "0" * 64
    n = 0
    for ev in db.scalars(select(AuditEvent).order_by(AuditEvent.id)):
        body = json.dumps({"ts": ev.created_at.isoformat(), "actor": ev.actor, "action": ev.action,
                           "entity_type": ev.entity_type, "entity_id": ev.entity_id, "details": ev.details},
                          sort_keys=True, default=str)
        if ev.prev_hash != prev or ev.hash != hashlib.sha256((prev + body).encode()).hexdigest():
            return {"valid": False, "events_checked": n, "first_invalid_id": ev.id}
        prev, n = ev.hash, n + 1
    return {"valid": True, "events_checked": n, "first_invalid_id": None}

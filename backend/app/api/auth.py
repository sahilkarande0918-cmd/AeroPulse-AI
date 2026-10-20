from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User
from app.security import PERMISSIONS, audit, create_token, current_user, rate_limit_login, verify_password

router = APIRouter(tags=["auth"])


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


def user_out(u: User) -> dict:
    return {"username": u.username, "full_name": u.full_name, "role": u.role,
            "permissions": sorted(p for p, roles in PERMISSIONS.items() if u.role in roles)}


@router.post("/auth/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    if settings.auth_mode == "oidc":
        raise HTTPException(404, "Local login is disabled; sign in through the organisation's SSO")
    rate_limit_login(request, body.username)
    user = db.scalar(select(User).where(User.username == body.username))
    if not user or not user.active or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid username or password")
    audit(db, user.username, "login", "user", user.id)
    db.commit()
    return {"access_token": create_token(user), "token_type": "bearer", "user": user_out(user)}


@router.get("/auth/me")
def me(user: User = Depends(current_user)):
    return user_out(user)

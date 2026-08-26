"""Authentication dependency for FastAPI — token-based auth."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.db import get_db
from app.models import User, UserRole

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> User:
    """Extract and validate the Bearer token, return the authenticated user."""
    token = credentials.credentials
    db = get_db()

    row = db.execute(
        "SELECT id, family_id, name, role, token FROM users WHERE token = ?",
        (token,),
    ).fetchone()

    if not row:
        raise HTTPException(status_code=401, detail="Invalid token")

    return User(
        id=row["id"],
        family_id=row["family_id"],
        name=row["name"],
        role=UserRole(row["role"]),
        token=row["token"],
    )


def require_parent(user: User = Depends(get_current_user)) -> User:
    """Dependency that requires the user to be a parent."""
    if user.role != UserRole.PARENT:
        raise HTTPException(status_code=403, detail="Forbidden: requires role parent")
    return user


def require_child(user: User = Depends(get_current_user)) -> User:
    """Dependency that requires the user to be a child."""
    if user.role != UserRole.CHILD:
        raise HTTPException(status_code=403, detail="Forbidden: requires role child")
    return user

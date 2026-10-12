from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from db import get_db
from deps import current_user, CLIENT
from models import User
from schemas import LoginIn, RegisterIn
from security import create_token, hash_password, throttle, verify_password
from audit import audit

router = APIRouter(prefix="/api/auth", tags=["auth"])


def user_out(u: User):
    return {"id": u.id, "name": u.name, "email": u.email, "role": u.role, "phone": u.phone,
            "sites": [{"id": s.id, "name": s.name} for s in u.sites]}


@router.post("/login")
def login(data: LoginIn, request: Request, db: Session = Depends(get_db)):
    key = f"{request.client.host if request.client else 'x'}:{data.email.lower()}"
    if not throttle(key):
        raise HTTPException(429, "Too many login attempts. Try again in a few minutes.")
    u = db.scalar(select(User).where(User.email == data.email.lower()))
    if not u or not u.is_active or not verify_password(data.password, u.password_hash):
        raise HTTPException(401, "Incorrect email or password")
    return {"access_token": create_token(u.id), "token_type": "bearer", "user": user_out(u)}


@router.post("/register", status_code=201)
def register(data: RegisterIn, db: Session = Depends(get_db)):
    """Self-registration creates CLIENT accounts only. Site access is granted by an admin."""
    if db.scalar(select(User).where(User.email == data.email.lower())):
        raise HTTPException(409, "An account with this email already exists")
    u = User(name=data.name, email=data.email.lower(), phone=data.phone, password_hash=hash_password(data.password), role=CLIENT)
    db.add(u)
    db.flush()
    audit(db, u, "register", "user", u.id)
    db.commit()
    return user_out(u)


@router.get("/me")
def me(user: User = Depends(current_user)):
    return user_out(user)

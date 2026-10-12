from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from db import get_db
from models import User
from security import decode_token

bearer = HTTPBearer(auto_error=False)
ADMIN, MGMT, FM, TECH, CLIENT = "super_admin", "management", "facility_manager", "technician", "client"
ROLES = [ADMIN, MGMT, FM, TECH, CLIENT]


def current_user(cred: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if not cred:
        raise HTTPException(401, "Not authenticated")
    try:
        uid = decode_token(cred.credentials)
    except Exception:
        raise HTTPException(401, "Invalid or expired token")
    user = db.get(User, uid)
    if not user or not user.is_active:
        raise HTTPException(401, "Account disabled or not found")
    return user


def require(*roles):
    def dep(user: User = Depends(current_user)):
        if user.role not in roles:
            raise HTTPException(403, "You do not have permission for this action")
        return user
    return dep


def user_site_ids(user: User) -> list:
    return [s.id for s in user.sites]

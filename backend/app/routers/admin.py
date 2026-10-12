from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from audit import audit
from db import get_db
from deps import ADMIN, CLIENT, FM, MGMT, ROLES, TECH, current_user, require, user_site_ids
from models import Building, Category, Floor, Region, Site, Tower, User
from schemas import BuildingIn, CategoryIn, FloorIn, SiteIn, TowerIn, UserCreate, UserPatch
from security import hash_password
from schemas import UserOut

router = APIRouter(prefix="/api", tags=["admin"])


def _site_filter(user: User):
    if user.role == ADMIN:
        return None
    ids = user_site_ids(user)
    if user.role == MGMT and not ids:
        return None
    return ids


@router.get("/sites")
def list_sites(user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = select(Site).where(Site.is_active == True)  # noqa: E712
    ids = _site_filter(user)
    if ids is not None:
        q = q.where(Site.id.in_(ids or [-1]))
    return [{"id": s.id, "name": s.name, "code": s.code, "region": s.region.name} for s in db.scalars(q.order_by(Site.name))]


@router.get("/sites/{site_id}/structure")
def structure(site_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ids = _site_filter(user)
    if ids is not None and site_id not in ids:
        raise HTTPException(403, "No access to this site")
    out = []
    for b in db.scalars(select(Building).where(Building.site_id == site_id).order_by(Building.name)):
        out.append({
            "id": b.id, "name": b.name,
            "towers": [{"id": t.id, "name": t.name} for t in db.scalars(select(Tower).where(Tower.building_id == b.id))],
            "floors": [{"id": f.id, "name": f.name, "tower_id": f.tower_id} for f in db.scalars(select(Floor).where(Floor.building_id == b.id))],
        })
    return out


@router.post("/sites", status_code=201)
def create_site(data: SiteIn, user: User = Depends(require(ADMIN)), db: Session = Depends(get_db)):
    if db.scalar(select(Site).where(Site.code == data.code)):
        raise HTTPException(409, "Site code already exists")
    region = db.scalar(select(Region).where(Region.name == data.region)) or Region(name=data.region)
    db.add(region)
    db.flush()
    s = Site(region_id=region.id, name=data.name, code=data.code, address=data.address)
    db.add(s)
    db.flush()
    audit(db, user, "create", "site", s.id, data.name)
    db.commit()
    return {"id": s.id}


@router.post("/buildings", status_code=201)
def create_building(data: BuildingIn, user: User = Depends(require(ADMIN)), db: Session = Depends(get_db)):
    if not db.get(Site, data.site_id):
        raise HTTPException(404, "Site not found")
    b = Building(site_id=data.site_id, name=data.name)
    db.add(b); db.flush(); audit(db, user, "create", "building", b.id, data.name); db.commit()
    return {"id": b.id}


@router.post("/towers", status_code=201)
def create_tower(data: TowerIn, user: User = Depends(require(ADMIN)), db: Session = Depends(get_db)):
    if not db.get(Building, data.building_id):
        raise HTTPException(404, "Building not found")
    t = Tower(building_id=data.building_id, name=data.name)
    db.add(t); db.flush(); audit(db, user, "create", "tower", t.id, data.name); db.commit()
    return {"id": t.id}


@router.post("/floors", status_code=201)
def create_floor(data: FloorIn, user: User = Depends(require(ADMIN)), db: Session = Depends(get_db)):
    if not db.get(Building, data.building_id):
        raise HTTPException(404, "Building not found")
    f = Floor(building_id=data.building_id, tower_id=data.tower_id, name=data.name)
    db.add(f); db.flush(); audit(db, user, "create", "floor", f.id, data.name); db.commit()
    return {"id": f.id}


@router.get("/categories")
def categories(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [{"id": c.id, "name": c.name, "default_priority": c.default_priority, "team": c.team}
            for c in db.scalars(select(Category).where(Category.is_active == True).order_by(Category.name))]  # noqa: E712


@router.post("/categories", status_code=201)
def create_category(data: CategoryIn, user: User = Depends(require(ADMIN)), db: Session = Depends(get_db)):
    if data.default_priority not in ("Critical", "High", "Medium", "Low"):
        raise HTTPException(422, "Invalid priority")
    c = Category(**data.model_dump())
    db.add(c); db.flush(); audit(db, user, "create", "category", c.id, data.name); db.commit()
    return {"id": c.id}


@router.get("/users")
def list_users(role: str | None = None, user: User = Depends(require(ADMIN, MGMT, FM)), db: Session = Depends(get_db)):
    q = select(User).order_by(User.name)
    if role:
        q = q.where(User.role == role)
    users = list(db.scalars(q))
    if user.role == FM:  # facility managers only see staff sharing their sites
        mine = set(user_site_ids(user))
        users = [u for u in users if u.role in (TECH, FM) and mine & set(user_site_ids(u))]
    return [{**user_out(u), "is_active": u.is_active} for u in users]


@router.post("/users", status_code=201)
def create_user(data: UserCreate, admin: User = Depends(require(ADMIN)), db: Session = Depends(get_db)):
    if data.role not in ROLES:
        raise HTTPException(422, "Invalid role")
    if db.scalar(select(User).where(User.email == data.email.lower())):
        raise HTTPException(409, "Email already in use")
    u = User(name=data.name, email=data.email.lower(), phone=data.phone, role=data.role, password_hash=hash_password(data.password))
    u.sites = list(db.scalars(select(Site).where(Site.id.in_(data.site_ids)))) if data.site_ids else []
    db.add(u); db.flush(); audit(db, admin, "create", "user", u.id, data.role); db.commit()
    return user_out(u)


@router.patch("/users/{uid}")
def patch_user(uid: int, data: UserPatch, admin: User = Depends(require(ADMIN)), db: Session = Depends(get_db)):
    u = db.get(User, uid)
    if not u:
        raise HTTPException(404, "User not found")
    if data.is_active is not None:
        if u.id == admin.id and not data.is_active:
            raise HTTPException(400, "You cannot deactivate yourself")
        u.is_active = data.is_active
    if data.role:
        if data.role not in ROLES:
            raise HTTPException(422, "Invalid role")
        u.role = data.role
    if data.site_ids is not None:
        u.sites = list(db.scalars(select(Site).where(Site.id.in_(data.site_ids))))
    audit(db, admin, "update", "user", u.id, data.model_dump_json())
    db.commit()
    return user_out(u)

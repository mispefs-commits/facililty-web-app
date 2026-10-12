"""Demo data for LOCAL DEVELOPMENT ONLY. Enabled by SEED_DEMO=true."""
from sqlalchemy import select
from .config import settings
from .models import Building, Category, Floor, Region, Site, Tower, User
from .security import hash_password

CATEGORIES = [("HVAC / Air Conditioning", "Medium", "HVAC Team"), ("Electrical", "High", "Electrical Team"),
              ("Plumbing", "Medium", "Plumbing Team"), ("Housekeeping", "Low", "Housekeeping"),
              ("Lifts", "High", "Lift Vendor"), ("Fire & Safety", "Critical", "Safety Team"),
              ("Civil / Carpentry", "Low", "Civil Team"), ("IT / Network", "Medium", "IT Support")]


def seed_demo(db):
    if db.scalar(select(User).limit(1)):
        return
    hyd = Region(name="Hyderabad"); blr = Region(name="Bengaluru")
    db.add_all([hyd, blr]); db.flush()
    s1 = Site(region_id=hyd.id, name="Hitech City Campus", code="HYD-HC", address="Hitech City, Hyderabad")
    s2 = Site(region_id=hyd.id, name="Gachibowli Tech Park", code="HYD-GB", address="Gachibowli, Hyderabad")
    s3 = Site(region_id=blr.id, name="Whitefield Tower", code="BLR-WF", address="Whitefield, Bengaluru")
    db.add_all([s1, s2, s3]); db.flush()
    for s in (s1, s2, s3):
        b = Building(site_id=s.id, name="Main Building"); db.add(b); db.flush()
        t1 = Tower(building_id=b.id, name="Tower A"); t2 = Tower(building_id=b.id, name="Tower B"); db.add_all([t1, t2]); db.flush()
        for t in (t1, t2):
            for n in ("Ground", "1st Floor", "2nd Floor", "3rd Floor"):
                db.add(Floor(building_id=b.id, tower_id=t.id, name=n))
    db.add_all([Category(name=n, default_priority=p, team=t) for n, p, t in CATEGORIES])
    pw = hash_password(settings.demo_password)

    def u(name, email, role, sites):
        user = User(name=name, email=email, role=role, password_hash=pw); user.sites = sites; db.add(user)
    u("Super Admin", "admin@example.com", "super_admin", [])
    u("Regional Manager", "manager@example.com", "management", [s1, s2, s3])
    u("Hitech FM", "fm@example.com", "facility_manager", [s1])
    u("Ravi Technician", "tech@example.com", "technician", [s1])
    u("Client Occupant", "client@example.com", "client", [s1])
    db.commit()

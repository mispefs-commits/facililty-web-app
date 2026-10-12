"""Secure first-admin creation:  python -m app.create_admin
Prompts for the password (not echoed); nothing is stored in code or env files."""
import getpass, sys
from sqlalchemy import select
from .db import Base, SessionLocal, engine
from .models import User
from .security import check_password_strength, hash_password

Base.metadata.create_all(engine)
email = input("Admin email: ").strip().lower()
name = input("Admin name: ").strip() or "Administrator"
pw = getpass.getpass("Password: ")
if pw != getpass.getpass("Confirm password: "):
    sys.exit("Passwords do not match")
try:
    check_password_strength(pw)
except ValueError as e:
    sys.exit(str(e))
with SessionLocal() as db:
    if db.scalar(select(User).where(User.email == email)):
        sys.exit("User already exists")
    db.add(User(name=name, email=email, role="super_admin", password_hash=hash_password(pw)))
    db.commit()
print("Super admin created.")

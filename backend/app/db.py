from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from config import settings

kwargs = (
    {"connect_args": {"check_same_thread": False}}
    if settings.database_url.startswith("sqlite")
    else {"pool_size": 20, "max_overflow": 30, "pool_pre_ping": True}
)
engine = create_engine(settings.database_url, **kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

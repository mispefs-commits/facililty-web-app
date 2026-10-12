import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from db import Base, SessionLocal, engine
from routers import admin, auth, chat, dashboard, tickets


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)  # dev convenience; use Alembic migrations in production (see README)
    os.makedirs(settings.upload_dir, exist_ok=True)
    if settings.seed_demo:
        from .seed import seed_demo
        with SessionLocal() as db:
            seed_demo(db)
    yield


app = FastAPI(title="Facility Management Helpdesk API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
for r in (auth.router, admin.router, tickets.router, dashboard.router, chat.router):
    app.include_router(r)


@app.get("/api/health")
def health():
    return {"status": "ok"}

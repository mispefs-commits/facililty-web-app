from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session
from ..db import get_db
from ..deps import current_user, ADMIN, MGMT, FM, TECH, CLIENT
from ..models import Feedback, Site, Ticket, User
from .tickets import scoped

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])
OPEN = ("New", "Acknowledged", "Assigned", "In Progress", "On Hold", "Pending Vendor", "Pending Client", "Escalated", "Reopened")


@router.get("/summary")
def summary(user: User = Depends(current_user), db: Session = Depends(get_db)):
    sub = scoped(user).subquery()
    by_status = {s: n for s, n in db.execute(select(sub.c.status, func.count()).group_by(sub.c.status))}
    by_priority = {p: n for p, n in db.execute(select(sub.c.priority, func.count()).where(sub.c.status.in_(OPEN)).group_by(sub.c.priority))}
    total = sum(by_status.values())
    open_n = sum(n for s, n in by_status.items() if s in OPEN)
    rating = db.scalar(select(func.avg(Feedback.rating)).where(Feedback.ticket_id.in_(select(sub.c.id))))
    out = {
        "role": user.role, "total": total, "open": open_n,
        "closed": by_status.get("Closed", 0) + by_status.get("Resolved", 0),
        "needs_acknowledgement": by_status.get("New", 0), "in_progress": by_status.get("In Progress", 0),
        "reopened": by_status.get("Reopened", 0), "escalated": by_status.get("Escalated", 0),
        "by_status": by_status, "open_by_priority": by_priority,
        "avg_rating": round(float(rating), 2) if rating else None,
    }
    if user.role in (ADMIN, MGMT, FM):
        rows = db.execute(select(Site.name, func.count(), func.sum(case((sub.c.status.in_(OPEN), 1), else_=0)))
                          .join(sub, sub.c.site_id == Site.id).group_by(Site.name))
        out["by_site"] = [{"site": n, "total": t, "open": int(o or 0)} for n, t, o in rows]
    return out

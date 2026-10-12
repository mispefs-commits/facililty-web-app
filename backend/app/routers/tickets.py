import os
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import or_, select, func
from sqlalchemy.orm import Session
from ..audit import audit
from ..config import settings
from ..db import get_db
from ..deps import ADMIN, CLIENT, FM, MGMT, TECH, current_user, user_site_ids
from ..models import (Attachment, Building, Category, Comment, Feedback, Floor, Site, Ticket,
                      TicketHistory, Tower, User)
from ..schemas import (AssignIn, CommentIn, FeedbackIn, PriorityIn, ReopenIn, StatusIn, TicketIn)
from ..utils import normalize_phone, wa_link

router = APIRouter(prefix="/api", tags=["tickets"])

PRIORITIES = ["Critical", "High", "Medium", "Low"]
STAFF = (ADMIN, FM, TECH)
STAFF_STATUS = ["Acknowledged", "In Progress", "On Hold", "Pending Vendor", "Pending Client", "Resolved", "Escalated", "Closed"]
TECH_STATUS = ["Acknowledged", "In Progress", "On Hold", "Pending Vendor", "Pending Client", "Resolved", "Escalated"]
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
PHOTO_KINDS = ("before", "during", "after")
ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".pdf", ".docx", ".xlsx", ".txt"}
ALLOWED_MIME_PREFIX = ("image/", "application/pdf", "application/vnd.openxmlformats", "text/plain", "application/octet-stream")


def now():
    return datetime.now(timezone.utc)


def scoped(user: User):
    q = select(Ticket)
    if user.role == ADMIN:
        return q
    if user.role == MGMT:
        ids = user_site_ids(user)
        return q.where(Ticket.site_id.in_(ids)) if ids else q
    if user.role == FM:
        return q.where(Ticket.site_id.in_(user_site_ids(user) or [-1]))
    if user.role == TECH:
        return q.where(Ticket.assigned_to_id == user.id)
    return q.where(Ticket.requester_id == user.id)


def get_ticket(db: Session, user: User, tid: int) -> Ticket:
    t = db.scalar(scoped(user).where(Ticket.id == tid))
    if not t:  # 404 for both missing and out-of-scope so ticket existence is not leaked
        raise HTTPException(404, "Ticket not found")
    return t


def log(db, t, actor, action, frm="", to="", note=""):
    db.add(TicketHistory(ticket_id=t.id, actor_id=actor.id, action=action, from_status=frm, to_status=to, note=note))


def ticket_out(t: Ticket):
    return {
        "id": t.id, "number": t.number, "subject": t.subject, "description": t.description,
        "status": t.status, "priority": t.priority, "source": t.source,
        "site": {"id": t.site_id, "name": t.site.name}, "building": {"id": t.building_id, "name": t.building.name},
        "tower": t.tower.name if t.tower else None, "floor": t.floor.name if t.floor else None,
        "location": t.location, "asset_id": t.asset_id,
        "category": {"id": t.category_id, "name": t.category.name},
        "requester": {"id": t.requester_id, "name": t.requester.name},
        "assignee": {"id": t.assigned_to_id, "name": t.assignee.name} if t.assignee else None,
        "client_name": t.client_name, "rep_name": t.rep_name, "rep_phone": t.rep_phone,
        "rep_whatsapp": t.rep_whatsapp, "wa_link": wa_link(t.rep_whatsapp),
        "root_cause": t.root_cause, "corrective_action": t.corrective_action, "closure_remarks": t.closure_remarks,
        "created_at": t.created_at, "updated_at": t.updated_at, "acknowledged_at": t.acknowledged_at,
        "work_started_at": t.work_started_at, "resolved_at": t.resolved_at, "closed_at": t.closed_at,
    }


def make_ticket(db: Session, user: User, data: TicketIn, source: str = "Web Portal", priority_override: str | None = None) -> Ticket:
    """Validates and creates a ticket (flush only; caller commits). Shared by the web form and the chatbot."""
    if user.role == TECH:
        raise HTTPException(403, "Technicians cannot raise tickets")
    if user.role != ADMIN and data.site_id not in user_site_ids(user):
        raise HTTPException(403, "You are not authorised to raise tickets at this site")
    site = db.get(Site, data.site_id)
    if not site or not site.is_active:
        raise HTTPException(404, "Site not found or inactive")
    b = db.get(Building, data.building_id)
    if not b or b.site_id != site.id:
        raise HTTPException(422, "Building does not belong to the selected site")
    if data.tower_id:
        tw = db.get(Tower, data.tower_id)
        if not tw or tw.building_id != b.id:
            raise HTTPException(422, "Tower does not belong to the selected building")
    if data.floor_id:
        fl = db.get(Floor, data.floor_id)
        if not fl or fl.building_id != b.id:
            raise HTTPException(422, "Floor does not belong to the selected building")
    cat = db.get(Category, data.category_id)
    if not cat or not cat.is_active:
        raise HTTPException(422, "Invalid category")
    rep_name = data.rep_name.strip()
    phone, wa = normalize_phone(data.rep_phone), normalize_phone(data.rep_whatsapp)
    if not rep_name or not phone or not wa:
        raise HTTPException(422, "Representative name, a valid phone number and a valid WhatsApp number are required")
    priority = priority_override or (data.priority if (data.priority and user.role in (ADMIN, FM)) else cat.default_priority)
    if priority not in PRIORITIES:
        raise HTTPException(422, "Invalid priority")
    t = Ticket(number=f"TMP-{uuid.uuid4().hex[:12]}", requester_id=user.id, site_id=site.id, building_id=b.id,
               tower_id=data.tower_id, floor_id=data.floor_id, location=data.location, asset_id=data.asset_id,
               category_id=cat.id, subject=data.subject, description=data.description, priority=priority,
               status="New", source=source, client_name=data.client_name.strip(), rep_name=rep_name,
               rep_phone=phone, rep_whatsapp=wa)
    db.add(t)
    db.flush()
    t.number = f"TKT-{now().year}-{t.id:06d}"
    log(db, t, user, "created", "", "New", f"Ticket raised via {source}")
    return t


@router.post("/tickets", status_code=201)
def create_ticket(data: TicketIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    t = make_ticket(db, user, data, source="Admin" if user.role == ADMIN else "Web Portal")
    db.commit()
    db.refresh(t)
    return ticket_out(t)


@router.get("/tickets")
def list_tickets(status: str | None = None, priority: str | None = None, site_id: int | None = None,
                 building_id: int | None = None, category_id: int | None = None, assignee_id: int | None = None,
                 q: str | None = None, page: int = 1, page_size: int = 20,
                 user: User = Depends(current_user), db: Session = Depends(get_db)):
    page_size = min(max(page_size, 1), 100)
    query = scoped(user)
    for col, val in ((Ticket.status, status), (Ticket.priority, priority), (Ticket.site_id, site_id),
                     (Ticket.building_id, building_id), (Ticket.category_id, category_id), (Ticket.assigned_to_id, assignee_id)):
        if val is not None:
            query = query.where(col == val)
    if q:
        like = f"%{q}%"
        query = query.where(or_(Ticket.number.ilike(like), Ticket.subject.ilike(like), Ticket.location.ilike(like),
                                Ticket.asset_id.ilike(like), Ticket.description.ilike(like)))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(query.order_by(Ticket.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"total": total, "page": page, "page_size": page_size, "items": [ticket_out(t) for t in rows]}


@router.get("/tickets/{tid}")
def ticket_detail(tid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    t = get_ticket(db, user, tid)
    comments = db.scalars(select(Comment).where(Comment.ticket_id == t.id).order_by(Comment.created_at)).all()
    if user.role == CLIENT:
        comments = [c for c in comments if not c.internal]
    hist = db.scalars(select(TicketHistory).where(TicketHistory.ticket_id == t.id).order_by(TicketHistory.created_at, TicketHistory.id)).all()
    atts = db.scalars(select(Attachment).where(Attachment.ticket_id == t.id).order_by(Attachment.created_at)).all()
    fb = db.scalar(select(Feedback).where(Feedback.ticket_id == t.id))
    return {
        **ticket_out(t),
        "comments": [{"id": c.id, "author": c.author.name, "role": c.author.role, "body": c.body, "internal": c.internal, "created_at": c.created_at} for c in comments],
        "history": [{"id": h.id, "actor": h.actor.name if h.actor else "System", "action": h.action, "from_status": h.from_status,
                     "to_status": h.to_status, "note": h.note, "created_at": h.created_at} for h in hist],
        "attachments": [{"id": a.id, "filename": a.filename, "kind": a.kind, "size": a.size, "content_type": a.content_type, "created_at": a.created_at} for a in atts],
        "feedback": {"rating": fb.rating, "comment": fb.comment} if fb else None,
    }


@router.post("/tickets/{tid}/assign")
def assign(tid: int, data: AssignIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role not in (ADMIN, FM):
        raise HTTPException(403, "Only facility managers or admins can assign tickets")
    t = get_ticket(db, user, tid)
    if t.status == "Closed":
        raise HTTPException(409, "Closed tickets must be reopened before assignment")
    a = db.get(User, data.assignee_id)
    if not a or not a.is_active or a.role not in (TECH, FM):
        raise HTTPException(422, "Assignee must be an active technician or facility manager")
    if t.site_id not in user_site_ids(a):
        raise HTTPException(422, "Assignee is not assigned to this ticket's site")
    old = t.status
    t.assigned_to_id = a.id
    if t.status in ("New", "Acknowledged", "Escalated"):
        t.status = "Assigned"
    t.acknowledged_at = t.acknowledged_at or now()
    log(db, t, user, "assigned", old, t.status, f"Assigned to {a.name}. {data.note}".strip())
    db.commit()
    return ticket_out(t)


@router.post("/tickets/{tid}/status")
def change_status(tid: int, data: StatusIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    t = get_ticket(db, user, tid)
    new, old = data.status, t.status
    if user.role == CLIENT:
        if not (new == "Closed" and old == "Resolved"):
            raise HTTPException(403, "Clients can only confirm closure of a resolved ticket")
    elif user.role == TECH:
        if new not in TECH_STATUS:
            raise HTTPException(403, "Technicians cannot set this status")
    elif user.role in (ADMIN, FM):
        if new not in STAFF_STATUS:
            raise HTTPException(422, "Invalid status")
    else:
        raise HTTPException(403, "Read-only role")
    if old == "Closed":
        raise HTTPException(409, "Ticket is closed; reopen it first")
    if new == "Closed" and old != "Resolved":
        raise HTTPException(409, "Only resolved tickets can be closed")
    if new == "Resolved" and not (data.corrective_action.strip() or t.corrective_action):
        raise HTTPException(422, "Corrective action is required to resolve a ticket")
    if new == "Resolved":
        kinds = set(db.scalars(select(Attachment.kind).where(Attachment.ticket_id == t.id)))
        missing = [k for k in ("during", "after") if k not in kinds]
        if missing:
            raise HTTPException(422, "Upload the " + " and ".join(missing) + " photo(s) before resolving the ticket")
    if new in ("In Progress",) and not t.assigned_to_id:
        raise HTTPException(409, "Assign the ticket before starting work")
    if data.root_cause: t.root_cause = data.root_cause
    if data.corrective_action: t.corrective_action = data.corrective_action
    if data.closure_remarks: t.closure_remarks = data.closure_remarks
    t.status = new
    ts = now()
    if new == "Acknowledged": t.acknowledged_at = t.acknowledged_at or ts
    if new == "In Progress": t.work_started_at = t.work_started_at or ts
    if new == "Resolved": t.resolved_at = ts
    if new == "Closed": t.closed_at = ts
    log(db, t, user, "status_change", old, new, data.note)
    db.commit()
    return ticket_out(t)


@router.post("/tickets/{tid}/priority")
def change_priority(tid: int, data: PriorityIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role not in (ADMIN, FM):
        raise HTTPException(403, "Only facility managers or admins can change priority")
    if data.priority not in PRIORITIES:
        raise HTTPException(422, "Invalid priority")
    t = get_ticket(db, user, tid)
    log(db, t, user, "priority_change", note=f"{t.priority} -> {data.priority}. {data.note}".strip())
    t.priority = data.priority
    db.commit()
    return ticket_out(t)


@router.post("/tickets/{tid}/comments", status_code=201)
def add_comment(tid: int, data: CommentIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    t = get_ticket(db, user, tid)
    internal = data.internal and user.role in STAFF
    c = Comment(ticket_id=t.id, author_id=user.id, body=data.body, internal=internal)
    db.add(c)
    log(db, t, user, "comment", note="Internal note" if internal else "Comment added")
    db.commit()
    return {"id": c.id}


@router.post("/tickets/{tid}/reopen")
def reopen(tid: int, data: ReopenIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role not in (CLIENT, FM, ADMIN):
        raise HTTPException(403, "Not allowed to reopen tickets")
    t = get_ticket(db, user, tid)
    if t.status not in ("Resolved", "Closed"):
        raise HTTPException(409, "Only resolved or closed tickets can be reopened")
    old = t.status
    t.status = "Reopened"
    t.closed_at = None
    log(db, t, user, "reopened", old, "Reopened", data.reason)
    db.commit()
    return ticket_out(t)


@router.post("/tickets/{tid}/feedback", status_code=201)
def feedback(tid: int, data: FeedbackIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    t = get_ticket(db, user, tid)
    if user.role != CLIENT or t.requester_id != user.id:
        raise HTTPException(403, "Only the requester can rate this ticket")
    if t.status not in ("Resolved", "Closed"):
        raise HTTPException(409, "Feedback is allowed after the ticket is resolved")
    if db.scalar(select(Feedback).where(Feedback.ticket_id == t.id)):
        raise HTTPException(409, "Feedback already submitted")
    db.add(Feedback(ticket_id=t.id, rating=data.rating, comment=data.comment))
    log(db, t, user, "feedback", note=f"Rating {data.rating}/5")
    db.commit()
    return {"ok": True}


async def store_upload(file: UploadFile, photo: bool = False):
    """Validate + save an upload. Returns (stored_name, size, safe_filename, content_type)."""
    ext = os.path.splitext(file.filename or "")[1].lower()
    ctype = file.content_type or ""
    if ext not in ALLOWED_EXT or not ctype.startswith(ALLOWED_MIME_PREFIX):
        raise HTTPException(415, f"File type not allowed. Allowed: {', '.join(sorted(ALLOWED_EXT))}")
    if photo and (ext not in IMAGE_EXT or not ctype.startswith("image/")):
        raise HTTPException(415, "Before / during / after evidence must be an image (jpg, png, webp)")
    limit = settings.max_upload_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"File exceeds {settings.max_upload_mb} MB")
    os.makedirs(settings.upload_dir, exist_ok=True)
    stored = f"{uuid.uuid4().hex}{ext}"
    with open(os.path.join(settings.upload_dir, stored), "wb") as f:
        f.write(data)
    return stored, len(data), os.path.basename(file.filename or "file")[:200], ctype


@router.post("/tickets/{tid}/attachments", status_code=201)
async def upload(tid: int, file: UploadFile = File(...), kind: str = Form("evidence"),
                 user: User = Depends(current_user), db: Session = Depends(get_db)):
    t = get_ticket(db, user, tid)
    if kind not in ("before", "during", "after", "evidence"):
        raise HTTPException(422, "Invalid attachment kind")
    if t.status == "Closed":
        raise HTTPException(409, "Ticket is closed; reopen it to add files")
    if user.role == CLIENT and kind not in ("before", "evidence"):
        raise HTTPException(403, "Clients can only add 'before' photos or supporting files")
    if user.role not in (CLIENT, ADMIN, FM, TECH):
        raise HTTPException(403, "Not allowed to upload")
    stored, size, fname, ctype = await store_upload(file, photo=kind in PHOTO_KINDS)
    a = Attachment(ticket_id=t.id, uploader_id=user.id, filename=fname, stored_name=stored,
                   content_type=ctype, size=size, kind=kind)
    db.add(a)
    log(db, t, user, "attachment", note=f"{kind} photo: {fname}" if kind in PHOTO_KINDS else f"{kind}: {fname}")
    db.commit()
    return {"id": a.id, "filename": a.filename}


@router.get("/attachments/{aid}")
def download(aid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    a = db.get(Attachment, aid)
    if not a:
        raise HTTPException(404, "File not found")
    get_ticket(db, user, a.ticket_id)  # enforces same access scope as the ticket
    path = os.path.join(settings.upload_dir, a.stored_name)
    if not os.path.exists(path):
        raise HTTPException(404, "File missing from storage")
    return FileResponse(path, media_type=a.content_type, filename=a.filename)

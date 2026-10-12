import json
import os
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
import chatbot
from config import settings
from db import get_db
from deps import ADMIN, CLIENT, FM, current_user, user_site_ids
from models import ChatFile, ChatMessage, ChatThread, User
from tickets import store_upload

router = APIRouter(prefix="/api/chat", tags=["chat"])
AGENTS = (ADMIN, FM)
CAN_CHAT = (CLIENT, FM, ADMIN)


class MsgIn(BaseModel):
    text: str = Field(default="", max_length=2000)
    choice: str | None = None


def now():
    return datetime.now(timezone.utc)


def is_owner(user, th):
    return th.requester_id == user.id


def can_access(db, user, th):
    if is_owner(user, th) or user.role == ADMIN:
        return True
    if user.role == FM:
        req = db.get(User, th.requester_id)
        mine = set(user_site_ids(user))
        return bool(mine & set(user_site_ids(req))) or (th.site_id in mine)
    return False


def get_thread(db, user, tid):
    th = db.get(ChatThread, tid)
    if not th or not can_access(db, user, th):
        raise HTTPException(404, "Chat not found")
    return th


def msg_out(m):
    name = {"user": m.sender.name if m.sender else "You", "agent": m.sender.name if m.sender else "Agent",
            "bot": "FM Assistant", "system": "System"}[m.sender_type]
    return {"id": m.id, "sender_type": m.sender_type, "sender": name, "text": m.text,
            "options": json.loads(m.options) if m.options else [], "meta": json.loads(m.meta) if m.meta else None,
            "file": {"id": m.file.id, "filename": m.file.filename, "content_type": m.file.content_type} if m.file else None,
            "created_at": m.created_at}


def thread_out(db, user, th):
    last = db.scalar(select(ChatMessage).where(ChatMessage.thread_id == th.id).order_by(ChatMessage.id.desc()).limit(1))
    own = is_owner(user, th)
    return {"id": th.id, "title": th.title, "mode": th.mode, "own": own, "requester": th.requester.name,
            "agent": th.agent.name if th.agent else None, "ticket": th.ticket.number if th.ticket else None,
            "unread": (th.client_unread if own else th.agent_unread) or 0, "last_message_at": th.last_message_at,
            "preview": (last.text or ("📷 Photo" if last and last.file_id else ""))[:70] if last else ""}


@router.get("/threads")
def threads(user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role not in CAN_CHAT:
        raise HTTPException(403, "Chat is not available for your role")
    rows = db.scalars(select(ChatThread).order_by(ChatThread.last_message_at.desc()).limit(300)).all()
    return [thread_out(db, user, t) for t in rows if can_access(db, user, t)][:100]


@router.post("/threads", status_code=201)
def new_thread(user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role not in CAN_CHAT:
        raise HTTPException(403, "Chat is not available for your role")
    th = ChatThread(requester_id=user.id, title="New chat")
    db.add(th)
    db.flush()
    chatbot.greet(db, user, th)
    db.commit()
    db.refresh(th)
    return thread_out(db, user, th)


@router.get("/threads/{tid}/messages")
def messages(tid: int, after: int = 0, user: User = Depends(current_user), db: Session = Depends(get_db)):
    th = get_thread(db, user, tid)
    rows = db.scalars(select(ChatMessage).where(ChatMessage.thread_id == th.id, ChatMessage.id > after).order_by(ChatMessage.id)).all()
    if is_owner(user, th):
        changed = th.client_unread != 0
        th.client_unread = 0
    else:
        changed = th.agent_unread != 0
        th.agent_unread = 0
    if changed:
        db.commit()
    return {"mode": th.mode, "title": th.title, "messages": [msg_out(m) for m in rows]}


def _post(db, user, th, text, file_id=None):
    """Store the sender's message and return its id."""
    if th.mode == "closed":
        raise HTTPException(409, "This chat is closed. Start a new chat.")
    owner = is_owner(user, th)
    m = ChatMessage(thread_id=th.id, sender_type="user" if owner else "agent", sender_id=user.id, text=text, file_id=file_id)
    db.add(m)
    db.flush()
    th.last_message_at = now()
    if not owner:
        th.mode, th.assigned_agent_id = "agent", user.id
        th.client_unread = (th.client_unread or 0) + 1
    elif th.mode == "agent":
        th.agent_unread = (th.agent_unread or 0) + 1
    return m


def _since(db, th, first_id):
    rows = db.scalars(select(ChatMessage).where(ChatMessage.thread_id == th.id, ChatMessage.id >= first_id).order_by(ChatMessage.id)).all()
    return {"mode": th.mode, "title": th.title, "messages": [msg_out(m) for m in rows]}


@router.post("/threads/{tid}/messages")
def send(tid: int, data: MsgIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    th = get_thread(db, user, tid)
    text = (data.choice or data.text or "").strip()
    if not text:
        raise HTTPException(422, "Message is empty")
    m = _post(db, user, th, text)
    if is_owner(user, th) and th.mode == "bot":
        chatbot.handle(db, user, th, text)
    db.commit()
    return _since(db, th, m.id)


@router.post("/threads/{tid}/upload", status_code=201)
async def upload(tid: int, file: UploadFile = File(...), user: User = Depends(current_user), db: Session = Depends(get_db)):
    th = get_thread(db, user, tid)
    if th.mode == "closed":
        raise HTTPException(409, "This chat is closed")
    stored, size, fname, ctype = await store_upload(file, photo=False)
    cf = ChatFile(thread_id=th.id, uploader_id=user.id, filename=fname, stored_name=stored, content_type=ctype, size=size)
    db.add(cf)
    db.flush()
    m = _post(db, user, th, "", file_id=cf.id)
    if is_owner(user, th) and th.mode == "bot":
        chatbot.on_photo(db, th)
    db.commit()
    return _since(db, th, m.id)


@router.post("/threads/{tid}/handoff")
def handoff(tid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    th = get_thread(db, user, tid)
    if not is_owner(user, th):
        raise HTTPException(403, "Only the chat owner can request an agent")
    if th.mode == "bot":
        chatbot.handoff(db, th)
        th.last_message_at = now()
    db.commit()
    return {"mode": th.mode}


@router.post("/threads/{tid}/bot")
def back_to_bot(tid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    th = get_thread(db, user, tid)
    if th.mode == "closed":
        raise HTTPException(409, "Chat is closed")
    th.mode = "bot"
    chatbot.greet(db, user if is_owner(user, th) else th.requester, th)
    th.last_message_at = now()
    db.commit()
    return {"mode": th.mode}


@router.post("/threads/{tid}/close")
def close(tid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    th = get_thread(db, user, tid)
    if user.role not in AGENTS:
        raise HTTPException(403, "Only helpdesk agents can close chats")
    th.mode = "closed"
    db.add(ChatMessage(thread_id=th.id, sender_type="system", text=f"Chat closed by {user.name}."))
    th.client_unread = (th.client_unread or 0) + 1
    db.commit()
    return {"mode": th.mode}


@router.get("/unread")
def unread(user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role not in CAN_CHAT:
        return {"unread": 0}
    total = 0
    for t in db.scalars(select(ChatThread).where((ChatThread.client_unread > 0) | (ChatThread.agent_unread > 0))):
        if not can_access(db, user, t):
            continue
        total += (t.client_unread if is_owner(user, t) else t.agent_unread) or 0
    return {"unread": total}


@router.get("/files/{fid}")
def file(fid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    cf = db.get(ChatFile, fid)
    if not cf:
        raise HTTPException(404, "File not found")
    get_thread(db, user, cf.thread_id)
    path = os.path.join(settings.upload_dir, cf.stored_name)
    if not os.path.exists(path):
        raise HTTPException(404, "File missing from storage")
    return FileResponse(path, media_type=cf.content_type, filename=cf.filename)

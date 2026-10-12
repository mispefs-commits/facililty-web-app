# AI-Powered Multi-Site Facility Management Helpdesk — Phase 1

FastAPI + SQLAlchemy backend, React + TypeScript frontend, SQLite (dev) / PostgreSQL (prod).

## What Phase 1 contains
- JWT authentication, PBKDF2 password hashing, login throttling, client self-registration (client role only)
- 5 roles: super_admin, management, facility_manager, technician, client — enforced **server-side**
- Hierarchy: Region → Site → Building → Tower → Floor → free-text room/asset. New sites are added from the Admin screen/API with no code change
- Site-scoped access: users only see tickets/sites they are authorised for (out-of-scope tickets return 404)
- Tickets: create, auto ticket number (`TKT-2026-000001`), assign, status workflow, priority change, comments (+ internal notes hidden from clients), reopen, feedback/rating
- Photo/document upload (type + size validated, access checked on download), before/after photos for staff
- Full activity history (audit trail) and an `audit_logs` table for admin actions
- Role dashboards, filters, search, pagination
- Tests covering the full lifecycle: client → assign → technician → resolve → close → feedback

Not yet built (Phases 2–4): SLA engine/escalations, notifications, Excel/PDF exports, AI chatbot, Alembic migrations, Redis/Celery, S3 storage, MFA.

## NEW in this version
- **Photo evidence in 3 stages**: *Before* (when reported, by client / chatbot / staff), *During* (work in progress) and *After* (completed). Thumbnails with click-to-zoom on every ticket. A ticket **cannot be Resolved without at least one During and one After photo**. Clients can only add Before photos; staff add any stage. Stage photos must be images.
- **Client & representative details** on every ticket: client name, representative name, phone, WhatsApp. The WhatsApp number is shown on the ticket and in the chat with a one-click *Chat on WhatsApp* button (wa.me link with a pre-filled message).
- **Multi-chat assistant** (💬 Chat): clients can open many conversations. The bot asks: issue → site → (building) → floor → exact location → client name → representative name → phone → WhatsApp → photos → confirmation, then creates the ticket and posts the representative's WhatsApp number. It also detects category/priority from free text (typos tolerated), flags emergencies (fire, smoke, gas, sparks, flooding…) as Critical with a safety message, warns about duplicate open tickets, lets users edit details before confirming, and answers ticket-status questions using only database data (own tickets only).
- **Live agent chat**: "Talk to an agent" hands the conversation to helpdesk agents (facility managers at the client's sites, and admins). Agents have an inbox with unread counts, see the full transcript and photos, reply, and close chats. Clients can return to the assistant. Chats and the unread badge refresh every 2–5 s (polling).
- **Optional LLM**: set `OPENAI_API_KEY` in `backend/.env` and the bot also uses the model (server-side only, output validated) to suggest category, priority and summary. Works fully without it.
- Live auto-refresh on dashboard, ticket list and ticket detail.

**Important after upgrading:** the database structure changed. Close the app and delete `backend\helpdesk.db` (and `backend\uploads`) once, then start again.

WhatsApp note: the app shows the number and opens WhatsApp click-to-chat. *Automatic* WhatsApp messages from the server need an approved WhatsApp Business API provider (planned for Phase 2 notifications).

## Run on Windows (local)
Prerequisites: Python 3.11+, Node.js 20+.

```
scripts\setup.bat      :: one time
scripts\test.bat       :: run backend tests (should all pass)
scripts\run.bat        :: starts API (8000) and web app (5173)
```
Open http://localhost:5173 (API docs: http://localhost:8000/docs).

Demo accounts (local only, created when `SEED_DEMO=true`; password is `DEMO_PASSWORD` in `backend\.env`, default `ChangeMe@123`):
`admin@example.com`, `manager@example.com`, `fm@example.com`, `tech@example.com`, `client@example.com`

### Try the lifecycle
1. Sign in as `client@example.com` → Raise Complaint → attach a photo.
2. Sign in as `fm@example.com` → open the ticket → Assign to Ravi Technician.
3. Sign in as `tech@example.com` → In Progress → upload before/after → Resolved (corrective action required).
4. Back as client → Confirm & close → rate the service.

## Create the first real administrator (secure)
Set `SEED_DEMO=false` in `backend\.env`, then `scripts\create_admin.bat`. The password is prompted (not echoed) and never stored in files.

## Docker (PostgreSQL)
```
docker compose up --build
```
Web: http://localhost:8080 · API docs: http://localhost:8000/docs.
For anything beyond testing: `SEED_DEMO=false`, set a long random `SECRET_KEY`, change the DB password, put HTTPS in front (reverse proxy / managed platform).

## Load testing (500+ users)
```
pip install locust
cd backend
locust -f loadtest.py --host http://localhost:8000 -u 500 -r 25 --headless -t 5m
```
Run against PostgreSQL with several uvicorn workers (the Dockerfile uses 4), not SQLite. Treat the 500-user goal as a target to measure and tune, not a given.

## Troubleshooting
- `ModuleNotFoundError: app` → run commands from the `backend` folder.
- Web app shows network errors → API must be running on port 8000 (Vite proxies `/api`).
- Client can't raise complaints → an admin must assign the client to a site (Admin → Users → "Add site").
- Port in use → change `--port` / `server.port`.
- Reset local data → stop the API, delete `backend\helpdesk.db` and `backend\uploads`.

## Production notes / next steps
1. Replace `create_all` with Alembic: `pip install alembic; alembic init migrations`, point it at `app.models.Base`, `alembic revision --autogenerate`.
2. Move uploads to S3-compatible storage; move login throttling to Redis.
3. Phase 2: SLA tables + Celery beat for deadline checks, email notifications, openpyxl/reportlab exports.
4. Phase 3: AI chatbot — backend-only OpenAI calls, structured JSON output, user confirmation before ticket creation, safety escalation rules, AI suggestion audit table.
5. Phase 4: load/security testing, backups, monitoring.
"# facililty-web-app" 

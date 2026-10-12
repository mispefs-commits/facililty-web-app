@echo off
cd /d %~dp0..
start "Helpdesk API" cmd /k "cd backend && call .venv\Scripts\activate.bat && uvicorn app.main:app --reload --port 8000"
start "Helpdesk Web" cmd /k "cd frontend && npm run dev"
echo API docs: http://localhost:8000/docs   App: http://localhost:5173

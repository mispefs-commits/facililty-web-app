@echo off
REM One-time setup on Windows. Requires Python 3.11+ and Node.js 20+.
cd /d %~dp0..
echo === Backend ===
cd backend
python -m venv .venv || goto :err
call .venv\Scripts\activate.bat
pip install -r requirements.txt || goto :err
if not exist .env copy ..\.env.example .env
cd ..
echo === Frontend ===
cd frontend
call npm install || goto :err
cd ..
echo.
echo Setup complete. Run scripts\run.bat
exit /b 0
:err
echo SETUP FAILED - see messages above
exit /b 1

@echo off
cd /d %~dp0..\backend
call .venv\Scripts\activate.bat
pytest -v

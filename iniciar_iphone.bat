@echo off
cd /d "%~dp0"
set "PORT=5001"
set "DEBUG=0"
venv\Scripts\python.exe run_iphone.py

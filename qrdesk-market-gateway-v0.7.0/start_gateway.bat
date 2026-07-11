@echo off
setlocal
cd /d %~dp0
python -m uvicorn qrdesk_gateway.app:app --host 127.0.0.1 --port 8787
endlocal

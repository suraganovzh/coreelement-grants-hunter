@echo off
title Grant Hunter Dashboard
echo Starting Grant Hunter Dashboard...
echo.
echo Dashboard will open at http://localhost:8000/dashboard/
echo Press Ctrl+C to stop the server.
echo.
start http://localhost:8000/dashboard/
python -m http.server 8000

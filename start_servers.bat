@echo off
start cmd /k "cd backend && ..\.venv\Scripts\activate && uvicorn main:app --reload"
start cmd /k "cd frontend && npm run dev"
echo Servers are starting in separate windows.

@echo off
set CAL_ENV=development
cd backend
pip install -r requirements.txt
uvicorn main:app --port 8000

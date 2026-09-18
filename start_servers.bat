@echo off
start cmd /k "cd /d C:\Users\keysk\OneDrive\Desktop\project 2\tamper-audit-system\backend && python -m uvicorn auth_backend:app --reload --port 8000"
start cmd /k "cd /d C:\Users\keysk\OneDrive\Desktop\project 2\tamper-audit-system\frontend && python -m http.server 8080"
start cmd /k "cd /d C:\Users\keysk\OneDrive\Desktop\project 2\tamper-audit-system\frontend && python -m http.server 9090"

# start.ps1 — Jalankan backend + frontend SitasiAI sekaligus (dua jendela).
$root = "d:\TUGAS AKHIR\TA"

Write-Host "Menjalankan Backend (FastAPI :8000) ..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
  "-NoExit","-Command",
  "cd '$root'; & '.venv\Scripts\python.exe' -m uvicorn backend.api:app --reload --port 8000"
)

Write-Host "Menjalankan Frontend (Vite :5173) ..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
  "-NoExit","-Command",
  "cd '$root\frontend-react'; npm run dev"
)

Write-Host ""
Write-Host "Backend : http://localhost:8000/docs" -ForegroundColor Green
Write-Host "Frontend: http://localhost:5173"      -ForegroundColor Green
Write-Host "Tunggu backend 'Application startup complete', lalu buka frontend di browser." -ForegroundColor Yellow

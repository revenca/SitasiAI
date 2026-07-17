# run_retrieval_only.ps1 — UJI RETRIEVAL MURNI: HyDE vs SPECTER2 (tanpa generasi, tanpa LLM judge).
# Mengisolasi efek HyDE pada retrieval — di mana satu-satunya tempat HyDE bekerja.
# Hanya butuh OpenRouter (untuk HyDE); TIDAK butuh DeepSeek (tidak ada judge).
# Retrieve top-10; scorer menghitung @3/@5/@10 dengan slicing. RESUMABLE (skip file yang ada).
#
# Jalankan:  .\run_retrieval_only.ps1

$root = "d:\TUGAS AKHIR\TA"
$py   = "$root\.venv\Scripts\python.exe"
$res  = "$root\hasil_eksperimen"
Set-Location $root

$env:RETRIEVAL_ONLY = "1"
$env:TOP_K          = "10"        # retrieve top-10; @3/@5/@10 dihitung saat scoring
$env:HYDE_TEMP      = "0.7"
$env:HYDE_WORDS     = "100-150"

# 1) SPECTER2 saja (mode=baseline → query = paragraf mentah). Deterministik, 0 LLM.
$env:PIPELINE_MODE = "baseline"
$env:RUN_TAG       = "ro_specter"
$specPred = "$res\hasil_prediksi_baseline_k10_ro_specter.csv"
if (Test-Path $specPred) {
    Write-Host "SKIP SPECTER2 (sudah ada)" -ForegroundColor DarkGray
} else {
    Write-Host "`n=== SPECTER2-only (retrieval-only, 0 LLM) ===" -ForegroundColor Cyan
    & $py pipeline.py
    if ($LASTEXITCODE -ne 0) { Write-Host "GAGAL: SPECTER2" -ForegroundColor Red; exit 1 }
}

# 2) HyDE (mode=hyde → query = abstrak HyDE). 5 run stokastik, hanya panggilan HyDE.
$env:PIPELINE_MODE = "hyde"
foreach ($run in 1..5) {
    $env:RUN_TAG = "ro_hyde_r$run"
    $pred = "$res\hasil_prediksi_hyde_k10_ro_hyde_r$run.csv"
    if (Test-Path $pred) { Write-Host "SKIP HyDE r$run (sudah ada)" -ForegroundColor DarkGray; continue }
    Write-Host "`n=== HyDE run $run (retrieval-only) ===" -ForegroundColor Cyan
    & $py pipeline.py
    if ($LASTEXITCODE -ne 0) { Write-Host "GAGAL: HyDE r$run" -ForegroundColor Red; exit 1 }
}

Remove-Item Env:\RETRIEVAL_ONLY -ErrorAction SilentlyContinue
Write-Host "`n=== SKOR RETRIEVAL (Prec/Recall/Hit @3/5/10) ===" -ForegroundColor Yellow
& $py score_retrieval.py

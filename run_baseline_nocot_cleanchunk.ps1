# run_baseline_nocot_cleanchunk.ps1 — Lengkapi ablation: BASELINE MURNI SPECTER2 (tanpa CoT, tanpa HyDE)
# di index clean-chunk. mode=baseline → embed paragraf → simple_generate (bukan CoT). 3 run + judge.
# Melengkapi: clean_specter (ini) vs clean_base (SPECTER2+CoT) vs clean_hyde (HyDE+CoT) yang sudah ada.
# RESUMABLE. Pakai OpenRouter (generate) + DeepSeek (judge).
#
# Jalankan:  .\run_baseline_nocot_cleanchunk.ps1

$root = "d:\TUGAS AKHIR\TA"
$py   = "$root\.venv\Scripts\python.exe"
$res  = "$root\hasil_eksperimen"
Set-Location $root

$env:FAISS_INDEX_FILE = "faiss_index_chunk_clean.bin"
$env:METADATA_FILE    = "metadata_chunk_clean.json"
$env:TOP_K            = "5"
$env:PIPELINE_MODE    = "baseline"     # SPECTER2 langsung + simple_generate (TANPA CoT, TANPA HyDE)

foreach ($run in 1..3) {
    $rtag = "clean_specter_r$run"
    if (Test-Path "$res\hasil_ragas_${rtag}_citation.csv") { Write-Host "SKIP $rtag (ada)" -ForegroundColor DarkGray; continue }
    Write-Host "`n=== $rtag  (mode=baseline, tanpa CoT, index=clean-chunk) ===" -ForegroundColor Cyan
    $env:RUN_TAG = $rtag
    & $py pipeline.py
    if ($LASTEXITCODE -ne 0) { Write-Host "GAGAL pipeline $rtag" -ForegroundColor Red; exit 1 }

    $env:PRED_FILE  = "hasil_eksperimen\hasil_prediksi_baseline_k5_${rtag}.csv"
    $env:RAGAS_FILE = "hasil_eksperimen\hasil_ragas_${rtag}.csv"
    & $py evaluate.py
    if ($LASTEXITCODE -ne 0) { Write-Host "GAGAL evaluate $rtag (saldo DeepSeek?) - berhenti rapi; jalankan ulang utk lanjut." -ForegroundColor Red; exit 2 }
}

Write-Host "`n=== ABLATION 3 KONDISI (clean-chunk) ===" -ForegroundColor Yellow
& $py score_ablation.py

Write-Host "`n=== SELESAI ===" -ForegroundColor Green

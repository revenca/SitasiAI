# run_hyde07.ps1 — Rerun konfigurasi UTAMA baru: HyDE temp 0.7, CoT temp 0.2.
# Output ke file _hyde07 (TIDAK menimpa hasil lama).
# Jalankan:  .\run_hyde07.ps1   (pastikan backend web DIMATIKAN agar GPU bebas)

$ErrorActionPreference = "Stop"
$root = "d:\TUGAS AKHIR\TA"
$py   = "$root\.venv\Scripts\python.exe"
Set-Location $root

$env:HYDE_TEMP  = "0.7"      # KONFIGURASI BARU
$env:COT_TEMP   = "0.2"      # TETAP
$env:HYDE_WORDS = "100-150"  # TETAP
$env:RUN_TAG    = "hyde07"

function Run-One {
    param([string]$Mode, [string]$K)
    Write-Host "`n===== $Mode  K=$K  (HyDE=0.7, CoT=0.2) =====" -ForegroundColor Cyan
    $env:PIPELINE_MODE = $Mode
    $env:TOP_K = $K
    & $py pipeline.py
    if ($LASTEXITCODE -ne 0) { throw "pipeline gagal: $Mode k$K" }

    $env:PRED_FILE  = "hasil_eksperimen\hasil_prediksi_${Mode}_k${K}_hyde07.csv"
    $env:RAGAS_FILE = "hasil_eksperimen\hasil_ragas_${Mode}_k${K}_hyde07.csv"
    & $py evaluate.py
    if ($LASTEXITCODE -ne 0) { throw "evaluate gagal: $Mode k$K" }
    Write-Host "----- selesai: hasil_ragas_${Mode}_k${K}_hyde07.csv -----" -ForegroundColor Green
}

# 1) Validasi dulu: Proposed K=5 harus mendekati P0.6157 / Faith0.6406
Run-One -Mode "proposed" -K "5"
# 2) HyDE-only @ 0.7 (untuk Tabel kontribusi komponen)
Run-One -Mode "hyde" -K "5"
# 3) Variasi K @ 0.7
Run-One -Mode "proposed" -K "3"
Run-One -Mode "proposed" -K "10"

Write-Host "`nSEMUA RUN HyDE=0.7 SELESAI." -ForegroundColor Green

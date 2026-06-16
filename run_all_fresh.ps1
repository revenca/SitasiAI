# run_all_fresh.ps1 — RERUN SEMUA dari NOL, data baru, UNIFORM 5 run tiap kondisi.
# Bagian A: Retrieval murni (SPECTER2 5x + HyDE 5x). SPECTER2 dijalankan 5x utk MEMBUKTIKAN
#           determinisme (std=0), bukan diasumsikan. Tanpa generasi/judge → murah, tanpa DeepSeek.
# Bagian B: Faithfulness/generasi (Baseline 5x + HyDE 5x, pipeline + judge). Butuh OpenRouter + DeepSeek.
# Bug HyDE silent-fallback sudah diperbaiki (kolom hyde_fallback). RESUMABLE (skip file yang sudah ada).
# Tanpa seed → run independen (HyDE temp 0.7 & CoT temp 0.2 sampling beda tiap run).
#
# Jalankan:  .\run_all_fresh.ps1   (sebaiknya matikan backend web agar GPU bebas)

$root = "d:\TUGAS AKHIR\TA"
$py   = "$root\.venv\Scripts\python.exe"
$res  = "$root\hasil_eksperimen"
Set-Location $root

# ============ BAGIAN A: RETRIEVAL MURNI (tanpa generasi, tanpa judge) ============
$env:RETRIEVAL_ONLY = "1"
$env:TOP_K          = "10"          # retrieve top-10; scorer hitung @3/@5/@10
$env:HYDE_TEMP      = "0.7"
$env:HYDE_WORDS     = "100-150"

Write-Host "`n########## BAGIAN A: RETRIEVAL MURNI ##########" -ForegroundColor Magenta

# SPECTER2 saja (mode=baseline → query = paragraf mentah). 0 LLM, deterministik → 5 run harus identik.
$env:PIPELINE_MODE = "baseline"
foreach ($run in 1..5) {
    $env:RUN_TAG = "fresh_specter_r$run"
    $pred = "$res\hasil_prediksi_baseline_k10_fresh_specter_r$run.csv"
    if (Test-Path $pred) { Write-Host "SKIP A-SPECTER r$run" -ForegroundColor DarkGray; continue }
    Write-Host "`n[A-SPECTER2 run $run] (retrieval-only, 0 LLM)" -ForegroundColor Cyan
    & $py pipeline.py
    if ($LASTEXITCODE -ne 0) { Write-Host "GAGAL: A-SPECTER r$run" -ForegroundColor Red; exit 1 }
}

# HyDE + SPECTER2 (mode=hyde → query = abstrak HyDE). 5 run stokastik, hanya panggilan HyDE.
$env:PIPELINE_MODE = "hyde"
foreach ($run in 1..5) {
    $env:RUN_TAG = "fresh_hyderet_r$run"
    $pred = "$res\hasil_prediksi_hyde_k10_fresh_hyderet_r$run.csv"
    if (Test-Path $pred) { Write-Host "SKIP A-HyDE r$run" -ForegroundColor DarkGray; continue }
    Write-Host "`n[A-HyDE run $run] (retrieval-only)" -ForegroundColor Cyan
    & $py pipeline.py
    if ($LASTEXITCODE -ne 0) { Write-Host "GAGAL: A-HyDE r$run" -ForegroundColor Red; exit 1 }
}

Remove-Item Env:\RETRIEVAL_ONLY -ErrorAction SilentlyContinue
Write-Host "`n[A-SKOR RETRIEVAL]" -ForegroundColor Yellow
& $py score_retrieval.py
if ($LASTEXITCODE -ne 0) { Write-Host "GAGAL skor retrieval" -ForegroundColor Red; exit 1 }

# ============ BAGIAN B: FAITHFULNESS / GENERASI (pipeline + judge) ============
$env:TOP_K      = "5"
$env:HYDE_TEMP  = "0.7"
$env:COT_TEMP   = "0.2"
$env:HYDE_WORDS = "100-150"

$condsB = @(
    @{ tag = "fresh_base"; mode = "cot"      },   # Baseline = tanpa HyDE (+CoT)
    @{ tag = "fresh_prop"; mode = "proposed" }    # HyDE      = HyDE (+CoT)
)
Write-Host "`n########## BAGIAN B: FAITHFULNESS (Baseline vs HyDE, 5 run) ##########" -ForegroundColor Magenta
foreach ($run in 1..5) {
    foreach ($c in $condsB) {
        $rtag = "$($c.tag)_r$run"
        if (Test-Path "$res\hasil_ragas_${rtag}_citation.csv") { Write-Host "SKIP B-$rtag (ada)" -ForegroundColor DarkGray; continue }
        Write-Host "`n[B-$rtag] (mode=$($c.mode) K=5 HyDE=0.7 CoT=0.2)" -ForegroundColor Cyan
        $env:PIPELINE_MODE = $c.mode
        $env:RUN_TAG       = $rtag
        & $py pipeline.py
        if ($LASTEXITCODE -ne 0) { Write-Host "GAGAL pipeline B-$rtag" -ForegroundColor Red; exit 1 }

        $env:PRED_FILE  = "hasil_eksperimen\hasil_prediksi_$($c.mode)_k5_${rtag}.csv"
        $env:RAGAS_FILE = "hasil_eksperimen\hasil_ragas_${rtag}.csv"
        & $py evaluate.py
        if ($LASTEXITCODE -ne 0) { Write-Host "GAGAL evaluate B-$rtag (saldo DeepSeek?) - berhenti rapi; jalankan ulang utk lanjut." -ForegroundColor Red; exit 2 }
    }
}
Write-Host "`n[B-SKOR FAITHFULNESS]" -ForegroundColor Yellow
& $py score_faithfulness.py

Write-Host "`n########## SEMUA SELESAI (batch fresh) ##########" -ForegroundColor Green

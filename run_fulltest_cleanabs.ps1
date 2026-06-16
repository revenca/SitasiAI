# run_fulltest_cleanabs.ps1 — Tes END-TO-END di index CLEAN-ABSTRACT (100 vektor, judul+abstrak).
# HyDE (prompt baru) + generate sitasi (CoT) + judge → Faithfulness, Answer Relevancy, citation@5.
# Baseline (tanpa HyDE) vs HyDE, 3 run masing-masing. CoT selalu aktif (komponen tetap).
# Pakai OpenRouter (HyDE+CoT) + DeepSeek (judge). RESUMABLE (skip yang sudah ada).
#
# Jalankan:  .\run_fulltest_cleanabs.ps1

$root = "d:\TUGAS AKHIR\TA"
$py   = "$root\.venv\Scripts\python.exe"
$res  = "$root\hasil_eksperimen"
Set-Location $root

# Index CLEAN-ABSTRACT utk retrieval (pipeline) DAN mapping citation (evaluate)
$env:FAISS_INDEX_FILE = "faiss_index_abstract_clean.bin"
$env:METADATA_FILE    = "metadata_abstract_clean.json"
$env:TOP_K            = "5"
$env:HYDE_TEMP        = "0.7"
$env:COT_TEMP         = "0.2"
$env:HYDE_WORDS       = "100-150"

$conds = @(
    @{ tag = "cleanabs_base"; mode = "cot"      },   # Baseline = tanpa HyDE (+CoT)
    @{ tag = "cleanabs_hyde"; mode = "proposed" }    # HyDE (prompt baru) + CoT
)

foreach ($run in 1..3) {
    foreach ($c in $conds) {
        $rtag = "$($c.tag)_r$run"
        if (Test-Path "$res\hasil_ragas_${rtag}_citation.csv") { Write-Host "SKIP $rtag (ada)" -ForegroundColor DarkGray; continue }
        Write-Host "`n=== $rtag  (mode=$($c.mode), index=clean-abstract) ===" -ForegroundColor Cyan
        $env:PIPELINE_MODE = $c.mode
        $env:RUN_TAG       = $rtag
        & $py pipeline.py
        if ($LASTEXITCODE -ne 0) { Write-Host "GAGAL pipeline $rtag" -ForegroundColor Red; exit 1 }

        $env:PRED_FILE  = "hasil_eksperimen\hasil_prediksi_$($c.mode)_k5_${rtag}.csv"
        $env:RAGAS_FILE = "hasil_eksperimen\hasil_ragas_${rtag}.csv"
        & $py evaluate.py
        if ($LASTEXITCODE -ne 0) { Write-Host "GAGAL evaluate $rtag (saldo DeepSeek?) - berhenti rapi; jalankan ulang utk lanjut." -ForegroundColor Red; exit 2 }
    }
}

Write-Host "`n=== SKOR (Baseline vs HyDE, clean-abstract) ===" -ForegroundColor Yellow
& $py score_faithfulness.py cleanabs_base cleanabs_hyde

Write-Host "`n=== SELESAI ===" -ForegroundColor Green

# run_hyde_isolation_5x.ps1 — ISOLASI MURNI HyDE (5 run, mean±std) di index clean-chunk.
# Baseline = SPECTER2 tanpa HyDE (mode=baseline, tanpa CoT)
# HyDE     = SPECTER2 + HyDE   (mode=hyde,     tanpa CoT, prompt baru)  → beda HANYA HyDE.
# K=5, HyDE 0.7. RESUMABLE (clean_specter r1-3 sudah ada → tinggal r4,r5; clean_hydeonly r1-5 baru).
# OpenRouter (HyDE+generate) + DeepSeek (judge).
#
# Jalankan:  .\run_hyde_isolation_5x.ps1

$root = "d:\TUGAS AKHIR\TA"
$py   = "$root\.venv\Scripts\python.exe"
$res  = "$root\hasil_eksperimen"
Set-Location $root

$env:FAISS_INDEX_FILE = "faiss_index_chunk_clean.bin"
$env:METADATA_FILE    = "metadata_chunk_clean.json"
$env:TOP_K            = "5"
$env:HYDE_TEMP        = "0.7"
$env:HYDE_WORDS       = "100-150"

$conds = @(
    @{ tag = "clean_specter";  mode = "baseline" },   # Baseline: SPECTER2, tanpa HyDE, tanpa CoT
    @{ tag = "clean_hydeonly"; mode = "hyde"     }    # HyDE: SPECTER2 + HyDE (query expansion), tanpa CoT
)

foreach ($run in 1..5) {
    foreach ($c in $conds) {
        $rtag = "$($c.tag)_r$run"
        if (Test-Path "$res\hasil_ragas_${rtag}_citation.csv") { Write-Host "SKIP $rtag (ada)" -ForegroundColor DarkGray; continue }
        Write-Host "`n=== $rtag  (mode=$($c.mode), index=clean-chunk) ===" -ForegroundColor Cyan
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

Write-Host "`n=== SKOR: Baseline vs HyDE (isolasi murni, 5 run, mean+-std) ===" -ForegroundColor Yellow
& $py score_faithfulness.py clean_specter clean_hydeonly

Write-Host "`n=== SELESAI ===" -ForegroundColor Green

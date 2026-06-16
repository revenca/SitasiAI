# run_sensitivity_hyde.ps1 — Uji sensitivitas HyDE (5 RUN): temperature & panjang abstrak.
# Setup: clean-chunk, proper HyDE (N=5 + query), K=5, CoT 0.2, mode=proposed.
# Titik off-standar (4): temp 0.2, temp 0.4, panjang 50-80, panjang 200-250 → 5 run masing-masing.
# r1 sudah ada (disalin dari run single), tinggal r2-r5. Titik DEFAULT (0.7/100-150) pakai data 'phyde' yg sudah 5 run.
# RESUMABLE. OpenRouter + DeepSeek.
#
# Jalankan:  .\run_sensitivity_hyde.ps1

$root = "d:\TUGAS AKHIR\TA"
$py   = "$root\.venv\Scripts\python.exe"
$res  = "$root\hasil_eksperimen"
Set-Location $root

$env:FAISS_INDEX_FILE   = "faiss_index_chunk_clean.bin"
$env:METADATA_FILE      = "metadata_chunk_clean.json"
$env:TOP_K              = "5"
$env:COT_TEMP           = "0.2"
$env:PIPELINE_MODE      = "proposed"
$env:HYDE_N             = "5"
$env:HYDE_INCLUDE_QUERY = "1"

# (tag, HYDE_TEMP, HYDE_WORDS) — hanya 4 titik off-standar
$configs = @(
    @{ tag = "sens_t02";  temp = "0.2"; words = "100-150" },
    @{ tag = "sens_t04";  temp = "0.4"; words = "100-150" },
    @{ tag = "sens_w50";  temp = "0.7"; words = "50-80"   },
    @{ tag = "sens_w200"; temp = "0.7"; words = "200-250" }
)

foreach ($run in 1..5) {
    foreach ($c in $configs) {
        $rtag = "$($c.tag)_r$run"
        if (Test-Path "$res\hasil_ragas_${rtag}_citation.csv") { Write-Host "SKIP $rtag (ada)" -ForegroundColor DarkGray; continue }
        Write-Host "`n=== $rtag  (HyDE temp=$($c.temp), words=$($c.words)) ===" -ForegroundColor Cyan
        $env:HYDE_TEMP  = $c.temp
        $env:HYDE_WORDS = $c.words
        $env:RUN_TAG    = $rtag
        & $py pipeline.py
        if ($LASTEXITCODE -ne 0) { Write-Host "GAGAL pipeline $rtag" -ForegroundColor Red; exit 1 }

        $env:PRED_FILE  = "hasil_eksperimen\hasil_prediksi_proposed_k5_${rtag}.csv"
        $env:RAGAS_FILE = "hasil_eksperimen\hasil_ragas_${rtag}.csv"
        & $py evaluate.py
        if ($LASTEXITCODE -ne 0) { Write-Host "GAGAL evaluate $rtag (saldo DeepSeek?) - berhenti rapi; jalankan ulang utk lanjut." -ForegroundColor Red; exit 2 }
    }
}

Write-Host "`n=== TABEL SENSITIVITAS HyDE (5 run, mean+-std) ===" -ForegroundColor Yellow
& $py score_sensitivity_hyde.py

Write-Host "`n=== SELESAI ===" -ForegroundColor Green

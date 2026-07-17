# run_sensitivity.ps1 — Eksperimen analisis sensitivitas hyperparameter.
# Menjawab: efek CoT-temp, HyDE-temp, dan panjang HyDE.
# Jalankan dari root:  .\run_sensitivity.ps1
#
# Catatan desain:
#  - Eksp A (CoT temp): HyDE dibuat DETERMINISTIK (HYDE_TEMP=0) agar retrieval
#    IDENTIK antar varian → CoT temp terisolasi (hanya Faithfulness/AnsRel berubah).
#  - Eksp B/C: retrieval memang berubah → laporkan Precision/Recall/Hit.
#  - Titik 0.4 (Eksp B) & 100-150 (Eksp C) = pakai hasil 'proposed_k5' yang sudah ada.

$ErrorActionPreference = "Stop"
$root = "d:\TUGAS AKHIR\TA"
$py   = "$root\.venv\Scripts\python.exe"
Set-Location $root

$env:PIPELINE_MODE = "proposed"
$env:TOP_K         = "5"

function Run-Variant {
    param([string]$Tag, [string]$HydeTemp, [string]$CotTemp, [string]$HydeWords)
    Write-Host "`n===== VARIAN: $Tag  (HyDE_t=$HydeTemp, CoT_t=$CotTemp, words=$HydeWords) =====" -ForegroundColor Cyan
    $env:HYDE_TEMP  = $HydeTemp
    $env:COT_TEMP   = $CotTemp
    $env:HYDE_WORDS = $HydeWords
    $env:RUN_TAG    = $Tag

    & $py pipeline.py
    if ($LASTEXITCODE -ne 0) { throw "pipeline gagal pada $Tag" }

    $env:PRED_FILE  = "hasil_eksperimen\hasil_prediksi_proposed_k5_$Tag.csv"
    $env:RAGAS_FILE = "hasil_eksperimen\hasil_ragas_$Tag.csv"
    & $py evaluate.py
    if ($LASTEXITCODE -ne 0) { throw "evaluate gagal pada $Tag" }
    Write-Host "----- $Tag selesai → hasil_ragas_$Tag.csv -----" -ForegroundColor Green
}

# ── Eksperimen A: variasi CoT temperature (HyDE deterministik) ────────────────
Run-Variant -Tag "cot_t02" -HydeTemp "0" -CotTemp "0.2" -HydeWords "100-150"
Run-Variant -Tag "cot_t05" -HydeTemp "0" -CotTemp "0.5" -HydeWords "100-150"
Run-Variant -Tag "cot_t07" -HydeTemp "0" -CotTemp "0.7" -HydeWords "100-150"

# ── Eksperimen B: variasi HyDE temperature (CoT tetap 0.2) ────────────────────
# (titik 0.4 = pakai 'proposed_k5' yang sudah ada)
Run-Variant -Tag "hyde_t02" -HydeTemp "0.2" -CotTemp "0.2" -HydeWords "100-150"
Run-Variant -Tag "hyde_t07" -HydeTemp "0.7" -CotTemp "0.2" -HydeWords "100-150"

# ── Eksperimen C: variasi panjang abstrak HyDE ───────────────────────────────
# (titik 100-150 = pakai 'proposed_k5' yang sudah ada)
Run-Variant -Tag "hyde_w50"  -HydeTemp "0.4" -CotTemp "0.2" -HydeWords "50-80"
Run-Variant -Tag "hyde_w200" -HydeTemp "0.4" -CotTemp "0.2" -HydeWords "200-250"

Write-Host "`nSEMUA EKSPERIMEN SENSITIVITAS SELESAI." -ForegroundColor Green
Write-Host "Lanjut: & '$py' export_sensitivity.py  (buat tabel + grafik)" -ForegroundColor Yellow

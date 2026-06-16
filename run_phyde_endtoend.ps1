# run_phyde_endtoend.ps1 — END-TO-END: Baseline (SPECTER2+CoT) vs PROPER HyDE+CoT, clean-chunk, 5 run.
# Proper HyDE: HYDE_N=5 abstrak + embedding paragraf asli, dirata-rata (Gao et al.) + prompt baru.
# Beda HANYA HyDE (CoT sama-sama nyala). RESUMABLE. OpenRouter (HyDE+CoT) + DeepSeek (judge).
#
# Jalankan:  .\run_phyde_endtoend.ps1

$root = "d:\TUGAS AKHIR\TA"
$py   = "$root\.venv\Scripts\python.exe"
$res  = "$root\hasil_eksperimen"
Set-Location $root

$env:FAISS_INDEX_FILE   = "faiss_index_chunk_clean.bin"
$env:METADATA_FILE      = "metadata_chunk_clean.json"
$env:TOP_K              = "5"
$env:HYDE_TEMP          = "0.7"
$env:COT_TEMP           = "0.2"
$env:HYDE_WORDS         = "100-150"
$env:HYDE_N             = "5"      # PROPER HyDE (mode=cot abaikan ini)
$env:HYDE_INCLUDE_QUERY = "1"

$conds = @(
    @{ tag = "clean_base"; mode = "cot"      },   # Baseline = SPECTER2 + CoT (reuse r1-3 + tambah r4,r5)
    @{ tag = "phyde";      mode = "proposed" }    # Proper HyDE + CoT
)

foreach ($run in 1..5) {
    foreach ($c in $conds) {
        $rtag = "$($c.tag)_r$run"
        if (Test-Path "$res\hasil_ragas_${rtag}_citation.csv") { Write-Host "SKIP $rtag (ada)" -ForegroundColor DarkGray; continue }
        Write-Host "`n=== $rtag  (mode=$($c.mode), clean-chunk, properHyDE N=5) ===" -ForegroundColor Cyan
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

Write-Host "`n=== SKOR: Baseline vs PROPER HyDE (5 run, mean+-std) ===" -ForegroundColor Yellow
& $py score_faithfulness.py clean_base phyde

Write-Host "`n=== SELESAI ===" -ForegroundColor Green

# run_variasi_k.ps1 — Lengkapi Variasi K: Faithfulness di K=3 & K=10 (K=5 sudah ada), clean-chunk.
# Baseline (mode=cot) + Proper HyDE (mode=proposed, N=5 +query), 5 run masing-masing (HyDE stokastik).
# RESUMABLE. OpenRouter (HyDE+CoT) + DeepSeek (judge).
#
# Jalankan:  .\run_variasi_k.ps1

$root = "d:\TUGAS AKHIR\TA"
$py   = "$root\.venv\Scripts\python.exe"
$res  = "$root\hasil_eksperimen"
Set-Location $root

$env:FAISS_INDEX_FILE   = "faiss_index_chunk_clean.bin"
$env:METADATA_FILE      = "metadata_chunk_clean.json"
$env:HYDE_TEMP          = "0.7"
$env:COT_TEMP           = "0.2"
$env:HYDE_WORDS         = "100-150"
$env:HYDE_N             = "5"
$env:HYDE_INCLUDE_QUERY = "1"

# (K, tag, mode) — K=5 sudah ada (clean_base, phyde), jadi hanya K=3 & K=10
$configs = @(
    @{ k = "3";  tag = "base_k3";   mode = "cot"      },
    @{ k = "3";  tag = "phyde_k3";  mode = "proposed" },
    @{ k = "10"; tag = "base_k10";  mode = "cot"      },
    @{ k = "10"; tag = "phyde_k10"; mode = "proposed" }
)

foreach ($run in 1..5) {
    foreach ($c in $configs) {
        $rtag = "$($c.tag)_r$run"
        if (Test-Path "$res\hasil_ragas_${rtag}_citation.csv") { Write-Host "SKIP $rtag (ada)" -ForegroundColor DarkGray; continue }
        Write-Host "`n=== $rtag  (mode=$($c.mode) K=$($c.k) clean-chunk) ===" -ForegroundColor Cyan
        $env:TOP_K         = $c.k
        $env:PIPELINE_MODE = $c.mode
        $env:RUN_TAG       = $rtag
        & $py pipeline.py
        if ($LASTEXITCODE -ne 0) { Write-Host "GAGAL pipeline $rtag" -ForegroundColor Red; exit 1 }

        $env:PRED_FILE  = "hasil_eksperimen\hasil_prediksi_$($c.mode)_k$($c.k)_${rtag}.csv"
        $env:RAGAS_FILE = "hasil_eksperimen\hasil_ragas_${rtag}.csv"
        & $py evaluate.py
        if ($LASTEXITCODE -ne 0) { Write-Host "GAGAL evaluate $rtag (saldo DeepSeek?) - berhenti rapi; jalankan ulang utk lanjut." -ForegroundColor Red; exit 2 }
    }
}

Write-Host "`n=== TABEL VARIASI K LENGKAP ===" -ForegroundColor Yellow
& $py score_variasi_k.py

Write-Host "`n=== SELESAI ===" -ForegroundColor Green

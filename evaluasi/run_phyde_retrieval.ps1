# run_phyde_retrieval.ps1 — GATE MURAH: proper HyDE (multi-gen+avg+query) vs SPECTER2, retrieval-only, clean-chunk.
# Menguji mekanisme: apakah HyDE yang diimplementasi BENAR memperbaiki retrieval? (tanpa generasi/judge)
# HYDE_N=5 abstrak/kueri, +embedding paragraf asli, dirata-rata. 5 run (stokastik). Hanya OpenRouter, TANPA DeepSeek.
#
# Jalankan:  .\run_phyde_retrieval.ps1

$root = "d:\TUGAS AKHIR\TA\evaluasi"
$py   = "d:\TUGAS AKHIR\TA\.venv\Scripts\python.exe"
$res  = "$root\hasil_eksperimen"
Set-Location $root

$env:FAISS_INDEX_FILE = "faiss_index_chunk_clean.bin"
$env:METADATA_FILE    = "metadata_chunk_clean.json"
$env:RETRIEVAL_ONLY   = "1"
$env:TOP_K            = "10"
$env:PIPELINE_MODE    = "hyde"          # HyDE retrieval (CoT tak relevan utk retrieval-only)
$env:HYDE_TEMP        = "0.7"
$env:HYDE_WORDS       = "100-150"
$env:HYDE_N           = "5"             # PROPER HyDE: 5 abstrak hipotetis
$env:HYDE_INCLUDE_QUERY = "1"           # + sertakan embedding paragraf asli (hybrid)

foreach ($run in 1..5) {
    $rtag = "phyde_ret_r$run"
    $pred = "$res\hasil_prediksi_hyde_k10_$rtag.csv"
    if (Test-Path $pred) { Write-Host "SKIP $rtag (ada)" -ForegroundColor DarkGray; continue }
    Write-Host "`n=== $rtag  (proper HyDE N=5 +query, retrieval-only, clean-chunk) ===" -ForegroundColor Cyan
    $env:RUN_TAG = $rtag
    & $py pipeline.py
    if ($LASTEXITCODE -ne 0) { Write-Host "GAGAL $rtag" -ForegroundColor Red; exit 1 }
}

Remove-Item Env:\RETRIEVAL_ONLY, Env:\HYDE_N, Env:\HYDE_INCLUDE_QUERY -ErrorAction SilentlyContinue
Write-Host "`n=== SKOR: Proper HyDE vs SPECTER2 (retrieval) ===" -ForegroundColor Yellow
& $py score_phyde_retrieval.py

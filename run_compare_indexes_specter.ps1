# run_compare_indexes_specter.ps1 — Opsi A: SPECTER2-only retrieval di 3 index (GRATIS, deterministik).
# Query = paragraf mentah (mode=baseline), retrieval-only (tanpa generasi/judge), TOP_K=10.
# Bandingkan representasi dokumen: dirty-chunk vs clean-chunk vs clean-abstract.
#
# Jalankan:  .\run_compare_indexes_specter.ps1

$root = "d:\TUGAS AKHIR\TA"
$py   = "$root\.venv\Scripts\python.exe"
$res  = "$root\hasil_eksperimen"
Set-Location $root

$env:RETRIEVAL_ONLY = "1"
$env:TOP_K          = "10"
$env:PIPELINE_MODE  = "baseline"     # query = paragraf mentah (SPECTER2 langsung, tanpa HyDE)

# (tag, faiss_index, metadata)
$indexes = @(
    @{ tag="specter_dirty";      faiss="faiss_index.bin";                 meta="metadata.json" },
    @{ tag="specter_cleanchunk"; faiss="faiss_index_chunk_clean.bin";     meta="metadata_chunk_clean.json" },
    @{ tag="specter_cleanabs";   faiss="faiss_index_abstract_clean.bin";  meta="metadata_abstract_clean.json" }
)

foreach ($ix in $indexes) {
    $pred = "$res\hasil_prediksi_baseline_k10_$($ix.tag).csv"
    if (Test-Path $pred) { Write-Host "SKIP $($ix.tag) (sudah ada)" -ForegroundColor DarkGray; continue }
    Write-Host "`n=== $($ix.tag)  (index=$($ix.faiss)) ===" -ForegroundColor Cyan
    $env:FAISS_INDEX_FILE = $ix.faiss
    $env:METADATA_FILE    = $ix.meta
    $env:RUN_TAG          = $ix.tag
    & $py pipeline.py
    if ($LASTEXITCODE -ne 0) { Write-Host "GAGAL $($ix.tag)" -ForegroundColor Red; exit 1 }
}

Remove-Item Env:\RETRIEVAL_ONLY, Env:\FAISS_INDEX_FILE, Env:\METADATA_FILE, Env:\RUN_TAG -ErrorAction SilentlyContinue
Write-Host "`n=== SKOR PERBANDINGAN INDEX ===" -ForegroundColor Yellow
& $py score_index_compare.py

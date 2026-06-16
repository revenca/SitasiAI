# run_build_clean_indexes.ps1 — Bangun 2 index BARU dari teks bersih (output_teks_clean/).
# Index lama (faiss_index.bin/metadata.json & faiss_index_abstract.bin) TIDAK disentuh.
# Lokal (SPECTER2 GPU), tanpa API.
#
# Jalankan:  .\run_build_clean_indexes.ps1

$root = "d:\TUGAS AKHIR\TA"
$py   = "$root\.venv\Scripts\python.exe"
Set-Location $root

$env:OUTPUT_TEKS_DIR = "output_teks_clean"

Write-Host "`n=== [1/2] Index CHUNK (clean) — chunk 512 char dari teks bersih ===" -ForegroundColor Cyan
$env:FAISS_INDEX_FILE = "faiss_index_chunk_clean.bin"
$env:METADATA_FILE    = "metadata_chunk_clean.json"
& $py indexing.py
if ($LASTEXITCODE -ne 0) { Write-Host "GAGAL build chunk index" -ForegroundColor Red; exit 1 }

Write-Host "`n=== [2/2] Index ABSTRAK (clean) — judul+abstrak, 1 vektor/paper ===" -ForegroundColor Cyan
$env:FAISS_INDEX_FILE = "faiss_index_abstract_clean.bin"
$env:METADATA_FILE    = "metadata_abstract_clean.json"
& $py indexing_abstract.py
if ($LASTEXITCODE -ne 0) { Write-Host "GAGAL build abstrak index" -ForegroundColor Red; exit 1 }

Remove-Item Env:\OUTPUT_TEKS_DIR, Env:\FAISS_INDEX_FILE, Env:\METADATA_FILE -ErrorAction SilentlyContinue
Write-Host "`n=== SELESAI: 2 index baru dibuat dari teks bersih ===" -ForegroundColor Green
Write-Host "  faiss_index_chunk_clean.bin    + metadata_chunk_clean.json" -ForegroundColor Green
Write-Host "  faiss_index_abstract_clean.bin + metadata_abstract_clean.json" -ForegroundColor Green

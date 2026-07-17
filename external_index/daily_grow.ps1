# daily_grow.ps1 — Tumbuhkan korpus eksternal harian menuju 1 juta (dijalankan Task Scheduler).
# Tiap hari setelah reset budget OpenAlex (tengah malam UTC = 07:00 WIB):
#   1) harvest resume (ambil jatah harian, berhenti bersih saat budget habis)
#   2) embed shard baru (SPECTER2 GPU, skip yang sudah ada)
#   3) rebuild index FAISS
# Semua resumable & idempoten. Berhenti sendiri bila harvested >= TARGET.
$root = "d:\TUGAS AKHIR\TA"
$py   = "$root\.venv\Scripts\python.exe"
$ext  = "$root\external_index"
$log  = "$ext\daily_grow.log"
$env:TARGET = "1000000"
$env:PYTHONUNBUFFERED = "1"
$env:BATCH = "32"          # kecil = hemat VRAM
$env:SLEEP_MS = "40"       # jeda antar-batch = GPU tidak 100% terus (adem)

function Log($m) { "$((Get-Date).ToString('yyyy-MM-dd HH:mm:ss')) $m" | Tee-Object -FilePath $log -Append }

$h = (Get-Content "$ext\harvest_checkpoint.json" | ConvertFrom-Json).harvested
Log "=== daily_grow mulai (harvested=$h) ==="
if ($h -ge 1000000) { Log "TARGET 1 juta tercapai — tidak ada yang perlu dilakukan."; exit 0 }

Log "1/3 harvest (resume)..."
& $py "-u" "$ext\harvest_openalex.py" *>> $log

Log "2/3 embed shard baru (GPU)..."
& $py "-u" "$ext\embed_shards.py" *>> $log

Log "3/3 rebuild index..."
& $py "-u" "$ext\build_index.py" *>> $log

$h2 = (Get-Content "$ext\harvest_checkpoint.json" | ConvertFrom-Json).harvested
Log "=== daily_grow selesai (harvested=$h2, +$($h2-$h) hari ini) ==="

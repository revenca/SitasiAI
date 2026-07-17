# run_harvest_loop.ps1 — Auto-restart harvest sampai TARGET tercapai.
# Harvest resumable via checkpoint; wrapper ini me-restart tiap kali script putus
# (429/jaringan) sampai jumlah 'harvested' >= TARGET. Aman di-Ctrl+C.
$root   = "d:\TUGAS AKHIR\TA"
$py     = "$root\.venv\Scripts\python.exe"
$target = 1000000
$ckpt   = "$root\external_index\harvest_checkpoint.json"
$env:TARGET = "$target"
$env:PYTHONUNBUFFERED = "1"

for ($i = 1; $i -le 500; $i++) {
    $h = 0
    if (Test-Path $ckpt) { $h = (Get-Content $ckpt | ConvertFrom-Json).harvested }
    if ($h -ge $target) { Write-Host "TARGET tercapai: $h" ; break }
    Write-Host "[$(Get-Date -Format HH:mm:ss)] percobaan #$i — harvested=$h, lanjut..."
    & $py "-u" "$root\external_index\harvest_openalex.py"
    Start-Sleep -Seconds 5   # cool-down sebelum restart
}
Write-Host "Loop harvest selesai."

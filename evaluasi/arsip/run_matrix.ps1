# run_matrix.ps1 — Jalankan daftar mode (via $env:MODES) di K=3,5,10.
# Dirancang untuk DUA TERMINAL paralel dengan mode berbeda (tanpa tabrakan file).
#
# Terminal 1:  $env:MODES="baseline,hyde";   $env:MAX_WORKERS="4"; $env:RAGAS_WORKERS="8"; .\run_matrix.ps1
# Terminal 2:  $env:MODES="cot,proposed";     $env:MAX_WORKERS="4"; $env:RAGAS_WORKERS="8"; .\run_matrix.ps1

$py    = "d:\TUGAS AKHIR\TA\.venv\Scripts\python.exe"
$dir   = "d:\TUGAS AKHIR\TA"
$res = "$dir\hasil_eksperimen"
$modes = if ($env:MODES) { $env:MODES.Split(",") } else { @("proposed") }
$Ks    = @(3, 5, 10)

$summary = @()

foreach ($mode in $modes) {
    $mode = $mode.Trim()
    foreach ($k in $Ks) {
        Write-Host ""
        Write-Host "========= MODE=$mode | TOP_K=$k =========" -ForegroundColor Cyan
        $env:PIPELINE_MODE = $mode
        $env:TOP_K = "$k"

        & $py "$dir\pipeline.py"
        if ($LASTEXITCODE -ne 0) { Write-Host "[GAGAL] pipeline $mode K=$k" -ForegroundColor Red; continue }

        & $py "$dir\evaluate.py"
        if ($LASTEXITCODE -ne 0) { Write-Host "[GAGAL] evaluate $mode K=$k" -ForegroundColor Red; continue }

        $rag = "$res\hasil_ragas_${mode}_k${k}.csv"
        $cit = "$res\hasil_ragas_${mode}_k${k}_citation.csv"
        if ((Test-Path $rag) -and (Test-Path $cit)) {
            $df = Import-Csv $rag; $c = Import-Csv $cit
            $f  = [math]::Round(($df.faithfulness    | Where-Object {$_ -ne ''} | Measure-Object -Average).Average, 4)
            $ar = [math]::Round(($df.answer_relevancy | Where-Object {$_ -ne ''} | Measure-Object -Average).Average, 4)
            $summary += [PSCustomObject]@{
                Mode = $mode; K = $k
                PrecAtK   = [math]::Round([double]$c[0].citation_precision, 4)
                RecallAtK = [math]::Round([double]$c[0].citation_recall, 4)
                HitAtK    = [math]::Round([double]$c[0].hit_at_k, 4)
                Faith     = $f; AnsRel = $ar
            }
        }
    }
}

Write-Host ""
Write-Host "============ RINGKASAN MATRIX ($($modes -join ',')) ============" -ForegroundColor Green
Write-Host ("{0,-11}{1,-4}{2,9}{3,10}{4,8}{5,8}{6,8}" -f "Mode","K","Prec@K","Recall@K","Hit@K","Faith","AnsRel")
Write-Host ("-" * 58)
foreach ($r in $summary) {
    Write-Host ("{0,-11}{1,-4}{2,9}{3,10}{4,8}{5,8}{6,8}" -f $r.Mode, $r.K, $r.PrecAtK, $r.RecallAtK, $r.HitAtK, $r.Faith, $r.AnsRel)
}
Write-Host ("=" * 58) -ForegroundColor Green

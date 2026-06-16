# run_k_variation.ps1 — Variasi nilai K (3, 5, 10) untuk SATU mode.
# Terpisah dari run_ablation.ps1. Default mode = proposed.
# Cara pakai: .\run_k_variation.ps1            (mode proposed)
#             $env:PIPELINE_MODE="baseline"; .\run_k_variation.ps1

$py   = "d:\TUGAS AKHIR\TA\.venv\Scripts\python.exe"
$dir  = "d:\TUGAS AKHIR\TA"
$res = "$dir\hasil_eksperimen"
$mode = if ($env:PIPELINE_MODE) { $env:PIPELINE_MODE } else { "proposed" }
$Ks   = @(3, 5, 10)

$env:PIPELINE_MODE = $mode
$summary = @()

foreach ($k in $Ks) {
    Write-Host ""
    Write-Host "================ MODE=$mode | TOP_K=$k ================" -ForegroundColor Cyan
    $env:TOP_K = "$k"

    & $py "$dir\pipeline.py"
    if ($LASTEXITCODE -ne 0) { Write-Host "[GAGAL] pipeline K=$k" -ForegroundColor Red; continue }

    & $py "$dir\evaluate.py"
    if ($LASTEXITCODE -ne 0) { Write-Host "[GAGAL] evaluate K=$k" -ForegroundColor Red; continue }

    $rag  = "$res\hasil_ragas_${mode}_k${k}.csv"
    $cit  = "$res\hasil_ragas_${mode}_k${k}_citation.csv"
    if ((Test-Path $rag) -and (Test-Path $cit)) {
        $df  = Import-Csv $rag
        $c   = Import-Csv $cit
        $f   = [math]::Round(($df.faithfulness    | Where-Object {$_ -ne ''} | Measure-Object -Average).Average, 4)
        $ar  = [math]::Round(($df.answer_relevancy | Where-Object {$_ -ne ''} | Measure-Object -Average).Average, 4)
        $summary += [PSCustomObject]@{
            K = $k
            PrecAtK   = [math]::Round([double]$c[0].citation_precision, 4)
            RecallAtK = [math]::Round([double]$c[0].citation_recall, 4)
            HitAtK    = [math]::Round([double]$c[0].hit_at_k, 4)
            Faith     = $f
            AnsRel    = $ar
        }
    }
}

Write-Host ""
Write-Host "============ RINGKASAN VARIASI K (mode=$mode) ============" -ForegroundColor Green
Write-Host ("{0,-5}{1,10}{2,11}{3,9}{4,9}{5,9}" -f "K","Prec@K","Recall@K","Hit@K","Faith","AnsRel")
Write-Host ("-" * 52)
foreach ($r in $summary) {
    Write-Host ("{0,-5}{1,10}{2,11}{3,9}{4,9}{5,9}" -f $r.K, $r.PrecAtK, $r.RecallAtK, $r.HitAtK, $r.Faith, $r.AnsRel)
}
Write-Host ("=" * 52) -ForegroundColor Green

# run_ablation.ps1 — Jalankan 4 mode ablation otomatis berurutan.
# Urutan: baseline → hyde → cot → proposed
# Output per mode: hasil_prediksi_{mode}.csv + hasil_ragas_{mode}.csv
# Cara pakai: .\run_ablation.ps1

$py    = "d:\TUGAS AKHIR\TA\.venv\Scripts\python.exe"
$dir   = "d:\TUGAS AKHIR\TA"
$res = "$dir\hasil_eksperimen"
$modes = @("baseline", "hyde", "cot", "proposed")

$summary = @()

foreach ($mode in $modes) {
    Write-Host ""
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host "  MODE: $($mode.ToUpper())" -ForegroundColor Cyan
    Write-Host "================================================================" -ForegroundColor Cyan

    # ── Pipeline ──────────────────────────────────────────────────────────────
    Write-Host "[1/2] Pipeline ($mode)..." -ForegroundColor Yellow
    $env:PIPELINE_MODE = $mode
    & $py "$dir\pipeline.py"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[GAGAL] pipeline.py mode=$mode (exit $LASTEXITCODE)" -ForegroundColor Red
        continue
    }

    # ── Evaluate ──────────────────────────────────────────────────────────────
    Write-Host "[2/2] Evaluate ($mode)..." -ForegroundColor Yellow
    $env:PIPELINE_MODE = $mode
    & $py "$dir\evaluate.py"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[GAGAL] evaluate.py mode=$mode (exit $LASTEXITCODE)" -ForegroundColor Red
        continue
    }

    # Baca hasil ragas + citation untuk summary
    $ragas_file = "$res\hasil_ragas_$mode.csv"
    $cite_file  = "$res\hasil_ragas_${mode}_citation.csv"
    if ((Test-Path $ragas_file) -and (Test-Path $cite_file)) {
        $df  = Import-Csv $ragas_file
        $cit = Import-Csv $cite_file
        $f   = [math]::Round(($df.faithfulness    | Where-Object {$_ -ne ''} | Measure-Object -Average).Average, 4)
        $ar  = [math]::Round(($df.answer_relevancy | Where-Object {$_ -ne ''} | Measure-Object -Average).Average, 4)
        $cpr = [math]::Round([double]$cit[0].citation_precision, 4)
        $crr = [math]::Round([double]$cit[0].citation_recall, 4)
        $hit = [math]::Round([double]$cit[0].hit_at_k, 4)
        $summary += [PSCustomObject]@{
            Mode = $mode.ToUpper(); Faithfulness = $f; AnswerRelevancy = $ar
            CitationPrec = $cpr; CitationRecall = $crr; HitAtK = $hit
        }
        Write-Host "  → F=$f  AR=$ar  CitP=$cpr  CitR=$crr  Hit=$hit" -ForegroundColor Green
    }
}

# ── Ringkasan akhir ────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "================================================================" -ForegroundColor Green
Write-Host "  RINGKASAN ABLATION STUDY" -ForegroundColor Green
Write-Host "================================================================" -ForegroundColor Green
Write-Host ("{0,-14} {1,10} {2,10} {3,10} {4,10} {5,10}" -f "Mode","Prec@K","Recall@K","Hit@K","Faith.","AnswerRel.")
Write-Host ("-" * 68)
foreach ($row in $summary) {
    Write-Host ("{0,-14} {1,10} {2,10} {3,10} {4,10} {5,10}" -f $row.Mode, $row.CitationPrec, $row.CitationRecall, $row.HitAtK, $row.Faithfulness, $row.AnswerRelevancy)
}
Write-Host "================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "File output:"
foreach ($mode in $modes) {
    Write-Host "  hasil_prediksi_$mode.csv + hasil_ragas_$mode.csv"
}

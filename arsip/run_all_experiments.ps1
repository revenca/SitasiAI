# run_all_experiments.ps1 — Satu perintah untuk SEMUA eksperimen (berurutan, aman).
#   Bagian 1: Ablation 4 mode @ K=5
#   Bagian 2: Sensitivitas K — Proposed @ K=3 dan K=10 (K=5 sudah dari Bagian 1)
# Di akhir: cetak Tabel Ablation + Tabel Variasi K.
# Cara pakai: .\run_all_experiments.ps1

$py  = "d:\TUGAS AKHIR\TA\.venv\Scripts\python.exe"
$dir = "d:\TUGAS AKHIR\TA"
$res = "$dir\hasil_eksperimen"

function Run-One($mode, $k) {
    Write-Host ""
    Write-Host "========= MODE=$mode | TOP_K=$k =========" -ForegroundColor Cyan
    $env:PIPELINE_MODE = $mode
    $env:TOP_K = "$k"
    & $py "$dir\pipeline.py"
    if ($LASTEXITCODE -ne 0) { Write-Host "[GAGAL] pipeline $mode K=$k" -ForegroundColor Red; return }
    & $py "$dir\evaluate.py"
    if ($LASTEXITCODE -ne 0) { Write-Host "[GAGAL] evaluate $mode K=$k" -ForegroundColor Red; return }
}

function Read-Result($mode, $k) {
    $rag = "$res\hasil_ragas_${mode}_k${k}.csv"
    $cit = "$res\hasil_ragas_${mode}_k${k}_citation.csv"
    if (-not ((Test-Path $rag) -and (Test-Path $cit))) { return $null }
    $df = Import-Csv $rag; $c = Import-Csv $cit
    return [PSCustomObject]@{
        Mode = $mode; K = $k
        PrecAtK   = [math]::Round([double]$c[0].citation_precision, 4)
        RecallAtK = [math]::Round([double]$c[0].citation_recall, 4)
        HitAtK    = [math]::Round([double]$c[0].hit_at_k, 4)
        Faith     = [math]::Round(($df.faithfulness    | Where-Object {$_ -ne ''} | Measure-Object -Average).Average, 4)
        AnsRel    = [math]::Round(($df.answer_relevancy | Where-Object {$_ -ne ''} | Measure-Object -Average).Average, 4)
    }
}

# ─── BAGIAN 1: ABLATION 4 MODE @ K=5 ───────────────────────────
Write-Host "`n############ BAGIAN 1: ABLATION (4 mode @ K=5) ############" -ForegroundColor Magenta
foreach ($m in @("baseline","hyde","cot","proposed")) { Run-One $m 5 }

# ─── BAGIAN 2: VARIASI K (Proposed @ K=3, 10) ──────────────────
Write-Host "`n############ BAGIAN 2: VARIASI K (Proposed @ K=3,10) ############" -ForegroundColor Magenta
foreach ($k in @(3,10)) { Run-One "proposed" $k }

# ─── TABEL 1: ABLATION ─────────────────────────────────────────
Write-Host "`n`n================ TABEL 1 — ABLATION (K=5) ================" -ForegroundColor Green
Write-Host ("{0,-11}{1,9}{2,10}{3,8}{4,8}{5,8}" -f "Mode","Prec@K","Recall@K","Hit@K","Faith","AnsRel")
Write-Host ("-" * 54)
foreach ($m in @("baseline","hyde","cot","proposed")) {
    $r = Read-Result $m 5
    if ($r) { Write-Host ("{0,-11}{1,9}{2,10}{3,8}{4,8}{5,8}" -f $r.Mode, $r.PrecAtK, $r.RecallAtK, $r.HitAtK, $r.Faith, $r.AnsRel) }
}

# ─── TABEL 2: VARIASI K (Proposed) ─────────────────────────────
Write-Host "`n================ TABEL 2 — VARIASI K (Proposed) ================" -ForegroundColor Green
Write-Host ("{0,-5}{1,9}{2,10}{3,8}{4,8}{5,8}" -f "K","Prec@K","Recall@K","Hit@K","Faith","AnsRel")
Write-Host ("-" * 48)
foreach ($k in @(3,5,10)) {
    $r = Read-Result "proposed" $k
    if ($r) { Write-Host ("{0,-5}{1,9}{2,10}{3,8}{4,8}{5,8}" -f $r.K, $r.PrecAtK, $r.RecallAtK, $r.HitAtK, $r.Faith, $r.AnsRel) }
}
Write-Host ("=" * 48) -ForegroundColor Green

# ─── TABEL 3: PER TOPIK (Proposed @ K=5) ───────────────────────
Write-Host "`n================ TABEL 3 — PER TOPIK (Proposed @ K=5) ================" -ForegroundColor Green
$topicFile = "$res\hasil_ragas_proposed_k5_topic.csv"
if (Test-Path $topicFile) {
    $t = Import-Csv $topicFile
    Write-Host ("{0,-18}{1,5}{2,9}{3,10}{4,8}{5,8}" -f "Kategori","N","Prec@K","Recall@K","Hit@K","Faith")
    Write-Host ("-" * 58)
    $strong = 0
    foreach ($row in $t) {
        Write-Host ("{0,-18}{1,5}{2,9}{3,10}{4,8}{5,8}" -f $row.kategori, $row.n, $row.precision_at_k, $row.recall_at_k, $row.hit_at_k, $row.faithfulness)
        if ([double]$row.hit_at_k -ge 0.8) { $strong++ }
    }
    Write-Host ("-" * 57)
    Write-Host ("Kategori dengan Hit@K >= 0.8 : {0} / {1} topik" -f $strong, $t.Count) -ForegroundColor Yellow
}
Write-Host ("=" * 57) -ForegroundColor Green
Write-Host "`nSELESAI — 3 tabel siap untuk skripsi." -ForegroundColor Green

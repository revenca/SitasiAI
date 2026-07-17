# run_rerun_2mode.ps1 — Rerun BERSIH 5 run: HyDE vs Tanpa-HyDE (CoT TETAP nyala di keduanya).
# CoT adalah komponen tetap arsitektur (menghasilkan sitasi) — yang di-toggle hanya HyDE.
#   Tanpa HyDE = mode "cot"     (embed paragraf langsung + CoT)
#   HyDE       = mode "proposed"(HyDE 0.7 -> embed + CoT)
# Bug silent HyDE-fallback sudah diperbaiki: kolom hyde_fallback + laporan di akhir run.
# RESUMABLE: skip (kondisi,run) yang file RAGAS-citation-nya sudah ada.
# Tanpa seed => 5 run independen (HyDE temp 0.7 sampling beda tiap run; CoT temp 0.2).
#
# Jalankan:  .\run_rerun_2mode.ps1   (sebaiknya matikan backend web dulu agar GPU bebas)

$root = "d:\TUGAS AKHIR\TA"
$py   = "$root\.venv\Scripts\python.exe"
$res  = "$root\hasil_eksperimen"
Set-Location $root

# 2 kondisi standar (HyDE 0.7 / CoT 0.2 / K=5 / words 100-150)
$conds = @(
    @{ tag="final_nohyde"; mode="cot";      hyde="0.7"; cot="0.2" },
    @{ tag="final_hyde";   mode="proposed"; hyde="0.7"; cot="0.2" }
)
$k = "5"; $words = "100-150"; $runs = 5
$total = $conds.Count * $runs; $done = 0; $ran = 0

foreach ($run in 1..$runs) {
    foreach ($c in $conds) {
        $done++
        $rtag    = "$($c.tag)_r$run"
        $ragasOk = "$res\hasil_ragas_${rtag}_citation.csv"
        if (Test-Path $ragasOk) {
            Write-Host "[$done/$total] SKIP (sudah ada): $rtag" -ForegroundColor DarkGray
            continue
        }
        Write-Host "`n[$done/$total] === $($c.tag) run $run  (mode=$($c.mode) K=$k HyDE=$($c.hyde) CoT=$($c.cot)) ===" -ForegroundColor Cyan

        $env:PIPELINE_MODE = $c.mode
        $env:TOP_K         = $k
        $env:HYDE_TEMP     = $c.hyde
        $env:COT_TEMP      = $c.cot
        $env:HYDE_WORDS    = $words
        $env:RUN_TAG       = $rtag

        & $py pipeline.py
        if ($LASTEXITCODE -ne 0) { Write-Host "pipeline GAGAL di $rtag - berhenti." -ForegroundColor Red; exit 1 }

        $env:PRED_FILE  = "hasil_eksperimen\hasil_prediksi_$($c.mode)_k${k}_${rtag}.csv"
        $env:RAGAS_FILE = "hasil_eksperimen\hasil_ragas_${rtag}.csv"
        & $py evaluate.py
        if ($LASTEXITCODE -ne 0) {
            Write-Host "evaluate GAGAL di $rtag (kemungkinan saldo DeepSeek habis) - berhenti rapi. Jalankan ulang script untuk lanjut." -ForegroundColor Red
            exit 2
        }
        $ran++
        Write-Host "----- selesai: $rtag ($ran run baru) -----" -ForegroundColor Green
    }
}
Write-Host "`nSEMUA $total RUN SELESAI ($ran baru)." -ForegroundColor Green
Write-Host "Lanjut analisis: agregasi + grafik (Baseline vs HyDE)." -ForegroundColor Yellow

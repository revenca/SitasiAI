# run_multirun.ps1 — Jalankan 14 konfigurasi x 3 run independen (estimasi variansi mean±std).
# RESUMABLE: lewati (config,run) yang file RAGAS-nya sudah ada.
# Independensi: tanpa set seed (temperature>0 => sampling beda tiap run).
# Berhenti rapi jika evaluate gagal (kemungkinan saldo DeepSeek habis).
#
# Jalankan:  .\run_multirun.ps1     (matikan backend web dulu agar GPU bebas)

$root = "d:\TUGAS AKHIR\TA"
$py   = "$root\.venv\Scripts\python.exe"
$res  = "$root\hasil_eksperimen"
Set-Location $root

# tag, mode, K, HYDE_TEMP, COT_TEMP, HYDE_WORDS
$configs = @(
    @{ tag="baseline";     mode="baseline"; k="5";  hyde="0.7"; cot="0.2"; words="100-150" },
    @{ tag="hyde";         mode="hyde";     k="5";  hyde="0.7"; cot="0.2"; words="100-150" },
    @{ tag="cot";          mode="cot";      k="5";  hyde="0.7"; cot="0.2"; words="100-150" },
    @{ tag="proposed_k5";  mode="proposed"; k="5";  hyde="0.7"; cot="0.2"; words="100-150" },
    @{ tag="proposed_k3";  mode="proposed"; k="3";  hyde="0.7"; cot="0.2"; words="100-150" },
    @{ tag="proposed_k10"; mode="proposed"; k="10"; hyde="0.7"; cot="0.2"; words="100-150" },
    @{ tag="hydetemp02";   mode="proposed"; k="5";  hyde="0.2"; cot="0.2"; words="100-150" },
    @{ tag="hydetemp04";   mode="proposed"; k="5";  hyde="0.4"; cot="0.2"; words="100-150" },
    @{ tag="cottemp02";    mode="proposed"; k="5";  hyde="0";   cot="0.2"; words="100-150" },
    @{ tag="cottemp05";    mode="proposed"; k="5";  hyde="0";   cot="0.5"; words="100-150" },
    @{ tag="cottemp07";    mode="proposed"; k="5";  hyde="0";   cot="0.7"; words="100-150" },
    @{ tag="words50";      mode="proposed"; k="5";  hyde="0.7"; cot="0.2"; words="50-80"   },
    @{ tag="words200";     mode="proposed"; k="5";  hyde="0.7"; cot="0.2"; words="200-250" }
)

$total = $configs.Count * 3; $done = 0; $ran = 0
foreach ($c in $configs) {
    foreach ($run in 1, 2, 3) {
        $done++
        $rtag    = "$($c.tag)_r$run"
        $ragasOk = "$res\hasil_ragas_${rtag}_citation.csv"
        if (Test-Path $ragasOk) {
            Write-Host "[$done/$total] SKIP (sudah ada): $rtag" -ForegroundColor DarkGray
            continue
        }
        Write-Host "`n[$done/$total] === $($c.tag) run $run  (mode=$($c.mode) K=$($c.k) HyDE=$($c.hyde) CoT=$($c.cot) words=$($c.words)) ===" -ForegroundColor Cyan

        $env:PIPELINE_MODE = $c.mode
        $env:TOP_K         = $c.k
        $env:HYDE_TEMP     = $c.hyde
        $env:COT_TEMP      = $c.cot
        $env:HYDE_WORDS    = $c.words
        $env:RUN_TAG       = $rtag

        & $py pipeline.py
        if ($LASTEXITCODE -ne 0) { Write-Host "pipeline GAGAL di $rtag — berhenti." -ForegroundColor Red; exit 1 }

        $env:PRED_FILE  = "hasil_eksperimen\hasil_prediksi_$($c.mode)_k$($c.k)_${rtag}.csv"
        $env:RAGAS_FILE = "hasil_eksperimen\hasil_ragas_${rtag}.csv"
        & $py evaluate.py
        if ($LASTEXITCODE -ne 0) {
            Write-Host "evaluate GAGAL di $rtag (kemungkinan saldo DeepSeek habis) — berhenti rapi." -ForegroundColor Red
            Write-Host "Sudah selesai: $ran konfigurasi-run. Jalankan ulang script ini untuk melanjutkan." -ForegroundColor Yellow
            exit 2
        }
        $ran++
        Write-Host "----- selesai: $rtag ($ran run baru) -----" -ForegroundColor Green
    }
}
Write-Host "`nSEMUA $total KONFIGURASI-RUN SELESAI." -ForegroundColor Green
Write-Host "Lanjut: & '$py' aggregate_multirun.py" -ForegroundColor Yellow

$root="d:\TUGAS AKHIR\TA"; $py="$root\.venv\Scripts\python.exe"; Set-Location $root
$env:HYDE_TEMP="0.7"; $env:COT_TEMP="0.2"; $env:PIPELINE_MODE="proposed"; $env:TOP_K="5"
# 50-80 @ HyDE 0.7
$env:HYDE_WORDS="50-80"; $env:RUN_TAG="w50_t07"
& $py pipeline.py; if($LASTEXITCODE -ne 0){exit 1}
$env:PRED_FILE="hasil_eksperimen\hasil_prediksi_proposed_k5_w50_t07.csv"; $env:RAGAS_FILE="hasil_eksperimen\hasil_ragas_w50_t07.csv"
& $py evaluate.py; if($LASTEXITCODE -ne 0){exit 2}
Write-Host "=== w50_t07 SELESAI ==="
# 200-250 @ HyDE 0.7
$env:HYDE_WORDS="200-250"; $env:RUN_TAG="w200_t07"
& $py pipeline.py; if($LASTEXITCODE -ne 0){exit 1}
$env:PRED_FILE="hasil_eksperimen\hasil_prediksi_proposed_k5_w200_t07.csv"; $env:RAGAS_FILE="hasil_eksperimen\hasil_ragas_w200_t07.csv"
& $py evaluate.py; if($LASTEXITCODE -ne 0){exit 2}
Write-Host "=== w200_t07 SELESAI === SEMUA BERES"

# Evaluasi — Skripsi (korpus 100 paper)

Folder ini berisi SELURUH artefak evaluasi tesis: pipeline eksperimen, skrip skoring,
hasil multi-run, uji signifikansi, ground truth, dan dokumen analisis. Terpisah dari
aplikasi web (root repo) — web TIDAK bergantung pada folder ini saat runtime
(kecuali `output_teks_clean/` yang dipakai sekali oleh skrip seeding backend).

## Isi
| Path | Keterangan |
|---|---|
| `pipeline.py`, `evaluate.py` | Pipeline eksperimen (HyDE+SPECTER2+CoT) & skoring RAGAS + metrik sitasi |
| `indexing.py`, `indexing_abstract.py`, `extract_pdf_clean.py` | Bangun index chunk/abstrak dari teks bersih |
| `score_*.py`, `run_*.ps1` | Skrip skoring & runner eksperimen (jalankan DARI folder ini) |
| `hasil_eksperimen/` | Semua CSV prediksi & RAGAS per-run |
| `results_tesis/` | Tabel siap-tesis: uji t + Bonferroni, ablasi, lampiran per-kueri |
| `results_fresh/`, `results_*/` | Rekap hasil |
| `dataset_v1.csv`, `ground_truth_human.csv`, `Ground_Truth/` | Dataset & ground truth (144 kueri, label manusia) |
| `docs/` | Analisis kualitatif, batasan prompting, tabel Bab 4 |
| `output_teks_clean/`, `Data (paper)/` | Teks paper bersih & PDF sumber (gitignored) |
| `faiss_index_*_clean.bin`, `metadata_*_clean.json` | Index evaluasi (gitignored) |
| `arsip/` | Skrip & hasil lama (jejak pengembangan) |

## Menjalankan ulang eksperimen
```powershell
cd "d:\TUGAS AKHIR\TA\evaluasi"
.\run_phyde_endtoend.ps1     # contoh: baseline vs proper HyDE 5-run
```
Butuh `.env` di root repo (OPENROUTER_API_KEY + DEEPSEEK_API_KEY).

## Temuan utama (jujur)
Baseline vs HyDE TIDAK berbeda signifikan pada seluruh metrik (paired t-test n=144,
koreksi Bonferroni: 0/5 metrik signifikan). Kontribusi nyata: SPECTER2 (Recall ~0,91),
CoT (+0,059 faithfulness), pembersihan teks. Detail: `results_tesis/` dan `docs/`.

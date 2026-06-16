# Sistem Citation Recommendation — HyDE + CoT + RAG (SciBERT)

Sistem rekomendasi sitasi untuk skripsi S1. Menerima paragraf dari paper ilmiah,
lalu merekomendasikan paper referensi yang relevan beserta teks sitasinya
menggunakan query expansion (HyDE + CoT) dan vector embeddings (SciBERT).

## Arsitektur

```
Paragraf sumber
   │
   ├─[HyDE]──────► GPT-4o-mini hasilkan hypothetical abstract
   │                     │
   │              SciBERT embed (768-dim, CLS, L2-norm)
   │                     │
   ├─[RETRIEVAL]──► FAISS IndexFlatIP → top-5 chunk (exclude paper sama)
   │                     │
   └─[CoT]────────► GPT-4o-mini pilih referensi terbaik + tulis sitasi
                         │
                  hasil_prediksi.csv
                         │
   [EVALUASI]──────► RAGAS + Claude Sonnet 4.5 (judge) → hasil_ragas.csv
```

| Komponen | Teknologi |
|---|---|
| Embedding | `allenai/scibert_scivocab_uncased` (768-dim, CLS token) |
| Generator (HyDE + CoT) | GPT-4o-mini via OpenRouter |
| Judge (RAGAS) | Claude Sonnet 4.5 via OpenRouter (beda vendor → hindari self-bias) |
| Vector DB | FAISS `IndexFlatIP` (cosine via inner product) |

## Setup

```powershell
# 1. Aktifkan virtual environment
& "d:\TUGAS AKHIR\TA\.venv\Scripts\Activate.ps1"
# (jika "running scripts is disabled": Set-ExecutionPolicy -Scope CurrentUser RemoteSigned)

# 2. Install dependencies (jika belum)
pip install -r requirements.txt

# 3. Setup API key
Copy-Item .env.example .env   # lalu edit .env, isi OPENROUTER_API_KEY
```

## Urutan Menjalankan

| Step | Perintah | Output | Estimasi |
|---|---|---|---|
| 0 | `python extract_pdf.py` | `output_teks/` (100 .txt) | ~2 menit |
| 1 | `python indexing.py` | `faiss_index.bin`, `metadata.json` | 5–20 menit (+unduh SciBERT 440MB) |
| 2 | `python pipeline.py` | `hasil_prediksi.csv` | ~2–3 jam (API) |
| 3 | `python evaluate.py` | `hasil_ragas.csv` | ~1 jam (API) |

```powershell
python extract_pdf.py
python indexing.py
python pipeline.py
python evaluate.py
```

## Prasyarat per Step

- **Step 1** hanya butuh `output_teks/` (SciBERT lokal, tanpa API/internet selain unduh model).
- **Step 2 & 3** butuh `dataset_v1.csv` di root + kredit OpenRouter cukup.

## File Penting

| File | Keterangan |
|---|---|
| `extract_pdf.py` | Ekstrak PDF → teks |
| `indexing.py` | Chunk + embed SciBERT → FAISS |
| `pipeline.py` | HyDE + CoT + RAG |
| `evaluate.py` | Evaluasi RAGAS |
| `dataset_v1.csv` | Source paragraph + reference (**belum ada — wajib disiapkan**) |
| `Ground_Truth/citation_checker_data.csv` | 886 citation, label 7 human evaluator |
| `.env` | API key (jangan di-commit) |

## Parameter Chunking (indexing.py)

- `MAX_WORDS = 150`, `OVERLAP = 30`, `MIN_WORDS = 80`

## Ground Truth (evaluate.py)

- Label valid bila **≥ 4 dari 7** human evaluator (V_H1–V_H7) menyatakan TRUE.
- Dari 886 citation: **334 valid**, **552 tidak valid**.

## Metrik RAGAS

| Metrik | Mengukur | Butuh ground truth? |
|---|---|---|
| Faithfulness | Sitasi didukung konteks (tidak halusinasi) | Tidak |
| Answer Relevancy | Sitasi relevan dengan paragraf sumber | Tidak |
| Context Precision | Presisi chunk hasil retrieval | Ya |
| Context Recall | Kelengkapan chunk hasil retrieval | Ya |

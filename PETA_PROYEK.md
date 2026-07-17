# Peta Proyek — SitasiAI (TA)

Sistem rekomendasi sitasi berbasis RAG: **HyDE (opsional) → SPECTER2 → FAISS → CoT (GPT-4o-mini)**, dievaluasi dengan **RAGAS** (judge DeepSeek) + metrik retrieval (Recall/Hit@K/MRR/Precision paper-level).

---

## 1. Pipeline Inti

| File | Fungsi |
|---|---|
| `pipeline.py` | Mesin utama: HyDE generate (N dok + rata-rata + query emb) → embed SPECTER2 → retrieval FAISS → CoT sitasi (GPT-4o-mini). Env: `HYDE_N`, `HYDE_INCLUDE_QUERY`, `HYDE_TEMP`, `RETRIEVAL_ONLY`, `FAISS_INDEX_FILE`, `METADATA_FILE`. |
| `extract_pdf_clean.py` | Ekstraksi PDF dengan **deteksi kolom** (gutter detection) → `output_teks_clean/`. Perbaikan teks acak (interleaving kolom). |
| `indexing.py` | Bangun index **chunk-based** dari `output_teks_clean/` → `faiss_index_chunk_clean.bin` + `metadata_chunk_clean.json` (9.473 vektor). |
| `indexing_abstract.py` | Bangun index **judul+abstrak** (1 vektor/paper) → `faiss_index_abstract_clean.bin` + `metadata_abstract_clean.json` (100 vektor). |
| `evaluate.py` | Skoring RAGAS (Faithfulness, Answer Relevancy) + metrik sitasi (Precision paper-level, Recall, Hit@K). Env: `METADATA_FILE`. |

---

## 2. Skrip Skoring (`score_*.py`)

| File | Fungsi |
|---|---|
| `score_retrieval.py` | Metrik retrieval murni (Recall/Hit/MRR) dari hasil prediksi. |
| `score_variasi_k.py` | Skor per nilai K (3/5/10), multi-run. |
| `score_ablation.py` | Ablasi komponen (baseline vs HyDE). |
| `score_faithfulness.py` | Skor faithfulness end-to-end. |
| `score_sensitivity_hyde.py` | Sensitivitas HyDE (temperature, panjang abstrak). |
| `score_index_compare.py` | Bandingkan index chunk vs abstrak. |
| `score_phyde_retrieval.py` | Skor proper-HyDE (retrieval-only). |

---

## 3. Skrip Run (`run_*.ps1`)

| File | Fungsi |
|---|---|
| `run_build_clean_indexes.ps1` | Bangun ulang kedua index dari teks bersih. |
| `run_variasi_k.ps1` | Eksperimen variasi K, multi-run. |
| `run_fulltest_cleanchunk.ps1` / `run_fulltest_cleanabs.ps1` | Full test index chunk / abstrak. |
| `run_baseline_nocot_cleanchunk.ps1` | Baseline tanpa CoT. |
| `run_phyde_endtoend.ps1` / `run_phyde_retrieval.ps1` | Proper-HyDE end-to-end / retrieval. |
| `run_sensitivity_hyde.ps1` | Sensitivitas HyDE. |
| `run_compare_indexes_specter.ps1` | Bandingkan index (SPECTER2). |
| `start.ps1` | Jalankan backend (:8000) + frontend (:5173) sekaligus. |

---

## 4. Backend Web (`backend/`)

| File | Fungsi |
|---|---|
| `api.py` | REST API FastAPI: Auth, Papers, `/recommend`, `/ask`, `/history`. HyDE+CoT **selalu aktif**. |
| `rag_engine.py` | Adaptor pipeline untuk web; baca data dari `backend/data/`. Fallback tahun `n.d.`. |
| `generate_paper_meta.py` | Ekstrak penulis+tahun tiap paper → `backend/data/paper_meta.json`. |
| `seed_papers.py` | Isi tabel papers ke DB dari metadata + teks bersih. |
| `auth.py` / `models.py` / `database.py` | JWT auth / model SQLAlchemy / koneksi DB. |
| `data/` | `faiss_index.bin`, `metadata.json`, `paper_meta.json`, `paper_metadata.json` (dipakai web). |

---

## 5. Frontend (`frontend-react/`)

| Path | Fungsi |
|---|---|
| `src/pages/Home.jsx` | Chat UI: tanya-jawab / rekomendasi sitasi. Toggle HyDE/CoT **dihapus**; opsi "Jumlah paper" (3/5/10). |
| `src/api.js`, `src/chat.jsx`, `src/components/` | Klien API, konteks chat, ikon & logo. |
| `frontend/` (lama) | Versi frontend lawas (tidak dipakai). |

---

## 6. Data & Ground Truth

| File | Fungsi |
|---|---|
| `dataset_v1.csv` | Dataset kueri sumber. |
| `ground_truth_human.csv` | Ground truth 100% human (mayoritas ≥4/7 evaluator). 144 kueri, ~1,18 gold paper unik/kueri. |
| `Ground_Truth/citation_checker_data.csv` | Data mentah checker sitasi (Pratama). |
| `extracted_abstracts.csv` | Abstrak hasil ekstraksi heuristik. |
| `metadata_chunk_clean.json` / `metadata_abstract_clean.json` | Metadata index chunk / abstrak. |
| `faiss_index_chunk_clean.bin` / `faiss_index_abstract_clean.bin` | Index FAISS chunk / abstrak (bersih). |
| `output_teks_clean/` | Teks paper hasil ekstraksi bersih (100 paper). |
| `Data (paper)/` | PDF sumber (gitignored). |

---

## 7. Hasil Eksperimen

| Path | Isi |
|---|---|
| `hasil_eksperimen/` | 538 file `hasil_prediksi_*.csv` (semua run: baseline/HyDE, K, index, multi-run). |
| `results_fresh/` | Rekap bersih: `ablation_cleanchunk.csv`, `faithfulness_*.csv`, `variasi_k_lengkap.csv`, `sensitivitas_hyde.csv`. |
| `results_tesis/` | Tabel siap-tesis: `ablasi_perrun.csv`, `variasi_k_perrun.csv`, `parameter_indexing.csv`. |
| `results_index_compare/` | `specter_index_compare.csv` (chunk vs abstrak). |
| `results_retrieval/` | `proper_hyde_vs_specter.csv`, `retrieval_specter_vs_hyde.csv`. |
| `docs/` | `tabel_final_bab4.md`, `tabel_final_bab4_multirun.md`. |

---

## 8. Arsip (`arsip/`)

Skrip diagnostik lama (`diag_*.py`), ekspor lama (`export_*.py`, `compare_*.py`), index lama (`faiss_index_abstract.bin`, `faiss_index_word150.bin`), teks kotor (`output_teks/`), ground truth lama. **Tidak dipakai lagi**, disimpan untuk jejak.

---

## Ringkasan Temuan (jujur)

- **Kontribusi nyata:** vector embedding SPECTER2 (Recall ~0,91), **CoT** (+0,066 faithfulness), **pembersihan teks** (+0,086 faithfulness — pendorong terbesar).
- **HyDE = null result** untuk rekomendasi sitasi di korpus ini: precision paper-level naik tipis (0,688→0,713) **hanya karena penyempitan jaring** (penyebut mengecil), tetapi Recall/Hit@K/MRR **turun**.
- Konfigurasi terbaik: **SPECTER2 + CoT + teks bersih, tanpa HyDE**.

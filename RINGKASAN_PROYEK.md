# Ringkasan Proyek — Sistem Rekomendasi Sitasi
**Judul:** Pembuatan Sitasi Paper Menggunakan LLM Berbasis Query Expansion dan Vector Embeddings  
**Mahasiswa:** Dwiyana Yudha Prawira (5025221230) — Teknik Informatika ITS

---

## Arsitektur Sistem Final

```
Paragraf sumber (dari ground_truth_final.csv, ground_truth==1)
        ↓ [Query Expansion — tergantung mode]
   Embed SPECTER2 (allenai/specter2_base + proximity adapter)
        ↓
   FAISS IndexFlatIP → top-5 chunk (exclude paper sama)
        ↓ [Generation — tergantung mode]
   citation_text
        ↓
   Evaluasi: RAGAS (Faith + AR) + Citation Metrics
```

---

## Konfigurasi Final

| Komponen | Nilai |
|---|---|
| Embedding encoder | `allenai/specter2_base` + proximity adapter |
| Chunking | Proposition (512 char, RecursiveCharacterTextSplitter) |
| Vector DB | FAISS IndexFlatIP (cosine via L2-norm) |
| TOP_K | 5 |
| Generator (HyDE + CoT) | GPT-4o-mini via OpenRouter |
| Judge RAGAS | DeepSeek (`deepseek-chat`) via api.deepseek.com |
| Ground Truth | `ground_truth_final.csv` (Checker A-G ≥4/7, 271 valid, 104 paragraf gold) |
| RAGAS versi | 0.4.3 (patch vertexai) |

---

## Hasil Ablation Final (SPECTER2 + proposition, N=104)

| Mode | Faithfulness | Answer Rel. | Cit. Precision | Cit. Recall | Hit@K |
|---|---|---|---|---|---|
| **Baseline** | 0.4206 | **0.8956** | **0.4240** | **0.7317** | **0.7788** |
| HyDE | 0.4317 | **0.9255** | 0.3962 | 0.7010 | 0.7404 |
| CoT | 0.4054 | 0.8713 | 0.4202 | 0.7269 | 0.7692 |
| Proposed (HyDE+CoT) | 0.3892 | 0.8828 | 0.3861 | 0.6577 | 0.6923 |

**Sistem terbaik = Baseline** (embed source langsung, generate simple).

---

## File Output

| File | Isi |
|---|---|
| `hasil_prediksi_{mode}.csv` | Prediksi per mode (4 file) |
| `hasil_ragas_{mode}.csv` | Skor RAGAS per baris |
| `hasil_ragas_{mode}_citation.csv` | Citation metrics agregat |
| `faiss_index.bin` | FAISS index (SPECTER2 + proposition) |
| `metadata.json` | Mapping chunk → paper title |
| `ground_truth_final.csv` | GT resmi (sama dengan TA-BGELarge) |

---

## Urutan Menjalankan

```powershell
# Aktifkan venv
& "d:\TUGAS AKHIR\TA\.venv\Scripts\Activate.ps1"

# 1. Ekstrak PDF (sudah selesai)
python extract_pdf.py

# 2. Bangun index
python indexing.py

# 3. Ablation 4 mode otomatis
.\run_ablation.ps1

# Atau manual per mode:
$env:PIPELINE_MODE="baseline"
python pipeline.py
python evaluate.py
```

---

## Metrik Evaluasi (menjawab RM #3)

| Metrik | Jenis | Tool | Mengukur |
|---|---|---|---|
| **Faithfulness** | RAGAS + LLM judge | DeepSeek | Sitasi tidak halusinasi |
| **Answer Relevancy** | RAGAS + LLM judge | DeepSeek | Sitasi relevan dengan paragraf |
| **Citation Precision** | Paper-level (gratis) | Lokal | Presisi retrieval paper |
| **Citation Recall** | Paper-level (gratis) | Lokal | Recall retrieval paper |
| **Hit@K** | Paper-level (gratis) | Lokal | Paper gold masuk top-K |

---

## Perbandingan SPECTER vs SPECTER2 + proposition

| Encoder + Chunking | CitRecall | Hit@K | AR |
|---|---|---|---|
| SPECTER + 150-kata | ~0.43 | ~0.47 | ~0.77 |
| **SPECTER2 + proposition** | **0.73** | **0.78** | **0.90** |

---

## Temuan Penting

1. **SPECTER2 + proposition** menaikkan Citation Recall drastis (0.43 → 0.73)
2. **HyDE merusak** dengan SPECTER (recall turun), tapi **membantu AR** dengan SPECTER2
3. **Baseline terbaik** untuk SPECTER2 — SPECTER2 sudah cukup citation-aware tanpa query expansion
4. **Chunking 150-kata** terbaik untuk SPECTER; **proposition** terbaik untuk SPECTER2
5. **CoT tidak membantu** dengan SPECTER2 (berbeda dari SPECTER)

---

## Project Terkait

| Project | Path | Keterangan |
|---|---|---|
| **TA (ini)** | `d:\TUGAS AKHIR\TA` | SPECTER2 + proposition + FAISS |
| **TA-BGELarge** | `d:\TUGAS AKHIR\TA-BGELarge` | BGE-Large + ChromaDB + reranker (sistem utama) |

GT sama: `ground_truth_final.csv` (Checker A-G, 271 valid, 104 paragraf gold)

---

## API & Biaya

| Service | Untuk | Estimasi per ablation |
|---|---|---|
| OpenRouter (GPT-4o-mini) | HyDE + CoT generation | ~$0.30-0.50 |
| DeepSeek (deepseek-chat) | RAGAS judge | ~$0.30-0.50 |
| SPECTER2 embedding | Lokal (GPU RTX 4070) | Gratis |

---

*Dibuat: 2026-05-31*

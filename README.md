# SitasiAI — Sistem Rekomendasi Sitasi Berbasis LLM & Vector Embeddings

**Judul TA:** Pembuatan Sitasi Paper Menggunakan LLM Berbasis Query Expansion dan Vector Embeddings
**Mahasiswa:** Dwiyana Yudha Prawira (5025221230) — Teknik Informatika, ITS

Aplikasi web yang merekomendasikan sitasi untuk sebuah klaim/paragraf akademik. Menggabungkan
**query expansion (HyDE)**, **embedding ilmiah SPECTER2**, **retrieval FAISS/pgvector**, dan
**LLM (Chain-of-Thought)** untuk memilih & menyusun sitasi, dengan penjaga anti-halusinasi.

> Aplikasi live (jaringan ITS): **https://senopati.its.ac.id/sitasi-ai/**

---

## Fitur

- **Buat sitasi** — tempel satu klaim → 1 sitasi terbaik; tempel abstrak/paragraf → sitasi per kalimat.
- **Cari paper** — pencarian topik hybrid: korpus lokal 163k (OpenAlex) + live Semantic Scholar.
- **Penjaga kualitas** — verifikasi relevansi (anti "maksa/ganti klaim"), filter paper tak-spesifik,
  cap sitasi per paper, preferensi kebaruan.
- **Tanpa login** — riwayat chat per-perangkat, disinkron ke server (kode pemulihan).

## Arsitektur

```
        ┌─ web (React + nginx) ─┐   ┌─ api (FastAPI) ──────────┐   ┌─ db ─────────┐
user →  │  SPA + reverse-proxy  │→  │ HyDE → SPECTER2 → FAISS   │→  │ PostgreSQL   │
        │  /api                 │   │ → CoT → verifikasi        │   │ + pgvector   │
        └───────────────────────┘   └──────────────────────────┘   └──────────────┘
                                       ↕ Semantic Scholar / OpenAlex (live)
```

| Komponen | Teknologi |
|---|---|
| Embedding | `allenai/specter2_base` + adapter proximity (CLS, 768-dim, L2-norm) |
| Vector DB | FAISS IndexFlatIP (fallback) / PostgreSQL + pgvector |
| LLM chain | Groq (llama-3.3-70b) → OpenRouter (GPT-4o-mini) → DeepSeek |
| Backend | FastAPI (Python 3.11) |
| Frontend | React 18 + Vite |
| Deploy | Docker Compose (web + api + db) |

## Struktur repo

| Path | Isi |
|---|---|
| `backend/` | API FastAPI, RAG engine, model DB, migrasi pgvector |
| `frontend-react/` | Aplikasi React (Vite) + Dockerfile + nginx |
| `external_index/` | Index korpus 163k (OpenAlex) + skrip harvest/embed *(data gitignored — lihat Release)* |
| `evaluasi/` | **Seluruh artefak evaluasi tesis** (pipeline, ground truth, hasil, analisis) — lihat `evaluasi/README.md` |
| `docker-compose.yml`, `Dockerfile` | Orkestrasi kontainer |
| `DEPLOY.md` | Panduan deploy lengkap ke server |
| `requirements.txt` | Dependensi Python (versi dikunci) |

> Berkas data besar (index FAISS, dataset) **tidak masuk git** (>100 MB). Tersedia sebagai
> **GitHub Release** `data-v1` atau lihat lampiran Drive.

## Menjalankan

### A. Produksi (Docker — direkomendasikan)
Lihat **[DEPLOY.md](DEPLOY.md)** untuk langkah lengkap. Ringkas:
```bash
git clone https://github.com/revenca/SitasiAI.git && cd SitasiAI
# unduh data index dari Release data-v1 (lihat DEPLOY.md FASE 2b)
nano .env                 # isi API key (template di DEPLOY.md FASE 2c)
docker compose up -d --build
# akses http://<server>/
```

### B. Pengembangan lokal
```powershell
# Backend
python -m venv .venv ; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn backend.api:app --reload --port 8003

# Frontend (terminal lain)
cd frontend-react ; npm install ; npm run dev
# buka http://localhost:5173
```

`.env` minimal:
```
AUTH_DISABLED=1
OPENROUTER_API_KEY=...
GROQ_API_KEY=...
DEEPSEEK_API_KEY=...
S2_API_KEY=...
```

## Evaluasi tesis

Seluruh eksperimen, ground truth, hasil multi-run, uji signifikansi, dan analisis ada di
**[`evaluasi/`](evaluasi/)** (lihat `evaluasi/README.md`).

**Temuan utama (jujur):** kontribusi nyata dari **SPECTER2** (Citation Recall ~0,73–0,91) dan
pembersihan teks. Baseline vs HyDE **tidak berbeda signifikan** (paired t-test n=144, koreksi
Bonferroni: 0/5 metrik signifikan) — dilaporkan apa adanya.

## Lisensi & etika

Proyek akademik (Tugas Akhir ITS). PDF paper hanya diproses lokal (tidak dikirim ke layanan
eksternal). API key disimpan di `.env` (tidak di-commit).

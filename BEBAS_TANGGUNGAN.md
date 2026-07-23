# Checklist Bebas Tanggungan — SitasiAI (TA)

**Mahasiswa:** Dwiyana Yudha Prawira · **NRP:** 5025221230 · **Tahun lulus:** `<isi>`
**Judul:** Pembuatan Sitasi Paper Menggunakan LLM Berbasis Query Expansion dan Vector Embeddings

Kirim **link Google Drive** (akses: "Siapa saja yang memiliki link → Pelihat") berisi 9 folder di bawah.

---

## Status 9 item

| # | Item | Status | Sumber / Catatan |
|---|---|---|---|
| 1 | **Proposal** (word, pdf) | 🟡 Kamu punya | File proposal TA-mu (biasanya dari seminar proposal) |
| 2 | **Buku tesis** (word, pdf) | 🟡 Kamu punya | Buku TA final (revisi sidang) — Word + PDF |
| 3 | **Data** (raw/csv/sql) + readme | ✅ **Siap di repo** | Lihat "Item 3" di bawah |
| 4 | **PPT** tesis | 🟡 Kamu punya | Slide sidang akhir |
| 5 | **Poster** tesis | 🟡 Kamu buat | Poster A1/A2 (kalau belum ada, perlu dibuat) |
| 6 | **Video** menjelaskan program | 🔴 **Perlu direkam** | Lihat panduan "Item 6" di bawah |
| 7 | **Kode program** + readme | ✅ **Siap di repo** | `README.md` sudah dibuat; lihat "Item 7" |
| 8 | **Paper** (submission/comments/revisi) | 🟡 Kamu punya | Paper + bukti submit + komentar reviewer + revisi |
| 9 | **Model tersimpan + hasil uji coba** | ✅ **Siap di repo** | Lihat "Item 9" di bawah |

Legenda: ✅ sudah ada di repo (aku bantu) · 🟡 kamu sudah punya, tinggal kumpulkan · 🔴 perlu dibuat.

---

## Struktur folder Google Drive (disarankan)

```
Bebas Tanggungan - 5025221230 - Dwiyana Yudha Prawira/
├─ 1. Proposal/                 proposal.docx, proposal.pdf
├─ 2. Buku Tesis/               buku_TA.docx, buku_TA.pdf
├─ 3. Data/                     (lihat Item 3) + README_DATA.md
├─ 4. PPT/                      sidang_akhir.pptx, sidang_akhir.pdf
├─ 5. Poster/                   poster.pdf (+ .png)
├─ 6. Video/                    demo_program.mp4  (atau link YouTube unlisted)
├─ 7. Kode Program/             SitasiAI-kode.zip + README.md  (atau link GitHub)
├─ 8. Paper/                    paper.pdf, bukti_submission, komentar_reviewer, revisi
└─ 9. Model & Hasil Uji/        index FAISS + hasil_eksperimen + results_tesis
```

---

## Item 3 — Data (SIAP)

Salin dari repo:
- `evaluasi/dataset_v1.csv` (1,9 MB) — dataset gabungan
- `evaluasi/ground_truth_human.csv` (1,6 MB) — ground truth label manusia
- `evaluasi/Ground_Truth/` — ground truth mentah per-checker
- `evaluasi/extracted_abstracts.csv` — abstrak terekstrak
- **README data** → pakai `evaluasi/README.md` (rename jadi `README_DATA.md`)

> Data korpus 163k (index eksternal) opsional — besar (~640 MB). Kalau diminta, ambil dari
> GitHub Release `data-v1` dan taruh linknya di README data.

## Item 6 — Video (PERLU DIREKAM)

Rekam layar 3-7 menit menjelaskan program. Struktur saran:
1. **Buka aplikasi** live: `https://senopati.its.ac.id/sitasi-ai/`
2. **Buat sitasi** — tempel 1 klaim → tunjukkan 1 sitasi + referensi terkait.
3. **Sitasi abstrak** — tempel abstrak → sitasi per kalimat.
4. **Cari paper** — cari topik → panel sumber (korpus lokal + Semantic Scholar).
5. **Tunjukkan penjaga anti-halusinasi** — masukkan klaim ngawur → ditolak, tidak dipaksa.
6. Singgung arsitektur (HyDE → SPECTER2 → FAISS → CoT).

Alat rekam: OBS Studio / Xbox Game Bar (Win+G) / Loom. Upload MP4 atau YouTube (unlisted).

## Item 7 — Kode Program (SIAP)

Dua opsi (boleh dua-duanya):
- **Link GitHub:** `https://github.com/revenca/SitasiAI` (kode + `README.md` + `DEPLOY.md`)
- **ZIP:** buat arsip tanpa berkas berat (lihat perintah di bawah)

`README.md` di root sudah menjelaskan: fitur, arsitektur, struktur, cara menjalankan (Docker & lokal).

## Item 9 — Model tersimpan & hasil uji coba (SIAP)

- **Model/index:** `evaluasi/faiss_index*.bin`, `backend/data/faiss_index.bin`,
  `external_index/faiss_index_external.bin` (163k) — index vektor SPECTER2 (ini "model tersimpan"-nya).
- **Hasil uji coba:** `evaluasi/hasil_eksperimen/` (prediksi & RAGAS per-run),
  `evaluasi/results_tesis/` (uji t + Bonferroni, tabel ablasi, lampiran per-kueri).
- **Analisis:** `evaluasi/docs/` (analisis kualitatif, batasan prompting, tabel Bab 4).

---

## Template email

**Subjek:**
```
Bebas Tanggungan 5025221230 Dwiyana Yudha Prawira <tahun-lulus>
```

**Isi:**
```
Yth. Bapak/Ibu,

Berikut saya lampirkan link Google Drive berisi kelengkapan bebas tanggungan Tugas Akhir saya:

Nama    : Dwiyana Yudha Prawira
NRP     : 5025221230
Prodi   : Teknik Informatika ITS
Judul   : Pembuatan Sitasi Paper Menggunakan LLM Berbasis Query Expansion dan Vector Embeddings

Link Drive: <tempel link di sini>

Konten: (1) Proposal, (2) Buku TA, (3) Data + readme, (4) PPT, (5) Poster,
(6) Video demo program, (7) Kode program + readme, (8) Paper, (9) Model & hasil uji coba.

Demikian, mohon arahannya bila ada yang perlu dilengkapi. Terima kasih.

Hormat saya,
Dwiyana Yudha Prawira
```

> Pastikan setelan berbagi Drive: **"Siapa saja yang memiliki link" → Pelihat**, agar dosen bisa membuka.

# Analisis Kualitatif Hasil — SitasiAI (korpus 100 paper, mode lokal)

Melengkapi analisis kuantitatif (Recall/Hit@K/MRR/Faithfulness) dengan telaah studi
kasus per-kueri: MENGAPA sistem berhasil atau gagal. Semua contoh diambil dari data
eksperimen nyata (`hasil_eksperimen/hasil_prediksi_baseline_k5_clean_specter_r1.csv`
dan `hasil_ragas_clean_base_r1.csv`), 144 kueri ground-truth.

Ringkasan angka pendukung (run r1): Hit rank-1 = 108/144 kueri; gold tak ter-retrieve
(miss) = 6 kueri; sistem menolak (relevant=False) = 3 kueri.

---

## A. Kasus BERHASIL — retrieval + sitasi tepat

### Kasus 1 (cid 1): segmentasi citra medis
- **Paragraf:** "...Res U-Net produced the best loss value... training time can be
  significantly faster... better segmentation results..."
- **Gold:** *Left Ventricular Wall Segmentation Using U-Net and Link-Net* → **ditemukan (rank-1)**
- **Kalimat sitasi (keluaran sistem):** "The proposed method reduces training time by 13%
  compared to U-Net while delivering visually better segmentation results (Ref 1)."
- **Analisis:** paragraf kaya istilah spesifik (Res U-Net, epoch, loss, segmentasi).
  Embedding SPECTER2 langsung mendekatkannya ke paper arsitektur U-Net. Sistem
  merangkum kontribusi pada tingkat konseptual (bukan menyalin abstrak). Ini pola
  mayoritas (108/144 kueri hit di rank-1).

---

## B. Kasus GAGAL retrieval (MISS) — gold tidak masuk top-K

### Kasus 2 (cid 25): topik paragraf ≠ topik paper yang disitasi
- **Paragraf:** "...exhibited better performance than the MobileNet model... accuracy 85%..."
  (membahas perbandingan model klasifikasi citra)
- **Gold:** *Sarcasm Detection in Indonesian-English Code-Mixed Text* (NLP!)
- **Didapat:** *A Comparison of VGG Architecture Convolutional Layers* (computer vision)
- **Analisis:** ini **kesenjangan antara isi paragraf dan paper yang sebenarnya
  disitasi**. Paragraf berbicara tentang MobileNet/akurasi (visi komputer), tetapi
  sitasi gold justru ke paper sarkasme (NLP) — kemungkinan sitasi metodologis silang-domain.
  Embedding berbasis KONTEN tidak mungkin menjembatani ini karena secara semantik
  paragraf memang jauh dari paper gold. **Batas fundamental pendekatan content-based:**
  ketika penulis asli menyitasi lintas-domain, sinyal kontennya tidak ada di paragraf.

### Kasus 3 (cid 9): satu paragraf, banyak paper sangat mirip
- **Paragraf:** "...graphical representation of COBIT 2019-governed processes..."
- **Gold:** *Novel Activity Recommendation System of Financial Balance Scorecard*
- **Didapat:** *Optimizing IT Governance...*, *Identifying Non-Conforming Process...*,
  *Process Mining for Evaluating Hospital Billing...* (semua COBIT/IT governance)
- **Analisis:** korpus memiliki **klaster paper COBIT yang sangat berdekatan** secara
  semantik. Sistem menemukan tetangga yang benar TOPIKNYA, tetapi bukan paper gold yang
  spesifik. Ini kegagalan "near-miss" — bukan melenceng total, melainkan tersaingi
  paper serumpun. Menjelaskan mengapa metrik paper-level lebih rendah pada sub-domain
  padat (COBIT) dibanding domain terisolasi (segmentasi medis).

---

## C. Kasus DITOLAK (relevant=False) — sistem menolak menyitasi

### Kasus 4 (cid 94): sistem menolak referensi yang tidak mendukung klaim
- **Gold:** *RNA-BioLens: Raspberry Pi-Based Digital Microscope*
- **Didapat:** *Leveraging Fine-Tuned YOLOv8 with Transfer Learning*
- **Alasan (reasoning sistem):** "The retrieved reference does not provide specific metrics
  or findings related to CRC detection using YOLO or SSD, which are critical to supporting
  the [claim]"
- **Analisis:** meski retrieval memberi kandidat, **sistem menilai isi chunk tidak cukup
  mendukung klaim spesifik paragraf, lalu menolak** (relevant=False). Ini perilaku yang
  DIINGINKAN: lebih baik tidak menyitasi daripada menyitasi keliru — sistem melakukan
  verifikasi isi, bukan sekadar memilih skor tertinggi.

### Kasus 5 (cid 95, 125): tidak ada chunk relevan → tolak jujur
- **Alasan:** "Tidak ada chunk yang di-retrieve." → relevant=False
- **Analisis:** ketika retrieval kosong/lemah, sistem menolak alih-alih mengarang. Sesuai
  desain fallback (kandidat kosong → relevant=False).

---

## D. Analisis kualitatif efek HyDE (mendukung temuan null-result)

### Kasus 6 (cid 2): HyDE MENYEMPITKAN retrieval
- **Paragraf:** "...novel recommendation system for internal business processes,
  grounded in the COBIT 2019 framework..."
- **Baseline |R|=3:** Novel Activity Recommendation, Identifying Non-Conforming Process,
  Optimizing IT Governance
- **HyDE |R|=1:** Novel Activity Recommendation (gold) saja
- **Analisis:** HyDE mengubah kueri menjadi abstrak hipotetis yang lebih terfokus →
  retrieval mengerucut ke lebih sedikit paper. Di kasus ini menguntungkan precision
  (gold langsung dominan). NAMUN pada kueri lain penyempitan yang sama **membuang gold**
  ketika abstrak hipotetis menarik kueri menjauh — inilah mekanisme di balik turunnya
  Recall/Hit/MRR HyDE secara agregat. Precision paper-level HyDE yang lebih tinggi
  adalah konsekuensi penyempitan (penyebut |R| mengecil), bukan peningkatan kemampuan
  menemukan gold. Analisis kualitatif ini konsisten dengan hasil kuantitatif.

---

## E. Analisis Faithfulness rendah (RAGAS)

Beberapa kueri mendapat faithfulness = 0,00. Telaah kualitatif:
- **cid 95:** response = kosong (NaN) — retrieval kosong → tidak ada yang dinilai → 0.
- Kueri NER/EEG: response memuat entitas/angka (GloVe, Word2vec, akurasi 65,9%) yang
  **tidak seluruhnya terdukung** oleh chunk konteks → RAGAS menandai klaim tak terdukung.
- **Analisis:** faithfulness rendah muncul dari (a) konteks kosong, atau (b) sistem
  menambah detail teknis yang tidak eksplisit di chunk. Ini membedakan faithfulness
  (grounding) dari kebenaran faktual: kalimat bisa benar tetapi dinilai tidak faithful
  bila tidak tertelusur ke konteks yang diberikan.

---

## Kesimpulan analisis kualitatif

1. **Keberhasilan** didorong oleh paragraf kaya istilah teknis + encoder domain
   (SPECTER2) → mayoritas gold ditemukan di rank-1.
2. **Kegagalan retrieval** berasal dari (a) sitasi lintas-domain yang tidak tercermin
   di konten paragraf, dan (b) klaster paper sangat mirip (near-miss) — keduanya batas
   fundamental pendekatan content-based, bukan bug implementasi.
3. **Sistem melakukan penyaringan** — menolak referensi yang tak mendukung klaim,
   mengurangi sitasi keliru dengan biaya sedikit penurunan recall.
4. **Efek HyDE** secara kualitatif = penyempitan retrieval; menguntungkan sebagian kueri
   tetapi merugikan agregat — mendukung kesimpulan kuantitatif bahwa HyDE tidak
   mengungguli baseline pada korpus ini.

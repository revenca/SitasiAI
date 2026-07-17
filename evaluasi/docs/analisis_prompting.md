# Analisis Kualitatif Evolusi Prompt HyDE — SitasiAI (lingkup skripsi: korpus 100 paper, mode lokal)

Cakupan: evolusi prompt **HyDE** (query expansion) pada sistem yang dievaluasi di skripsi.
CoT TIDAK dibahas terpisah di sini karena merupakan komponen tetap yang tidak diuji secara
terpisah (selalu aktif berbarengan dengan seluruh konfigurasi). Fitur pencarian eksternal
(pasca-sidang) TIDAK termasuk.

Sumber bukti: `arsip/diag_hyde_prompt.py` (V0 & V0.5), `backend/rag_engine.py` pada commit
awal `ef6f306` (V1), `pipeline.py` (V2 final).

---

## 1. Silsilah Prompt HyDE (4 versi)

### V0 — Naif / tanpa struktur (awal pengembangan)
```
Given the following paragraph from a scientific paper, generate a hypothetical
reference document (in the form of an abstract) that would be the most relevant
citation for this paragraph. The hypothetical document should match the topic,
methodology, findings, and domain of the source paragraph. Write only the
hypothetical abstract, no explanation.
```
**Batasan yang teramati (kualitatif):**
- Tidak ada kontrol panjang/format → panjang keluaran tidak stabil antar-run.
- Instruksi "match the topic" terlalu longgar → abstrak cenderung **parafrase umum**
  dari paragraf, miskin istilah teknis spesifik → daya pisah embedding rendah.
- Tidak ada aturan grounding → sesekali menambahkan temuan yang tidak ada di paragraf.

### V0.5 — Citation-aware (eksperimen diagnostik, `diag_hyde_prompt.py`)
```
You are helping identify the exact scientific paper that a given paragraph cites.
First, identify the SPECIFIC claim, method, dataset, metric, or finding ... then
write a detailed hypothetical abstract ... use precise technical terms, method/
model/algorithm names, datasets, and metrics ... state concrete quantitative
findings ... focus narrowly on the cited claim, not the broad topic.
```
**Pembelajaran:** mengarahkan model ke KLAIM SPESIFIK (bukan topik luas) menaikkan
kepadatan istilah teknis pada abstrak hipotetis. Diuji terpisah pada 50 paragraf gold
(recall gold paper, generator DeepSeek, index lama 150-kata) sebelum diadopsi.

### V1 — Persona CS + 3 aturan (produksi awal; terekam di `rag_engine.py` @ ef6f306)
```
Act as an expert computer science researcher. ...
Strict Rules:
1. Format & Length: Strictly 1 continuous paragraph, around 100-150 words. ...
2. Semantic Density: Maximize specific algorithms, frameworks, methodologies, ...
3. IEEE Structure: Start with the core contribution, state the setup, conclude with results.
```
(temperature 0,4; single-shot: 1 abstrak, embedding abstrak dipakai langsung)

**Batasan yang teramati:**
- **Bias persona domain**: persona "computer science researcher" menyeret kosakata
  keluaran ke ranah CS meskipun paragraf berasal dari domain lain (mis. instrumentasi,
  penginderaan kimia, medis) → abstrak hipotetis melenceng domain → vektor kueri
  menjauh dari chunk paper yang relevan (**retrieval drift**).
- **Single-shot + stokastik**: satu sampel abstrak pada temperature > 0 berarti kualitas
  retrieval bergantung pada satu kali "lemparan dadu" — antar-run bisa mengambil
  paper yang berbeda.

### V2 — Domain-agnostic + grounding + proper HyDE (final skripsi; `pipeline.py`)
```
You are an expert academic researcher writing in the style of a peer-reviewed
scientific paper. ...
Strict Rules:
1. Format & Length: ... approximately {HYDE_WORDS} words ...
2. Domain Fidelity: Infer the specific research domain from the paragraph
   (e.g., telecommunications, chemical sensing, computer vision, software
   engineering) ... Do not assume the domain is computer science.
3. Semantic Density: ... algorithms, frameworks, instruments, datasets, or
   evaluation metrics ...
4. IEEE Structure: ...
5. Grounding: Stay faithful to the claims in the draft. Do not introduce findings
   that contradict or drift away from the paragraph's actual topic.
```
Disertai perubahan ARSITEKTUR (Gao et al., 2022): N=5 abstrak hipotetis di-embed lalu
dirata-ratakan BERSAMA embedding paragraf asli (rumus N+1), dinormalisasi L2;
temperature 0,7; panjang parametrik (`HYDE_WORDS`).

**Perbaikan yang dituju per aturan:**
| Aturan V2 | Kegagalan V0/V1 yang direspons |
|---|---|
| Domain Fidelity ("do not assume CS") | Bias persona CS → melenceng domain |
| Grounding | Temuan karangan yang menjauh dari topik paragraf |
| Panjang parametrik | Studi sensitivitas panjang abstrak (50-80 vs 100-150 vs 200-250 kata) |
| Multi-generate N=5 + rata-rata + query | Ketidakstabilan single-shot; jangkar ke kueri asli meredam drift |

---

## 2. Tema batasan prompting HyDE (untuk subbab Keterbatasan)

1. **Stokastisitas** — pada temperature 0,7 keluaran HyDE berbeda tiap run; seluruh
   metrik dilaporkan multi-run (mean ± std). Ini batasan inheren, bukan bug.
2. **Bias persona** — persona pada prompt lebih kuat menyeret keluaran daripada isi
   input (V1 "computer science researcher" → melenceng domain); penentuan domain harus
   diserahkan ke inferensi model, bukan ditetapkan statis.
3. **Kepatuhan format tidak terjamin** — struktur keluaran (panjang, satu paragraf abstrak)
   tidak selalu dipatuhi pada temperature > 0; perlu aturan format eksplisit di prompt.
4. **Prompt engineering bersifat empiris** — evolusi V0→V2 terdokumentasi dengan file
   (arsip + git) sebagai respons kegagalan yang teramati, bukan desain sempurna sejak awal.
5. **Batas efektivitas prompting** — perbaikan prompt (V1→V2) memperbaiki kualitas
   abstrak hipotetis dan meredam drift, namun TIDAK mengubah kesimpulan utama:
   pada korpus ini HyDE tetap tidak mengungguli baseline (paragraf kueri sudah kaya
   konteks + encoder domain-spesifik), konsisten dengan sifat manfaat HyDE yang
   bergantung domain.

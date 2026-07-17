# Setup PostgreSQL + pgvector (deployment)

Basis data vektor SitasiAI bisa dipindah dari FAISS ke **PostgreSQL + pgvector** untuk
deployment (multi-user, satu database, mudah di-backup). Tanpa Postgres, sistem otomatis
memakai FAISS — jadi langkah ini **opsional**.

## 1. Jalankan Postgres + pgvector (paling mudah: Docker)
```bash
docker run -d --name sitasi-pg \
  -e POSTGRES_USER=sitasi -e POSTGRES_PASSWORD=password -e POSTGRES_DB=sitasiai \
  -p 5432:5432 pgvector/pgvector:pg16
```
(Image `pgvector/pgvector` sudah termasuk ekstensi vector.)

Alternatif cloud gratis: Supabase / Neon (sudah mendukung pgvector) — ambil connection string-nya.

## 2. Set connection string di `.env`
```
DATABASE_URL=postgresql://sitasi:password@localhost:5432/sitasiai
```
Ini dipakai untuk **dua** hal: tabel relasional (users/history/papers) via SQLAlchemy, dan
tabel vektor `documents` via pgvector.

## 3. Migrasi data vektor FAISS → Postgres
```bash
# basis data 163k (default)
python -m backend.migrate_to_pgvector
# (opsional) korpus 100-paper juga
python -m backend.migrate_to_pgvector --source lokal_100
```
Script akan: buat ekstensi `vector`, buat tabel `documents`, insert semua vektor + metadata
(batch 1.000), lalu buat index HNSW cosine.

## 4. Jalankan seperti biasa
```powershell
.\start.ps1
```
`rag_engine.search_database()` otomatis memakai pgvector bila tabel `documents` siap;
kalau tidak, fallback ke FAISS.

## Skema tabel `documents`
| kolom | tipe | isi |
|---|---|---|
| id | SERIAL | primary key |
| paper_title | TEXT | judul paper |
| abstract | TEXT | abstrak / chunk |
| authors | TEXT | penulis (display, mis. "Smith et al.") |
| year | TEXT | tahun |
| citation | TEXT | kunci sitasi ("Smith et al., 2020") |
| doi | TEXT | tautan DOI |
| cited_by | INTEGER | jumlah sitasi |
| source | TEXT | `db_163k` / `lokal_100` |
| embedding | vector(768) | embedding SPECTER2 (pgvector) |

Pencarian: `ORDER BY embedding <=> :qvec LIMIT k` (index HNSW cosine).

## Urutan prioritas basis data (search_database)
1. **PostgreSQL + pgvector** (bila DATABASE_URL Postgres & tabel documents ada)
2. **FAISS index 163k** (offline)
3. **Korpus 100-paper** (FAISS chunk)

Sumber eksternal (Semantic Scholar live) tidak berubah — tetap fetch on-demand.

## Catatan
- Ukuran: 163k × 768 dim ≈ ~500 MB di Postgres (sama seperti FAISS).
- Evaluasi tesis (100 paper) tidak butuh Postgres; ini murni untuk produk yang di-deploy.
- Backup cukup `pg_dump`.

"""
backend/migrate_to_pgvector.py — Migrasi index FAISS + metadata → PostgreSQL (pgvector).

Membaca vektor dari external_index/faiss_index_external.bin (+ metadata_external.jsonl),
lalu memasukkannya ke tabel `documents` di Postgres. Bisa juga memigrasi index korpus
100-paper. Idempoten per-source (hapus dulu source yang sama sebelum insert).

Prasyarat:
    - Postgres jalan + DATABASE_URL di .env (postgresql://user:pass@host:5432/sitasiai)
    - Ekstensi pgvector tersedia (CREATE EXTENSION vector — otomatis dicoba)

Jalankan:
    python -m backend.migrate_to_pgvector                     # migrasi index 163k (default)
    python -m backend.migrate_to_pgvector --source lokal_100  # migrasi korpus 100-paper
"""
import os, sys, json, argparse
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
import numpy as np
import faiss
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

from backend import vectordb

ROOT = Path(__file__).resolve().parent.parent
SOURCES = {
    "db_163k":   (ROOT / "external_index" / "faiss_index_external.bin",
                  ROOT / "external_index" / "metadata_external.jsonl", "jsonl"),
    "lokal_100": (ROOT / "backend" / "data" / "faiss_index.bin",
                  ROOT / "backend" / "data" / "metadata.json", "json"),
}


def _cite(authors, year):
    year = str(year) if year else "n.d."
    al = authors if isinstance(authors, list) else ([authors] if authors else [])
    al = [a for a in al if a]
    if not al:
        return "", year, ""
    surname = str(al[0]).split()[-1]
    disp = f"{al[0]} et al." if len(al) > 1 else al[0]
    key = f"{surname} et al., {year}" if len(al) > 1 else f"{surname}, {year}"
    return disp, year, key


def _load_meta(path, kind):
    if kind == "jsonl":
        return [json.loads(l) for l in open(path, encoding="utf-8")]
    return json.load(open(path, encoding="utf-8"))


def migrate(source: str):
    idx_path, meta_path, kind = SOURCES[source]
    if not idx_path.exists():
        print(f"SKIP {source}: {idx_path.name} tidak ada."); return
    print(f"Baca {idx_path.name} ...")
    index = faiss.read_index(str(idx_path))
    n = index.ntotal
    vecs = index.reconstruct_n(0, n)                 # (n, dim) — FAISS Flat mendukung ini
    meta = _load_meta(meta_path, kind)
    dim = vecs.shape[1]
    print(f"  {n:,} vektor ({dim}-dim), {len(meta):,} metadata")

    vectordb.ensure_schema(dim)
    vectordb.truncate(source)                        # idempoten: bersihkan source ini dulu

    BATCH, recs, done = 1000, [], 0
    for i in range(min(n, len(meta))):
        m = meta[i]
        # metadata bisa 2 skema: {title,abstract,authors[]...} atau chunk {paper_title,chunk_text}
        title = m.get("title") or m.get("paper_title") or ""
        abstract = m.get("abstract") or m.get("chunk_text") or ""
        authors_raw = m.get("authors", [])
        disp, year, citation = _cite(authors_raw, m.get("year", ""))
        recs.append({
            "paper_title": title, "abstract": abstract[:4000], "authors": disp,
            "year": year, "citation": citation, "doi": m.get("doi", "") or "",
            "cited_by": int(m.get("cited_by", 0) or 0), "source": source,
            "embedding": np.asarray(vecs[i], dtype=np.float32),
        })
        if len(recs) >= BATCH:
            vectordb.bulk_insert(recs); done += len(recs); recs = []
            print(f"  ...{done:,}/{n:,}", end="\r")
    if recs:
        vectordb.bulk_insert(recs); done += len(recs)
    print(f"\n  {done:,} baris ter-insert (source={source}).")
    print("  Membuat index HNSW (bisa beberapa menit utk data besar)...")
    vectordb.create_index()
    print(f"SELESAI migrasi {source}. Total di documents: {vectordb.count():,}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="db_163k", choices=list(SOURCES))
    args = ap.parse_args()
    if vectordb._connect() is None:
        print("Postgres tidak terhubung. Set DATABASE_URL=postgresql://... di .env dulu.")
        sys.exit(1)
    migrate(args.source)


if __name__ == "__main__":
    main()

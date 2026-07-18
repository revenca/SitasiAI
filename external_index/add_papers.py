"""
external_index/add_papers.py — Tambah paper spesifik ke index korpus 163k.

Fetch (Semantic Scholar) → embed SPECTER2 (identik harvest) → append ke
faiss_index_external.bin + metadata_external.jsonl (baris ke-i ⟷ vektor ke-i).

Aman: backup sekali (.bak), dedup by judul (tak dobel bila diulang), verifikasi di akhir.

Jalankan:
  .venv\\Scripts\\python.exe -m external_index.add_papers
  # atau tambah query sendiri:
  .venv\\Scripts\\python.exe -m external_index.add_papers "judul/kueri paper lain"
"""
import os, sys, json, shutil, time
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
from pathlib import Path
import numpy as np
import requests
import faiss

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import backend.rag_engine as rag

HERE       = Path(__file__).resolve().parent
INDEX_FILE = HERE / "faiss_index_external.bin"
META_FILE  = HERE / "metadata_external.jsonl"
S2_URL     = "https://api.semanticscholar.org/graph/v1/paper/search"
S2_KEY     = os.getenv("S2_API_KEY", "")

# Paper fondasi yang dipakai sistem tapi (mungkin) belum ada di korpus.
# 'expect' = kata yang WAJIB ada di judul hasil (sanity check biar tak salah ambil paper).
TARGETS = [
    {"query": "Precise Zero-Shot Dense Retrieval without Relevance Labels", "expect": "zero-shot"},
    {"query": "SPECTER Document-level Representation Learning using Citation-informed Transformers", "expect": "specter"},
    {"query": "SciRepEval Multi-Format Benchmark Scientific Document Representations", "expect": "scirepeval"},
]


def s2_search(query, limit=5):
    headers = {"x-api-key": S2_KEY} if S2_KEY else {}
    params = {"query": query, "limit": limit,
              "fields": "title,abstract,year,authors,citationCount,externalIds"}
    for attempt in range(3):
        try:
            r = requests.get(S2_URL, params=params, headers=headers, timeout=25)
            if r.status_code == 200:
                return r.json().get("data", []) or []
            if r.status_code == 429:
                time.sleep(2 * (attempt + 1)); continue
            print(f"  [S2 {r.status_code}] {query[:40]}"); return []
        except requests.RequestException as e:
            print(f"  [S2 err] {e}"); time.sleep(1)
    return []


def pick(cands, expect):
    """Ambil kandidat pertama yang punya abstrak & judulnya cocok 'expect'."""
    for p in cands:
        title = (p.get("title") or "")
        if p.get("abstract") and (not expect or expect.lower() in title.lower()):
            return p
    # longgar: cukup ada abstrak
    for p in cands:
        if p.get("abstract"):
            return p
    return None


def to_meta(p):
    doi = (p.get("externalIds") or {}).get("DOI", "")
    return {
        "title":    p.get("title", ""),
        "year":     p.get("year"),
        "authors":  [a["name"] for a in (p.get("authors") or [])],
        "doi":      f"https://doi.org/{doi}" if doi else "",
        "cited_by": p.get("citationCount") or 0,
        "abstract": (p.get("abstract") or "")[:600],
    }


def main():
    extra = sys.argv[1:]
    targets = TARGETS + [{"query": q, "expect": ""} for q in extra]

    print("Memuat model SPECTER2...")
    rag.init()

    # Backup sekali (pertahankan versi asli pristine)
    for f in (INDEX_FILE, META_FILE):
        bak = f.with_suffix(f.suffix + ".bak")
        if not bak.exists():
            shutil.copy2(f, bak); print(f"Backup -> {bak.name}")

    index = faiss.read_index(str(INDEX_FILE))
    meta  = [json.loads(l) for l in open(META_FILE, encoding="utf-8")]
    have  = {(m.get("title") or "").strip().lower() for m in meta}
    print(f"Index sekarang: {index.ntotal} vektor, {len(meta)} metadata\n")

    new_papers, new_texts = [], []
    for t in targets:
        print(f"Cari: {t['query'][:60]}")
        p = pick(s2_search(t["query"]), t.get("expect", ""))
        if not p:
            print("  ✗ tak ada hasil dgn abstrak"); continue
        title = (p.get("title") or "").strip()
        if title.lower() in have:
            print(f"  · sudah ada, lewati: {title[:55]}"); continue
        m = to_meta(p)
        # teks embed = format harvest (title + abstract penuh, potong 2000)
        text = f"{p.get('title','')} {p.get('abstract','')}"[:2000]
        new_papers.append(m); new_texts.append(text); have.add(title.lower())
        print(f"  ✓ {title[:60]} ({m['year']}) · dikutip {m['cited_by']:,}")

    if not new_papers:
        print("\nTidak ada paper baru untuk ditambahkan."); return

    print(f"\nEmbed {len(new_texts)} paper (SPECTER2)...")
    vecs = np.asarray(rag.embed_many(new_texts), dtype=np.float32)
    assert vecs.shape[1] == index.d, f"dim mismatch {vecs.shape[1]} != {index.d}"

    index.add(vecs)                                   # append ke IndexFlatIP
    faiss.write_index(index, str(INDEX_FILE))
    with open(META_FILE, "a", encoding="utf-8") as f:
        for m in new_papers:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")
    print(f"Ditambahkan. Index sekarang: {index.ntotal} vektor.\n")

    # Verifikasi: cari tiap paper baru, harus muncul teratas
    print("== Verifikasi (cari judul paper baru) ==")
    idx2 = faiss.read_index(str(INDEX_FILE))
    meta2 = [json.loads(l) for l in open(META_FILE, encoding="utf-8")]
    for m in new_papers:
        q = np.asarray(rag.embed(m["title"]), dtype=np.float32).reshape(1, -1)
        sc, ids = idx2.search(q, 1)
        top = meta2[ids[0][0]]["title"]
        ok = top.strip().lower() == m["title"].strip().lower()
        print(f"  {'✓' if ok else '✗'} skor {sc[0][0]:.3f}  {top[:58]}")


if __name__ == "__main__":
    main()

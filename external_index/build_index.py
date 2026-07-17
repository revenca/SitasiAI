"""
external_index/build_index.py — Gabung semua vektor shard → FAISS index + metadata.

Baca external_index/vecs/shard_*.npy (+ .meta.jsonl), tumpuk jadi satu index FAISS
(IndexFlatIP = cosine krn vektor sudah L2-normalized) + metadata sejajar.

Jalankan:
    python external_index/build_index.py
Output:
    external_index/faiss_index_external.bin
    external_index/metadata_external.jsonl
"""
import os, json, glob
import numpy as np
import faiss

HERE    = os.path.dirname(os.path.abspath(__file__))
VEC_DIR = os.path.join(HERE, "vecs")
OUT_IDX = os.path.join(HERE, "faiss_index_external.bin")
OUT_MET = os.path.join(HERE, "metadata_external.jsonl")


def main():
    vec_files = sorted(glob.glob(os.path.join(VEC_DIR, "shard_*.npy")))
    if not vec_files:
        print("Tidak ada .npy — jalankan embed_shards.py dulu."); return
    print(f"{len(vec_files)} shard vektor.")
    arrs, total = [], 0
    with open(OUT_MET, "w", encoding="utf-8") as mout:
        for vf in vec_files:
            name = os.path.splitext(os.path.basename(vf))[0]
            arr = np.load(vf)
            metf = os.path.join(VEC_DIR, f"{name}.meta.jsonl")
            metas = [l for l in open(metf, encoding="utf-8")]
            assert len(metas) == arr.shape[0], f"{name}: vektor≠meta"
            for m in metas:
                mout.write(m)
            arrs.append(arr); total += arr.shape[0]
            print(f"  + {name}: {arr.shape[0]} (total {total:,})")
    mat = np.vstack(arrs).astype(np.float32)
    dim = mat.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(mat)
    faiss.write_index(index, OUT_IDX)
    size_mb = os.path.getsize(OUT_IDX) / 1e6
    print(f"\nSELESAI: {index.ntotal:,} vektor ({dim}-dim) → {os.path.basename(OUT_IDX)} "
          f"({size_mb:.0f} MB) + metadata_external.jsonl")


if __name__ == "__main__":
    main()

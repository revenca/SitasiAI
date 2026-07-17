"""
external_index/embed_shards.py — Embed tiap shard abstrak dgn SPECTER2 (RESUMABLE, GPU batch).

Untuk tiap external_index/data/shard_XXXXX.jsonl → hasil external_index/vecs/shard_XXXXX.npy
(+ shard_XXXXX.meta.jsonl). Shard yang .npy-nya sudah ada di-SKIP → aman di-pause (Ctrl+C)
lalu lanjut. Tahap ini pakai GPU penuh — JANGAN dibarengkan main game (pause dulu).

Jalankan:
    python external_index/embed_shards.py
    BATCH=64 python external_index/embed_shards.py
"""
import os, json, glob
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
import numpy as np
import torch
from transformers import AutoTokenizer
from adapters import AutoAdapterModel

HERE     = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
VEC_DIR  = os.path.join(HERE, "vecs")
BATCH    = int(os.getenv("BATCH", "32"))
SLEEP_MS = int(os.getenv("SLEEP_MS", "0"))     # jeda antar-batch (ms) → mode hemat/adem
MODEL    = "allenai/specter2_base"
ADAPTER  = "allenai/specter2"
os.makedirs(VEC_DIR, exist_ok=True)

print("Memuat SPECTER2 + adapter proximity...")
tok = AutoTokenizer.from_pretrained(MODEL)
mdl = AutoAdapterModel.from_pretrained(MODEL)
mdl.load_adapter(ADAPTER, source="hf", load_as="proximity", set_active=True)
mdl.set_active_adapters("proximity"); mdl.eval()
DEV = "cuda" if torch.cuda.is_available() else "cpu"
mdl.to(DEV)
print(f"Device: {DEV} | batch={BATCH}")


def embed_batch(texts):
    x = tok(texts, return_tensors="pt", truncation=True, max_length=512, padding=True)
    x = {k: v.to(DEV) for k, v in x.items()}
    with torch.no_grad():
        o = mdl(**x)
    e = torch.nn.functional.normalize(o.last_hidden_state[:, 0, :], dim=1)
    return e.cpu().numpy().astype(np.float32)


def main():
    shards = sorted(glob.glob(os.path.join(DATA_DIR, "shard_*.jsonl")))
    print(f"{len(shards)} shard ditemukan.")
    for sp in shards:
        name = os.path.splitext(os.path.basename(sp))[0]
        out_vec = os.path.join(VEC_DIR, f"{name}.npy")
        if os.path.exists(out_vec):
            print(f"  SKIP {name} (sudah ada)"); continue
        recs = [json.loads(l) for l in open(sp, encoding="utf-8")]
        texts = [f"{r['title']} {r['abstract']}"[:2000] for r in recs]
        vecs = []
        for i in range(0, len(texts), BATCH):
            vecs.append(embed_batch(texts[i:i + BATCH]))
            if SLEEP_MS:                        # jeda hemat: turunkan util GPU & suhu
                import time as _t; _t.sleep(SLEEP_MS / 1000.0)
        arr = np.vstack(vecs)
        # tulis meta ringkas (tanpa abstrak penuh utk hemat; simpan cuplikan)
        with open(os.path.join(VEC_DIR, f"{name}.meta.jsonl"), "w", encoding="utf-8") as f:
            for r in recs:
                f.write(json.dumps({"title": r["title"], "year": r.get("year"),
                                    "authors": r.get("authors", []), "doi": r.get("doi", ""),
                                    "cited_by": r.get("cited_by", 0),
                                    "abstract": r["abstract"][:600]}, ensure_ascii=False) + "\n")
        np.save(out_vec, arr)   # tulis .npy TERAKHIR = penanda shard selesai
        print(f"  {name}: {arr.shape[0]} vektor → {name}.npy")
    print("SELESAI embed semua shard.")


if __name__ == "__main__":
    main()

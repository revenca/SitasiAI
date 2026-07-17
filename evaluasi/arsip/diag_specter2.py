"""
Tes inference SPECTER2 (allenai/specter2_base + proximity adapter) — recall gold paper.
Bandingkan dengan SPECTER (64.6% top-5). Tanpa training, tanpa API.
"""
import os
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
import re, json, faiss, torch
import numpy as np, pandas as pd
from transformers import AutoTokenizer
from adapters import AutoAdapterModel

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
BATCH = 64
print(f"Device: {DEVICE}", flush=True)

print("Memuat SPECTER2 (base + proximity adapter)...", flush=True)
tok = AutoTokenizer.from_pretrained("allenai/specter2_base")
mdl = AutoAdapterModel.from_pretrained("allenai/specter2_base")
mdl.load_adapter("allenai/specter2", source="hf", load_as="proximity", set_active=True)
mdl.set_active_adapters("proximity")          # pastikan adapter AKTIF
mdl.eval(); mdl.to(DEVICE)
print("Adapter aktif:", mdl.active_adapters, flush=True)

def embed_all(texts):
    out = []
    for i in range(0, len(texts), BATCH):
        batch = [str(t) if str(t).strip() else " " for t in texts[i:i+BATCH]]
        x = tok(batch, return_tensors="pt", truncation=True, max_length=512, padding=True)
        x = {k: v.to(DEVICE) for k, v in x.items()}
        with torch.no_grad():
            o = mdl(**x)
        e = o.last_hidden_state[:, 0, :]              # CLS token
        e = torch.nn.functional.normalize(e, dim=1)
        out.append(e.cpu().numpy())
        if (i // BATCH) % 20 == 0:
            print(f"    embed {i}/{len(texts)}", flush=True)
    return np.vstack(out).astype("float32")

def norm(s):
    s = str(s).strip(); s = re.sub(r"\.p?d?f?$", "", s); return s.strip().lower()
def tmatch(a, b):
    a, b = norm(a), norm(b)
    return bool(a and b and (a.startswith(b) or b.startswith(a)))

meta = json.load(open("metadata.json", encoding="utf-8"))
chunk_texts = [m["chunk_text"] for m in meta]
chunk_papers = [m["paper_title"] for m in meta]

df = pd.read_csv("dataset_v1.csv"); ck = pd.read_csv("Ground_Truth/citation_checker_data.csv", sep=";")
H = ["V_H1","V_H2","V_H3","V_H4","V_H5","V_H6","V_H7"]
for c in H: ck[c] = ck[c].map({"TRUE":1,"FALSE":0,True:1,False:0}).fillna(0).astype(int)
df = df.iloc[:len(ck)].copy(); df["gt"] = (ck[H].sum(axis=1) >= 4).astype(int).values
gold = df[df["gt"] == 1].groupby("page_content_sumber")["title_paper_referensi"].apply(list).to_dict()
queries = list(gold.items())

print("Re-embed korpus dgn SPECTER2...", flush=True)
corpus = embed_all(chunk_texts)
idx = faiss.IndexFlatIP(corpus.shape[1]); idx.add(corpus)

print("Ukur recall query...", flush=True)
qemb = embed_all([str(s) for s, _ in queries])
hit = {5:0, 10:0, 20:0}
for qi, (s, golds) in enumerate(queries):
    _, ids = idx.search(qemb[qi:qi+1], 20)
    papers = [chunk_papers[i] for i in ids[0] if 0 <= i < len(chunk_papers)]
    for k in (5,10,20):
        if any(tmatch(p, g) for p in papers[:k] for g in golds): hit[k] += 1
N = len(queries)

print(f"\n{'='*46}")
print(f"  SPECTER2 — RECALL GOLD PAPER (N={N})")
print(f"{'='*46}")
for k in (5,10,20):
    print(f"  top-{k:<3}: {hit[k]/N*100:.1f}%")
print(f"{'='*46}")
print("  (pembanding SPECTER: top5=64.6% top10=86.1% top20=93.1%)")

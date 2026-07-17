"""
Bandingkan recall gold paper antar encoder (SOURCE embedding, tanpa API):
  - SciBERT CLS (baseline)
  - SciBERT mean-pooling
  - SPECTER (allenai/specter, dirancang utk kemiripan paper ilmiah)

Re-embed seluruh korpus (4180 chunk) per encoder, lalu ukur recall@5/10/20.
"""
import os
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
import re, json, faiss, torch
import numpy as np, pandas as pd
from transformers import AutoTokenizer, AutoModel

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
BATCH = 64 if DEVICE == "cuda" else 32
QUERY_N = None   # None = semua 144 paragraf gold
print(f"Device: {DEVICE}", flush=True)

def load(model_name):
    tok = AutoTokenizer.from_pretrained(model_name)
    mdl = AutoModel.from_pretrained(model_name); mdl.eval(); mdl.to(DEVICE)
    return tok, mdl

def embed_batch(texts, tok, mdl, pooling):
    x = tok(texts, return_tensors="pt", truncation=True, max_length=512, padding=True)
    x = {k: v.to(DEVICE) for k, v in x.items()}
    with torch.no_grad():
        o = mdl(**x)
    if pooling == "cls":
        emb = o.last_hidden_state[:, 0, :]
    else:  # mean-pooling dengan attention mask
        mask = x["attention_mask"].unsqueeze(-1).float()
        emb = (o.last_hidden_state * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
    emb = torch.nn.functional.normalize(emb, dim=1)
    return emb.cpu().numpy()

def embed_all(texts, tok, mdl, pooling):
    out = []
    for i in range(0, len(texts), BATCH):
        out.append(embed_batch(texts[i:i+BATCH], tok, mdl, pooling))
        if (i // BATCH) % 20 == 0:
            print(f"    embed {i}/{len(texts)}", flush=True)
    return np.vstack(out).astype("float32")

def norm(s):
    s = str(s).strip(); s = re.sub(r"\.p?d?f?$", "", s); return s.strip().lower()
def tmatch(a, b):
    a, b = norm(a), norm(b)
    return bool(a and b and (a.startswith(b) or b.startswith(a)))

# Data
meta = json.load(open("metadata.json", encoding="utf-8"))
chunk_texts = [m["chunk_text"] for m in meta]
chunk_papers = [m["paper_title"] for m in meta]

df = pd.read_csv("dataset_v1.csv"); ck = pd.read_csv("Ground_Truth/citation_checker_data.csv", sep=";")
H = ["V_H1","V_H2","V_H3","V_H4","V_H5","V_H6","V_H7"]
for c in H: ck[c] = ck[c].map({"TRUE":1,"FALSE":0,True:1,False:0}).fillna(0).astype(int)
df = df.iloc[:len(ck)].copy(); df["gt"] = (ck[H].sum(axis=1) >= 4).astype(int).values
gold = df[df["gt"] == 1].groupby("page_content_sumber")["title_paper_referensi"].apply(list).to_dict()
queries = list(gold.items())
if QUERY_N: queries = queries[:QUERY_N]

CONFIGS = [
    ("SciBERT-CLS",  "allenai/scibert_scivocab_uncased", "cls"),
    ("SciBERT-mean", "allenai/scibert_scivocab_uncased", "mean"),
    ("SPECTER",      "allenai/specter",                  "cls"),
]

results = {}
for name, model_name, pooling in CONFIGS:
    print(f"\n=== {name} ({model_name}, {pooling}) ===", flush=True)
    tok, mdl = load(model_name)
    print("  re-embed korpus...", flush=True)
    corpus = embed_all(chunk_texts, tok, mdl, pooling)
    idx = faiss.IndexFlatIP(corpus.shape[1]); idx.add(corpus)
    print("  ukur recall query...", flush=True)
    qtexts = [str(s) for s, _ in queries]
    qemb = embed_all(qtexts, tok, mdl, pooling)
    hit = {5:0, 10:0, 20:0}
    for qi, (s, golds) in enumerate(queries):
        _, ids = idx.search(qemb[qi:qi+1], 20)
        papers = [chunk_papers[i] for i in ids[0] if 0 <= i < len(chunk_papers)]
        for k in (5,10,20):
            if any(tmatch(p, g) for p in papers[:k] for g in golds): hit[k] += 1
    N = len(queries)
    results[name] = {k: hit[k]/N*100 for k in (5,10,20)}
    print(f"  {name}: top5={results[name][5]:.1f}% top10={results[name][10]:.1f}% top20={results[name][20]:.1f}%", flush=True)

print(f"\n{'='*58}")
print(f"  RECALL GOLD PAPER (SOURCE embedding) — N={len(queries)}")
print(f"{'='*58}")
print(f"  {'Encoder':<16}{'top-5':>10}{'top-10':>10}{'top-20':>10}")
print(f"  {'-'*52}")
for name in results:
    r = results[name]
    print(f"  {name:<16}{r[5]:>9.1f}%{r[10]:>9.1f}%{r[20]:>9.1f}%")
print(f"{'='*58}")

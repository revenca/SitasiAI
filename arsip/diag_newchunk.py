"""
Tes recall gold paper pada index BARU (token-400 chunk + judul[SEP]teks).
Bandingkan beberapa format query. Tanpa API.
Pembanding (index lama word-150): SPECTER top5=64.6% top10=86.1% top20=93.1%
"""
import os
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
import re, json, faiss, torch
import numpy as np, pandas as pd
from transformers import AutoTokenizer, AutoModel

DEV = "cuda" if torch.cuda.is_available() else "cpu"
tok = AutoTokenizer.from_pretrained("allenai/specter")
mdl = AutoModel.from_pretrained("allenai/specter").eval().to(DEV)

def embed(text):
    x = tok(text, return_tensors="pt", truncation=True, max_length=512, padding=True)
    x = {k: v.to(DEV) for k, v in x.items()}
    with torch.no_grad():
        o = mdl(**x)
    e = torch.nn.functional.normalize(o.last_hidden_state[:, 0, :], dim=1)
    return e.squeeze().cpu().numpy()

def norm(s):
    s = str(s).strip(); s = re.sub(r"\.p?d?f?$", "", s); return s.strip().lower()
def tmatch(a, b):
    a, b = norm(a), norm(b)
    return bool(a and b and (a.startswith(b) or b.startswith(a)))

idx = faiss.read_index("faiss_index.bin")
meta = json.load(open("metadata.json", encoding="utf-8"))
papers = [m["paper_title"] for m in meta]
print(f"Index baru: {idx.ntotal} vektor, {len(set(papers))} paper\n")

df = pd.read_csv("dataset_v1.csv"); ck = pd.read_csv("Ground_Truth/citation_checker_data.csv", sep=";")
H = ["V_H1","V_H2","V_H3","V_H4","V_H5","V_H6","V_H7"]
for c in H: ck[c] = ck[c].map({"TRUE":1,"FALSE":0,True:1,False:0}).fillna(0).astype(int)
df = df.iloc[:len(ck)].copy(); df["gt"] = (ck[H].sum(axis=1) >= 4).astype(int).values
gold = df[df["gt"] == 1].drop_duplicates("page_content_sumber")
queries = list(zip(gold["page_content_sumber"], gold["title_paper_referensi"]))

SEP = tok.sep_token

def run(label, fmt):
    hit = {5:0,10:0,20:0}
    for src, gref in queries:
        q = embed(fmt(str(src))).reshape(1,-1).astype("float32")
        _, ids = idx.search(q, 20)
        ps = [papers[i] for i in ids[0] if 0 <= i < len(papers)]
        for k in (5,10,20):
            if any(tmatch(p, gref) for p in ps[:k]): hit[k] += 1
    N = len(queries)
    print(f"{label:28s} top5={hit[5]/N*100:5.1f}%  top10={hit[10]/N*100:5.1f}%  top20={hit[20]/N*100:5.1f}%")

print(f"Format query (N={len(queries)}):")
run("1. teks polos", lambda s: s)
run("2. [SEP]+teks (judul kosong)", lambda s: f"{SEP}{s}")
print("\n(pembanding index lama: top5=64.6% top10=86.1% top20=93.1%)")

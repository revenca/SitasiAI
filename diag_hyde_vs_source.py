"""
Diagnosa: bandingkan recall gold paper antara embedding HyDE vs embedding source.
Tanpa same-paper exclusion (agar sebanding dgn baseline source 30.6%).
"""
import os
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
import re, json, faiss, torch
import numpy as np, pandas as pd
from dotenv import load_dotenv
from openai import OpenAI
from transformers import AutoTokenizer, AutoModel

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENROUTER_API_KEY"),
               base_url="https://openrouter.ai/api/v1",
               timeout=30.0, max_retries=1)   # cegah satu call nyangkut lama
GEN = "openai/gpt-4o-mini"
SAMPLE = 50   # jumlah paragraf sampel (None = semua 144)

tok = AutoTokenizer.from_pretrained("allenai/scibert_scivocab_uncased")
mdl = AutoModel.from_pretrained("allenai/scibert_scivocab_uncased"); mdl.eval()

def embed(t):
    x = tok(t, return_tensors="pt", truncation=True, max_length=512, padding=True)
    with torch.no_grad(): o = mdl(**x)
    e = torch.nn.functional.normalize(o.last_hidden_state[:, 0, :], dim=1)
    return e.squeeze().numpy()

def hyde(p):
    prompt = ("Given the following paragraph from a scientific paper, generate a "
        "hypothetical reference document (in the form of an abstract) that would be "
        "the most relevant citation for this paragraph. Write only the hypothetical "
        f"abstract, no explanation.\n\nSource paragraph:\n{p}")
    try:
        r = client.chat.completions.create(model=GEN,
            messages=[{"role": "user", "content": prompt}], temperature=0.4)
        return r.choices[0].message.content.strip()
    except Exception:
        return p

idx = faiss.read_index("faiss_index.bin")
meta = json.load(open("metadata.json", encoding="utf-8"))

def norm(s):
    s = str(s).strip(); s = re.sub(r"\.p?d?f?$", "", s); return s.strip().lower()
def tmatch(a, b):
    a, b = norm(a), norm(b)
    return bool(a and b and (a.startswith(b) or b.startswith(a)))

df = pd.read_csv("dataset_v1.csv"); ck = pd.read_csv("Ground_Truth/citation_checker_data.csv", sep=";")
H = ["V_H1","V_H2","V_H3","V_H4","V_H5","V_H6","V_H7"]
for c in H: ck[c] = ck[c].map({"TRUE":1,"FALSE":0,True:1,False:0}).fillna(0).astype(int)
df = df.iloc[:len(ck)].copy(); df["gt"] = (ck[H].sum(axis=1) >= 4).astype(int).values
gold = df[df["gt"] == 1].groupby("page_content_sumber")["title_paper_referensi"].apply(list).to_dict()

def topk_papers(vec, k=20):
    _, ids = idx.search(vec.reshape(1, -1).astype("float32"), k)
    return [meta[i]["paper_title"] for i in ids[0] if 0 <= i < len(meta)]

def recall_at(papers, golds, k):
    return any(tmatch(p, g) for p in papers[:k] for g in golds)

src = {5:0,10:0,20:0}; hyd = {5:0,10:0,20:0}; N = 0
items = list(gold.items())
if SAMPLE:
    import random; random.seed(42); random.shuffle(items); items = items[:SAMPLE]
print(f"Memproses {len(items)} paragraf...", flush=True)
for n, (s, golds) in enumerate(items, 1):
    ps = topk_papers(embed(str(s)))
    ph = topk_papers(embed(hyde(str(s))))
    for k in (5,10,20):
        if recall_at(ps, golds, k): src[k] += 1
        if recall_at(ph, golds, k): hyd[k] += 1
    N += 1
    if n % 10 == 0: print(f"  ...{n}/{len(items)}", flush=True)

print(f"\n{'='*46}")
print(f"  RECALL GOLD PAPER — N={N}")
print(f"{'='*46}")
print(f"  {'':8} {'SOURCE':>10} {'HyDE':>10}")
for k in (5,10,20):
    print(f"  top-{k:<3}  {src[k]/N*100:>9.1f}% {hyd[k]/N*100:>9.1f}%")
print(f"{'='*46}")

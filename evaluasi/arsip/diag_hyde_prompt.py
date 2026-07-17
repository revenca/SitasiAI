"""
Bandingkan recall gold paper: HyDE prompt LAMA vs BARU (lebih spesifik).
Generator = DeepSeek (api.deepseek.com), encoder = SPECTER, index lama (150-kata).
Sampel 50 paragraf gold. Tanpa OpenRouter.
"""
import os
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
import re, json, faiss, torch, random
import numpy as np, pandas as pd
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
from openai import OpenAI
from transformers import AutoTokenizer, AutoModel

load_dotenv()
client = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com",
                timeout=60, max_retries=2)
GEN = "deepseek-chat"

DEV = "cuda" if torch.cuda.is_available() else "cpu"
tok = AutoTokenizer.from_pretrained("allenai/specter")
mdl = AutoModel.from_pretrained("allenai/specter").eval().to(DEV)
_lock = __import__("threading").Lock()

def embed(text):
    with _lock:
        x = tok(text, return_tensors="pt", truncation=True, max_length=512, padding=True)
        x = {k: v.to(DEV) for k, v in x.items()}
        with torch.no_grad():
            o = mdl(**x)
        e = torch.nn.functional.normalize(o.last_hidden_state[:, 0, :], dim=1)
        return e.squeeze().cpu().numpy()

PROMPT_OLD = ("Given the following paragraph from a scientific paper, generate a "
    "hypothetical reference document (in the form of an abstract) that would be the "
    "most relevant citation for this paragraph. The hypothetical document should match "
    "the topic, methodology, findings, and domain of the source paragraph. Write only "
    "the hypothetical abstract, no explanation.\n\nSource paragraph:\n{p}")

PROMPT_NEW = ("You are helping identify the exact scientific paper that a given paragraph cites.\n"
    "First, identify the SPECIFIC claim, method, dataset, metric, or finding in the paragraph "
    "that needs a citation. Then write a detailed hypothetical abstract of the reference paper "
    "that DIRECTLY supports that specific claim.\n"
    "Requirements:\n"
    "- Use precise technical terms, method/model/algorithm names, datasets, and metrics that "
    "would appear in the actual cited paper.\n"
    "- State concrete methodology and specific quantitative findings/results.\n"
    "- Focus narrowly on the cited claim, not the broad topic.\n"
    "- Write as a real scientific abstract, no meta-commentary.\n\n"
    "Source paragraph:\n{p}")

def hyde(prompt, p):
    try:
        r = client.chat.completions.create(model=GEN,
            messages=[{"role": "user", "content": prompt.format(p=p)}], temperature=0.4)
        return r.choices[0].message.content.strip()
    except Exception:
        return p

def norm(s):
    s = str(s).strip(); s = re.sub(r"\.p?d?f?$", "", s); return s.strip().lower()
def tmatch(a, b):
    a, b = norm(a), norm(b)
    return bool(a and b and (a.startswith(b) or b.startswith(a)))

idx = faiss.read_index("faiss_index.bin"); meta = json.load(open("metadata.json", encoding="utf-8"))
papers = [m["paper_title"] for m in meta]

df = pd.read_csv("dataset_v1.csv"); ck = pd.read_csv("Ground_Truth/citation_checker_data.csv", sep=";")
H = ["V_H1","V_H2","V_H3","V_H4","V_H5","V_H6","V_H7"]
for c in H: ck[c] = ck[c].map({"TRUE":1,"FALSE":0,True:1,False:0}).fillna(0).astype(int)
df = df.iloc[:len(ck)].copy(); df["gt"] = (ck[H].sum(axis=1) >= 4).astype(int).values
gold = df[df["gt"] == 1].drop_duplicates("page_content_sumber")
items = list(zip(gold["page_content_sumber"], gold["title_paper_referensi"], gold["title_paper_sumber"]))
random.seed(42); random.shuffle(items); items = items[:50]
print(f"Sampel {len(items)} paragraf gold\n", flush=True)

def retrieve_recall(emb, gref, spaper):
    q = emb.reshape(1, -1).astype("float32")
    _, ids = idx.search(q, 30)
    ps = [papers[i] for i in ids[0] if 0 <= i < len(papers) and not tmatch(papers[i], spaper)]
    return {k: any(tmatch(p, gref) for p in ps[:k]) for k in (5, 10, 20)}

def work(item):
    src, gref, spaper = item
    eo = embed(hyde(PROMPT_OLD, str(src)))
    en = embed(hyde(PROMPT_NEW, str(src)))
    return retrieve_recall(eo, gref, spaper), retrieve_recall(en, gref, spaper)

old = {5:0,10:0,20:0}; new = {5:0,10:0,20:0}
with ThreadPoolExecutor(max_workers=8) as ex:
    for n, (ro, rn) in enumerate(ex.map(work, items), 1):
        for k in (5,10,20):
            old[k] += ro[k]; new[k] += rn[k]
        if n % 10 == 0: print(f"  ...{n}/{len(items)}", flush=True)

N = len(items)
print(f"\n{'='*46}")
print(f"  RECALL GOLD PAPER — HyDE prompt (N={N})")
print(f"{'='*46}")
print(f"  {'':8}{'LAMA':>10}{'BARU':>10}")
for k in (5,10,20):
    print(f"  top-{k:<3} {old[k]/N*100:>9.1f}%{new[k]/N*100:>9.1f}%")
print(f"{'='*46}")

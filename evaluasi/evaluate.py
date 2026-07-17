"""
evaluate.py — Evaluasi RAGAS (v0.2.x) untuk sistem citation recommendation.
Judge: DeepSeek (api.deepseek.com). Embeddings: SPECTER lokal (GPU).
"""
import os
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import json
import sys
import pandas as pd
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

# ── CONFIG ─────────────────────────────────────────────────────────────────────
GT_FILE           = "ground_truth_human.csv"
COL_SOURCE        = "page_content_sumber"
COL_REFERENCE     = "page_content_referensi"
COL_GT            = "ground_truth"

RESULTS_DIR       = "hasil_eksperimen"
os.makedirs(RESULTS_DIR, exist_ok=True)
_mode             = os.getenv("PIPELINE_MODE", "proposed")
_k                = os.getenv("TOP_K", "5")
PRED_FILE         = os.getenv("PRED_FILE",  f"{RESULTS_DIR}/hasil_prediksi_{_mode}_k{_k}.csv")
RAGAS_OUTPUT_FILE = os.getenv("RAGAS_FILE", f"{RESULTS_DIR}/hasil_ragas_{_mode}_k{_k}.csv")
META_FILE         = os.getenv("METADATA_FILE", "metadata.json")   # map chunk_text→paper_title; samakan dgn index yg dipakai pipeline

DEEPSEEK_API_KEY  = os.getenv("DEEPSEEK_API_KEY", "sk-GANTI_DENGAN_KEY_DEEPSEEK")
JUDGE_BASE_URL    = os.getenv("JUDGE_BASE_URL", "https://api.deepseek.com/v1")
JUDGE_MODEL       = os.getenv("JUDGE_MODEL", "deepseek-chat")

EMBED_MODEL       = "allenai/specter2_base"
EMBED_ADAPTER     = "allenai/specter2"
RAGAS_WORKERS     = int(os.getenv("RAGAS_WORKERS", "16"))   # turunkan kalau jalan paralel
CONTEXT_LIMIT     = int(os.getenv("CONTEXT_LIMIT", "0")) or None
# ───────────────────────────────────────────────────────────────────────────────


def load_ground_truth() -> pd.DataFrame:
    df = pd.read_csv(GT_FILE)
    df["ground_truth_label"] = (
        df[COL_GT].map({True: 1, False: 0, 1: 1, 0: 0, "TRUE": 1, "FALSE": 0})
        .fillna(0).astype(int)
    )
    return df


def build_ragas_samples(pred_df: pd.DataFrame, gt_df: pd.DataFrame) -> list:
    """Bangun list SingleTurnSample RAGAS 0.2.x — hanya paragraf bergold reference."""
    from ragas.dataset_schema import SingleTurnSample

    valid_refs = (
        gt_df[gt_df["ground_truth_label"] == 1]
        .groupby(COL_SOURCE)[COL_REFERENCE]
        .apply(list)
        .to_dict()
    )

    samples, n_skip = [], 0
    for _, row in pred_df.iterrows():
        para = str(row["source_paragraph"])
        refs = valid_refs.get(para, [])
        if not refs:
            n_skip += 1
            continue

        ctx_list = []
        if "retrieved_contexts" in row.index and pd.notna(row["retrieved_contexts"]):
            try:
                ctx_list = [c for c in json.loads(row["retrieved_contexts"]) if str(c).strip()]
            except (json.JSONDecodeError, TypeError):
                ctx_list = []
        if not ctx_list:
            single = str(row.get("retrieved_chunk", ""))
            ctx_list = [single] if single.strip() else [""]
        if CONTEXT_LIMIT:
            ctx_list = ctx_list[:CONTEXT_LIMIT]

        answer = str(row["citation_text"]) if pd.notna(row.get("citation_text")) else ""

        samples.append(SingleTurnSample(
            user_input=para,
            response=answer,
            retrieved_contexts=ctx_list,
            reference=str(refs[0]),
        ))

    print(f"  Paragraf dievaluasi : {len(samples)} (punya gold reference)")
    print(f"  Paragraf dilewati   : {n_skip} (tanpa gold reference)\n")

    if not samples:
        print("[ERROR] Tidak ada sampel. Cek alignment source_paragraph vs page_content_sumber.",
              file=sys.stderr)
        sys.exit(1)

    return samples


def build_local_embeddings():
    """Embeddings lokal SPECTER2 + proximity adapter (GPU) — tidak butuh API."""
    import torch
    from transformers import AutoTokenizer
    from adapters import AutoAdapterModel
    from ragas.embeddings import BaseRagasEmbeddings

    device = "cuda" if torch.cuda.is_available() else "cpu"
    tok = AutoTokenizer.from_pretrained(EMBED_MODEL)
    mdl = AutoAdapterModel.from_pretrained(EMBED_MODEL)
    mdl.load_adapter(EMBED_ADAPTER, source="hf", load_as="proximity", set_active=True)
    mdl.set_active_adapters("proximity")
    mdl.eval(); mdl.to(device)

    def _embed(texts):
        out = []
        for i in range(0, len(texts), 32):
            batch = [str(t) if t else " " for t in texts[i:i + 32]]
            x = tok(batch, return_tensors="pt", truncation=True, max_length=512, padding=True)
            x = {k: v.to(device) for k, v in x.items()}
            with torch.no_grad():
                o = mdl(**x)
            import torch.nn.functional as F
            e = F.normalize(o.last_hidden_state[:, 0, :], dim=1)
            out.extend(e.cpu().tolist())
        return out

    class LocalEmbeddings(BaseRagasEmbeddings):
        def embed_documents(self, texts):
            return _embed(list(texts))
        def embed_query(self, text):
            return _embed([text])[0]
        async def aembed_documents(self, texts):
            return self.embed_documents(texts)
        async def aembed_query(self, text):
            return self.embed_query(text)

    print(f"  Embeddings : {EMBED_MODEL} (lokal, device={device})")
    return LocalEmbeddings()


def run_ragas(samples: list) -> pd.DataFrame:
    from ragas import evaluate
    from ragas.dataset_schema import EvaluationDataset
    from ragas.metrics import Faithfulness, ResponseRelevancy
    from ragas.run_config import RunConfig
    from langchain_openai import ChatOpenAI

    # Judge LLM (DeepSeek langsung)
    lc_llm = ChatOpenAI(
        model=JUDGE_MODEL,
        openai_api_key=DEEPSEEK_API_KEY,
        openai_api_base=JUDGE_BASE_URL,
        temperature=0,
    )
    from ragas.llms import LangchainLLMWrapper
    llm = LangchainLLMWrapper(lc_llm)

    # Embeddings lokal
    embeddings = build_local_embeddings()

    # Metrik RAGAS (hanya Faithfulness + Answer Relevancy)
    faithfulness = Faithfulness(llm=llm)
    answer_rel   = ResponseRelevancy(llm=llm, embeddings=embeddings)

    # Set strictness=1 (DeepSeek tidak support n>1)
    if hasattr(answer_rel, "strictness"):
        answer_rel.strictness = 1

    run_config = RunConfig(max_workers=RAGAS_WORKERS, timeout=180, max_retries=5)
    dataset    = EvaluationDataset(samples=samples)

    print(f"Menjalankan evaluasi RAGAS {__import__('ragas').__version__}...")
    print(f"  Dataset  : {len(samples)} baris")
    print(f"  Metrik   : Faithfulness + Answer Relevancy")
    print(f"  Judge    : {JUDGE_MODEL} (api.deepseek.com)")
    print(f"  Paralel  : {RAGAS_WORKERS} worker\n")

    result = evaluate(
        dataset=dataset,
        metrics=[faithfulness, answer_rel],
        run_config=run_config,
        raise_exceptions=False,
    )

    return result.to_pandas()


def citation_metrics(pred_df: pd.DataFrame, gt_df: pd.DataFrame, meta_file: str = None) -> dict:
    """
    Citation-level evaluation (paper-level, gratis, tanpa API).
    Cocok untuk dibandingkan langsung dengan TA-BGELarge.
    """
    import re

    def norm(s):
        s = str(s).strip()
        s = re.sub(r"\.p?d?f?$", "", s)
        return s.strip().lower()

    def tmatch(a, b):
        a, b = norm(a), norm(b)
        return bool(a and b and (a.startswith(b) or b.startswith(a)))

    # Map chunk_text → paper_title (untuk tahu paper dari tiap chunk di contexts)
    chunk2paper = {}
    try:
        meta = json.load(open(meta_file or META_FILE, encoding="utf-8"))
        for m in meta:
            chunk2paper[m["chunk_text"][:80]] = m["paper_title"]
    except Exception:
        pass
    def paper_of(chunk):
        return chunk2paper.get(str(chunk)[:80], "")

    # Gold: source_paragraph → list gold paper titles
    gold_map = (
        gt_df[gt_df["ground_truth_label"] == 1]
        .groupby(COL_SOURCE)["title_paper_referensi"]
        .apply(list)
        .to_dict()
    )

    cp_list, cr_list, f_list, hit_list = [], [], [], []

    for _, row in pred_df.iterrows():
        para   = str(row["source_paragraph"])
        golds  = gold_map.get(para, [])
        if not golds:
            continue

        # Retrieved chunks → UNIQUE paper titles (definisi paper-level ala TA-BGELarge)
        try:
            contexts = json.loads(row["retrieved_contexts"]) if pd.notna(row.get("retrieved_contexts")) else []
        except Exception:
            contexts = []

        retrieved_papers = set()
        for c in contexts:
            p = paper_of(c)
            if p.strip():
                retrieved_papers.add(p)
        if not retrieved_papers:  # fallback ke paper terpilih
            rp = str(row.get("retrieved_paper", ""))
            if rp.strip():
                retrieved_papers.add(rp)

        # Gold unik (dedup judul yg prefix-sama)
        gold_unique = []
        for g in golds:
            if not any(tmatch(g, gu) for gu in gold_unique):
                gold_unique.append(g)

        n_relevant  = len(gold_unique)
        n_retrieved = max(len(retrieved_papers), 1)
        hits        = sum(1 for g in gold_unique if any(tmatch(r, g) for r in retrieved_papers))

        cp  = hits / n_retrieved if n_retrieved > 0 else 0.0
        cr  = hits / n_relevant  if n_relevant > 0 else 0.0
        f   = 2*cp*cr / (cp+cr)  if (cp+cr) > 0 else 0.0
        hit = 1.0 if hits > 0 else 0.0

        cp_list.append(cp); cr_list.append(cr)
        f_list.append(f);   hit_list.append(hit)

    N = len(cp_list)
    return {
        "citation_precision": sum(cp_list)/N if N else 0,
        "citation_recall":    sum(cr_list)/N if N else 0,
        "f_measure":          sum(f_list)/N  if N else 0,
        "hit_at_k":           sum(hit_list)/N if N else 0,
        "n_queries":          N,
    }


def _categorize(title: str) -> str:
    t = str(title).lower()
    if any(k in t for k in ["segmentation","detection","yolo","cnn","image","vision","carving","batik","convnext","mobilenet","lesion","endoscopy","u-net","printing"]): return "Computer Vision"
    if any(k in t for k in ["sign language","javanese","sarcasm","entailment","named entity","transliteration","word segmentation"]): return "NLP"
    if any(k in t for k in ["mimo","radar","ofdm","lora","hevc","positioning","reconfigurable"]): return "Telecom/Radar"
    if any(k in t for k in ["power","photovoltaic","battery","wind","energy","grid","generator","transmission","scooter","ultracapacitor","charge"]): return "Power/Energy"
    if any(k in t for k in ["eeg","brain","emotion","epileptic"]): return "Biosignal/EEG"
    if any(k in t for k in ["drone","uav","flight log","aircraft"]): return "Drone/UAV"
    if any(k in t for k in ["electronic nose","e-nose","sensor","isfet","cookies","tea"]): return "E-Nose/Sensor"
    if any(k in t for k in ["cobit","process mining","microservice","api","code smell","conformance","governance"]): return "Software Eng/IT"
    if any(k in t for k in ["forecasting","stock","credit","prediction","classification","intrusion","diabetes","imputation"]): return "ML/Forecasting"
    if any(k in t for k in ["timetabling","optimization","colony","nearest neighbor"]): return "Optimization"
    return "Lainnya"


def per_topic_breakdown(pred_df: pd.DataFrame, gt_df: pd.DataFrame, ragas_df: pd.DataFrame):
    """Breakdown Hit@K, Recall@K, Faithfulness, Answer Relevancy per kategori topik."""
    import re
    def norm(s):
        s = str(s).strip(); s = re.sub(r"\.p?d?f?$", "", s); return s.strip().lower()
    def tmatch(a, b):
        a, b = norm(a), norm(b); return bool(a and b and (a.startswith(b) or b.startswith(a)))

    chunk2paper = {}
    try:
        for m in json.load(open(META_FILE, encoding="utf-8")):
            chunk2paper[m["chunk_text"][:80]] = m["paper_title"]
    except Exception:
        pass
    def paper_of(c): return chunk2paper.get(str(c)[:80], "")

    valid = gt_df[gt_df["ground_truth_label"] == 1]
    gold_ref = valid.groupby(COL_SOURCE)["title_paper_referensi"].apply(list).to_dict()
    src_paper = valid.groupby(COL_SOURCE)["title_paper_sumber"].first().to_dict()
    fa_map = {str(r["user_input"]): r.get("faithfulness") for _, r in ragas_df.iterrows()}
    ar_col = "answer_relevancy" if "answer_relevancy" in ragas_df.columns else "response_relevancy"
    ar_map = {str(r["user_input"]): r.get(ar_col) for _, r in ragas_df.iterrows()}

    cats = {}
    for _, row in pred_df.iterrows():
        para = str(row["source_paragraph"]); golds = gold_ref.get(para, [])
        if not golds: continue
        cat = _categorize(src_paper.get(para, ""))
        try: ctxs = json.loads(row["retrieved_contexts"]) if pd.notna(row.get("retrieved_contexts")) else []
        except Exception: ctxs = []
        rp = set(paper_of(c) for c in ctxs if paper_of(c))
        gu = []
        for g in golds:
            if not any(tmatch(g, x) for x in gu): gu.append(g)
        hits = sum(1 for g in gu if any(tmatch(r, g) for r in rp))
        prec = hits/max(len(rp),1); rec = hits/max(len(gu),1); hit = 1.0 if hits>0 else 0.0
        d = cats.setdefault(cat, {"prec":[],"rec":[],"hit":[],"fa":[],"ar":[]})
        d["prec"].append(prec); d["rec"].append(rec); d["hit"].append(hit)
        if fa_map.get(para) is not None and not pd.isna(fa_map.get(para)): d["fa"].append(fa_map[para])
        if ar_map.get(para) is not None and not pd.isna(ar_map.get(para)): d["ar"].append(ar_map[para])

    print("\n" + "=" * 60)
    print(f"  PER KATEGORI TOPIK (mode={_mode}, K={_k})")
    print("=" * 60)
    print(f"  {'Kategori':<18}{'N':>4}{'Prec@K':>9}{'Recall@K':>10}{'Hit@K':>8}{'Faith':>8}")
    print("  " + "-" * 57)
    rows = []
    for cat in sorted(cats, key=lambda c: -len(cats[c]["hit"])):
        d = cats[cat]; n = len(d["hit"])
        prec = sum(d["prec"])/n; rec = sum(d["rec"])/n; hit = sum(d["hit"])/n
        fa  = sum(d["fa"])/len(d["fa"]) if d["fa"] else 0
        ar  = sum(d["ar"])/len(d["ar"]) if d["ar"] else 0
        print(f"  {cat:<18}{n:>4}{prec:>9.3f}{rec:>10.3f}{hit:>8.3f}{fa:>8.3f}")
        rows.append({"kategori": cat, "n": n, "precision_at_k": round(prec,4),
                     "recall_at_k": round(rec,4), "hit_at_k": round(hit,4),
                     "faithfulness": round(fa,4), "answer_relevancy": round(ar,4)})

    # Ringkasan: berapa kategori "kuat" (Hit@K >= 0.8)
    n_strong = sum(1 for r in rows if r["hit_at_k"] >= 0.8)
    print("  " + "-" * 56)
    print(f"  Kategori dengan Hit@K >= 0.8 : {n_strong} / {len(rows)} topik")
    print("=" * 60)

    # Simpan ke CSV
    topic_file = RAGAS_OUTPUT_FILE.replace(".csv", "_topic.csv")
    pd.DataFrame(rows).to_csv(topic_file, index=False, encoding="utf-8")
    print(f"Per-topik disimpan       → '{topic_file}'")


def print_summary(ragas_df: pd.DataFrame, cite: dict):
    def mean(df, *names):
        for n in names:
            if n in df.columns:
                return df[n].dropna().mean()
        return float("nan")

    f  = mean(ragas_df, "faithfulness")
    ar = mean(ragas_df, "answer_relevancy", "response_relevancy")

    print("\n" + "=" * 50)
    print(f"  MODE: {_mode.upper()}")
    print("=" * 50)
    print("  [Retrieval Metrics — paper-level]")
    print(f"  Precision@K         : {cite['citation_precision']:.4f}")
    print(f"  Recall@K            : {cite['citation_recall']:.4f}")
    print(f"  Hit@K               : {cite['hit_at_k']:.4f}")
    print(f"  F-measure@K         : {cite['f_measure']:.4f}")
    print()
    print("  [Generation Metrics — RAGAS, LLM judge]")
    print(f"  Faithfulness        : {f:.4f}")
    print(f"  Answer Relevancy    : {ar:.4f}")
    print("=" * 50)
    print(f"  Total baris eval    : {cite['n_queries']}")
    print("=" * 50)


def main():
    for path in (GT_FILE, PRED_FILE):
        if not Path(path).exists():
            print(f"[ERROR] File tidak ditemukan: '{path}'", file=sys.stderr)
            if path == PRED_FILE:
                print("  → Jalankan pipeline.py terlebih dahulu.", file=sys.stderr)
            sys.exit(1)

    if DEEPSEEK_API_KEY.startswith("sk-GANTI"):
        print("[ERROR] DEEPSEEK_API_KEY belum diset di .env", file=sys.stderr)
        sys.exit(1)

    print("Memuat data...")
    pred_df = pd.read_csv(PRED_FILE)
    gt_df   = load_ground_truth()
    print(f"  Prediksi  : {len(pred_df)} baris ({PRED_FILE})")
    print(f"  GT valid  : {int((gt_df['ground_truth_label']==1).sum())} baris\n")

    samples   = build_ragas_samples(pred_df, gt_df)
    result_df = run_ragas(samples)
    cite      = citation_metrics(pred_df, gt_df)

    result_df.to_csv(RAGAS_OUTPUT_FILE, index=False, encoding="utf-8")

    # Simpan citation metric ke CSV terpisah
    cite_file = RAGAS_OUTPUT_FILE.replace(".csv", "_citation.csv")
    pd.DataFrame([cite]).to_csv(cite_file, index=False, encoding="utf-8")
    print(f"\nHasil RAGAS disimpan     → '{RAGAS_OUTPUT_FILE}'")
    print(f"Hasil citation disimpan  → '{cite_file}'")

    print_summary(result_df, cite)
    per_topic_breakdown(pred_df, gt_df, result_df)


if __name__ == "__main__":
    main()

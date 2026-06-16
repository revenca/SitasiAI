"""
backend/rag_engine.py — Core RAG engine untuk rekomendasi sitasi.
Mandiri (tidak bergantung skrip eksperimen). Komponen:
  SPECTER2 (embedding) + FAISS (retrieval) + GPT-4o-mini (HyDE & CoT).
"""
import os
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import re
import json
import faiss
import torch
from pathlib import Path
from openai import OpenAI
from transformers import AutoTokenizer
from adapters import AutoAdapterModel

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── Path (root proyek = parent dari folder backend) ──────────────────────────
ROOT        = Path(__file__).resolve().parent.parent
INDEX_FILE  = str(ROOT / "faiss_index.bin")
META_FILE   = str(ROOT / "metadata.json")
PAPER_META  = ROOT / "paper_meta.json"        # fallback regex: judul → {authors[], year}
CURATED_META = ROOT / "paper_metadata.json"   # kurasi: judul → {first_author, year}

# ── Konfigurasi ──────────────────────────────────────────────────────────────
MODEL_NAME   = "allenai/specter2_base"
ADAPTER_NAME = "allenai/specter2"
GEN_MODEL    = os.getenv("GEN_MODEL", "openai/gpt-4o-mini")
OPENROUTER_API_KEY  = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

_tokenizer = _model = _device = _index = _metadata = _client = None
_papermeta = {}     # fallback regex
_curated = {}       # metadata kurasi (first_author + year)


def _meta(title: str):
    """Return (authors_display, year, apa_key) — prioritaskan metadata kurasi."""
    cur = _curated.get(title) or {}
    fa = (cur.get("first_author") or "").strip()
    yr = (cur.get("year") or "").strip()
    if fa and fa != "Unknown":
        year = yr or "n.d."
        return f"{fa} et al.", year, f"{fa} et al., {year}"

    # fallback ke ekstraksi regex lokal
    pm = _papermeta.get(title) or {}
    al = pm.get("authors") or []
    yr2 = (pm.get("year") or "").strip()
    if al:
        surname = al[0].split()[-1]
        disp = al[0] + " et al." if len(al) > 1 else al[0]
        year = yr2 or "n.d."
        return disp, year, f"{surname} et al., {year}"
    return "", (yr2 or ""), ""


def init():
    """Muat model + index sekali (lazy)."""
    global _tokenizer, _model, _device, _index, _metadata, _client, _papermeta, _curated
    if _model is not None:
        return
    if PAPER_META.exists():
        _papermeta = json.load(open(PAPER_META, encoding="utf-8"))
    if CURATED_META.exists():
        _curated = json.load(open(CURATED_META, encoding="utf-8"))
    _tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    _model     = AutoAdapterModel.from_pretrained(MODEL_NAME)
    _model.load_adapter(ADAPTER_NAME, source="hf", load_as="proximity", set_active=True)
    _model.set_active_adapters("proximity")
    _model.eval()
    _device = "cuda" if torch.cuda.is_available() else "cpu"
    _model.to(_device)
    _index    = faiss.read_index(INDEX_FILE)
    _metadata = json.load(open(META_FILE, encoding="utf-8"))
    _client   = OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL,
                       default_headers={"HTTP-Referer": "citation-rec", "X-Title": "Citation Recommender"})


def _call_llm(prompt: str, temperature: float = 0.3) -> str:
    for _ in range(3):
        try:
            r = _client.chat.completions.create(
                model=GEN_MODEL, messages=[{"role": "user", "content": prompt}],
                temperature=temperature)
            return r.choices[0].message.content.strip()
        except Exception:
            continue
    return ""


def embed(text: str):
    x = _tokenizer(text, return_tensors="pt", truncation=True, max_length=512, padding=True)
    x = {k: v.to(_device) for k, v in x.items()}
    with torch.no_grad():
        o = _model(**x)
    e = torch.nn.functional.normalize(o.last_hidden_state[:, 0, :], dim=1)
    return e.squeeze().cpu().numpy()


def hyde_generate(paragraph: str) -> str:
    prompt = (
        "Act as an expert computer science researcher. Read the following draft paragraph that requires a technical citation. "
        "Generate a hypothetical paper abstract that perfectly supports the core claims in the paragraph. "
        "This abstract will be used for dense vector retrieval against a technical database.\n\n"
        "Strict Rules:\n"
        "1. Format & Length: Strictly 1 continuous paragraph, around 100-150 words. Output ONLY the abstract text.\n"
        "2. Semantic Density: Maximize specific algorithms, frameworks, methodologies, or evaluation metrics.\n"
        "3. IEEE Structure: Start with the core contribution, state the setup, conclude with results.\n\n"
        f"Draft Paragraph:\n{paragraph}"
    )
    return _call_llm(prompt, temperature=0.4)


def retrieve(query_emb, top_k: int = 5, pool_mult: int = 8):
    """Cari kandidat lalu dedupe per paper → Top-K paper UNIK (skor tertinggi)."""
    import numpy as np
    q = query_emb.reshape(1, -1).astype(np.float32)
    k = min(top_k * pool_mult, _index.ntotal)
    scores, idxs = _index.search(q, k)
    out, seen = [], set()
    for s, i in zip(scores[0], idxs[0]):
        if not (0 <= i < len(_metadata)):
            continue
        title = _metadata[i]["paper_title"]
        if title in seen:          # ambil hanya chunk terbaik per paper
            continue
        seen.add(title)
        authors, year, apa = _meta(title)
        out.append({"paper_title": title,
                    "authors": authors, "year": year, "citation": apa,
                    "chunk_text": _metadata[i]["chunk_text"], "score": float(s)})
        if len(out) >= top_k:
            break
    return out


def cot_generate(paragraph: str, chunks: list) -> dict:
    if not chunks:
        return {"relevant": False, "citation_text": "", "best_reference_paper": "", "reasoning": ""}
    formatted = "\n---\n".join(
        f"[Reference {i+1}] {c['paper_title']}:\n{c['chunk_text']}" for i, c in enumerate(chunks))
    prompt = (
        "You are an academic citation assistant. Use chain-of-thought reasoning to "
        "determine relevance and generate a citation.\n\n"
        f"Source paragraph (needs citation):\n{paragraph}\n\n"
        f"Retrieved reference content:\n{formatted}\n\n"
        "Think step by step:\n"
        "Step 1: What is the main claim/method/finding in the source paragraph?\n"
        "Step 2: What specific facts does each retrieved reference contain?\n"
        "Step 3: Which reference most directly supports the source claim (by overlap of facts)?\n"
        "Step 4: Is the best reference truly relevant? (Yes/No)\n"
        "Step 5: If relevant, write ONE coherent academic sentence (in the SAME language as the "
        "source paragraph) that explains what the chosen reference contributes or demonstrates "
        "in relation to the source claim, as it would appear in a literature review.\n"
        "  Rules for the sentence:\n"
        "  - Describe the method/approach/finding at a conceptual level (what & why), do NOT dump "
        "raw numbers, statistics, dataset sizes, or copy the abstract verbatim.\n"
        "  - It must be grounded in the chosen reference (no invented facts) but should READ "
        "naturally and clearly explain the connection — not just list facts.\n"
        "  - Do NOT include the paper title inside the sentence.\n\n"
        "Output format (JSON only):\n"
        '{ "relevant": true, "best_reference_paper": "title", '
        '"best_reference_chunk": "chunk", "citation_text": "sentence or null", "reasoning": "brief" }'
    )
    raw = _call_llm(prompt, temperature=0.2)
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip()); raw = re.sub(r"\s*```$", "", raw)
    try:
        r = json.loads(raw)
        r["relevant"] = bool(r.get("relevant", False))
        for k in ("best_reference_paper", "best_reference_chunk", "citation_text", "reasoning"):
            v = r.get(k); r[k] = "" if v in (None, "null") else str(v)
        return r
    except json.JSONDecodeError:
        return {"relevant": False, "citation_text": "", "best_reference_paper": "", "reasoning": ""}


def simple_generate(paragraph: str, chunks: list) -> dict:
    if not chunks:
        return {"relevant": False, "citation_text": "", "best_reference_paper": "", "reasoning": ""}
    formatted = "\n---\n".join(
        f"[Ref {i+1}] {c['paper_title']}\n{c['chunk_text']}" for i, c in enumerate(chunks))
    prompt = (
        "You are an academic citation assistant. Select the reference whose content most "
        "directly supports the source claim, then write a one-sentence citation stating ONLY "
        "facts explicitly present in the chosen reference.\n\n"
        f"Source paragraph:\n{paragraph}\n\nReferences:\n{formatted}\n\n"
        'Output JSON: { "relevant": true, "best_reference_paper": "title", '
        '"best_reference_chunk": "chunk", "citation_text": "sentence or null", "reasoning": "brief" }'
    )
    raw = _call_llm(prompt, temperature=0.2)
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip()); raw = re.sub(r"\s*```$", "", raw)
    try:
        r = json.loads(raw)
        r["relevant"] = bool(r.get("relevant", False))
        for k in ("best_reference_paper", "best_reference_chunk", "citation_text", "reasoning"):
            v = r.get(k); r[k] = "" if v in (None, "null") else str(v)
        return r
    except json.JSONDecodeError:
        return {"relevant": False, "citation_text": "", "best_reference_paper": "", "reasoning": ""}


def answer_question(question: str, top_k: int = 5) -> dict:
    """Tanya-jawab: ambil konteks korpus lalu jawab dengan GPT-4o-mini.
    Untuk pertanyaan umum, model menjawab dari pengetahuannya."""
    init()
    emb = embed(question)
    ctx = retrieve(emb, top_k=top_k)
    context = "\n---\n".join(
        f"[{c['paper_title']}] {c['chunk_text'][:500]}" for c in ctx)
    prompt = (
        "You are a helpful research assistant for SitasiAI, a citation recommendation "
        "system over a corpus of 100 academic papers (ITS). Answer the user's question "
        "clearly and concisely, in the SAME language as the question.\n"
        "- If the question relates to the papers/corpus, ground your answer in the context below "
        "and mention relevant paper titles.\n"
        "- If it is a general question, answer from your own knowledge.\n"
        "- Keep it brief (2-5 sentences) unless more detail is clearly needed.\n\n"
        f"Context from corpus:\n{context}\n\n"
        f"Question: {question}\n\nAnswer:"
    )
    ans = _call_llm(prompt, temperature=0.4)
    return {"answer": ans or "Maaf, tidak ada jawaban.", "candidates": ctx}


def cite_rewrite(paragraph: str, citation_key: str) -> str:
    """Tulis ulang paragraf jadi kalimat akademik formal + sisipkan sitasi in-text.
    TIDAK mengarang fakta baru — hanya memformalkan kalimat pengguna."""
    if not citation_key:
        return ""
    prompt = (
        "Rewrite the following draft sentence(s) into a polished, formal academic version "
        "in the SAME language as the input, and insert the in-text citation marker exactly as "
        f"\"({citation_key})\" at the most appropriate position (right after the claim it supports).\n"
        "Strict rules:\n"
        "- Preserve the original meaning. Do NOT invent specific facts, numbers, percentages, "
        "mechanisms, or claims that are not stated in the original text.\n"
        "- Keep it concise (1-2 sentences). Output ONLY the rewritten text, no quotes, no preamble.\n\n"
        f"Draft:\n{paragraph}"
    )
    out = _call_llm(prompt, temperature=0.3)
    return out or ""


def recommend(paragraph: str, top_k: int = 5, use_hyde: bool = True, use_cot: bool = True) -> dict:
    """
    Pipeline lengkap: (HyDE) → embed → retrieve → (CoT/simple).
    Return: { citation_text, best_reference_paper, relevant, reasoning, candidates[] }
    """
    init()
    query = hyde_generate(paragraph) or paragraph if use_hyde else paragraph
    emb = embed(query)
    candidates = retrieve(emb, top_k=top_k)
    gen = (cot_generate(paragraph, candidates) if use_cot
           else simple_generate(paragraph, candidates))

    # cocokkan paper referensi terbaik dengan kandidat (untuk penulis/tahun/skor)
    best_title = gen.get("best_reference_paper", "")
    ref = next((c for c in candidates if c["paper_title"] == best_title), None)
    if ref is None and best_title:
        ref = next((c for c in candidates
                    if best_title.lower() in c["paper_title"].lower()
                    or c["paper_title"].lower() in best_title.lower()), None)
    if ref is None and candidates:
        ref = candidates[0]

    # Tulis ulang akademik + sisip sitasi (untuk mode Automated Citation)
    apa_key = ref.get("citation", "") if ref else ""
    cited_paragraph = cite_rewrite(paragraph, apa_key) if (gen.get("relevant") and apa_key) else ""

    return {
        "citation_text":           gen.get("citation_text", ""),
        "best_reference_paper":    ref["paper_title"] if ref else best_title,
        "best_reference_authors":  ref.get("authors", "") if ref else "",
        "best_reference_year":     ref.get("year", "") if ref else "",
        "best_reference_score":    ref.get("score") if ref else None,
        "best_reference_citation": apa_key,
        "cited_paragraph":         cited_paragraph,
        "relevant":                gen.get("relevant", False),
        "reasoning":               gen.get("reasoning", ""),
        "candidates":              candidates,
    }

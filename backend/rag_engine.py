"""
backend/rag_engine.py — Core RAG engine untuk rekomendasi sitasi.
Mandiri (tidak bergantung skrip eksperimen). Komponen:
  SPECTER2 (embedding) + FAISS (retrieval) + GPT-4o-mini (HyDE & CoT).
"""
import os
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import re
import json
import time
import faiss
import torch
import requests
import numpy as np
import threading
from concurrent.futures import ThreadPoolExecutor

_embed_lock = threading.Lock()   # model embedding satu, panggilan paralel harus antre
from pathlib import Path
from openai import OpenAI
from transformers import AutoTokenizer
from adapters import AutoAdapterModel

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── Path (data backend disimpan di backend/database/) ────────────────────────
ROOT        = Path(__file__).resolve().parent.parent
DB          = Path(__file__).resolve().parent / "data"       # backend/data/
INDEX_FILE  = str(DB / "faiss_index.bin")     # index chunk CLEAN
META_FILE   = str(DB / "metadata.json")
PAPER_META  = DB / "paper_meta.json"          # fallback regex: judul → {authors[], year}
CURATED_META = DB / "paper_metadata.json"     # kurasi: judul → {first_author, year}

# ── Konfigurasi ──────────────────────────────────────────────────────────────
MODEL_NAME   = "allenai/specter2_base"
ADAPTER_NAME = "allenai/specter2"
GEN_MODEL    = os.getenv("GEN_MODEL", "openai/gpt-4o-mini")
OPENROUTER_API_KEY  = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# ── Penjaga presisi sitasi (anti false-positive) ─────────────────────────────
# Lapis 1: gerbang skor — kandidat harus >= MIN_SIM DAN dalam jendela REL_WIN dari terbaik.
# Lapis 3: verifikasi LLM independen atas referensi terpilih (lihat _verify_support).
MIN_SIM  = float(os.getenv("MIN_SIM", "0.70"))    # ambang cosine absolut (buang sampah)
REL_WIN  = float(os.getenv("REL_WIN", "0.08"))    # jendela relatif thd skor tertinggi
VERIFY_CITATION = os.getenv("VERIFY_CITATION", "1") == "1"


def _gate_candidates(cands: list) -> list:
    """Saring kandidat: skor >= MIN_SIM dan tidak jauh di bawah kandidat terbaik."""
    if not cands:
        return []
    top = max(c.get("score", 0.0) for c in cands)
    return [c for c in cands
            if c.get("score", 0.0) >= MIN_SIM and c.get("score", 0.0) >= top - REL_WIN]


def _verify_support(claim: str, ref: dict) -> bool:
    """Lapis 3: pemeriksaan independen — apakah referensi BENAR-BENAR mendukung klaim
    spesifik (bukan sekadar setopik). Gagal verifikasi → sitasi ditolak."""
    if not VERIFY_CITATION or not ref:
        return True
    out = _call_llm(
        "You are a strict citation auditor. Decide whether the reference DIRECTLY supports "
        "the SPECIFIC claim below — same finding, method, or fact. Being on the same broad "
        "topic is NOT enough. When in doubt, answer NO.\n\n"
        f"Claim:\n{claim[:800]}\n\n"
        f"Reference title: {ref.get('paper_title','')}\n"
        f"Reference abstract: {(ref.get('chunk_text') or '')[:900]}\n\n"
        "Answer with exactly one word: YES or NO.",
        temperature=0)
    return out.strip().upper().startswith("Y")


# ── Setup HyDE — DISAMAKAN dengan eksperimen (run_phyde_endtoend.ps1) ─────────
# Proper HyDE (Gao et al.): N abstrak hipotetis + embedding query, dirata-rata + L2-norm.
HYDE_TEMP = float(os.getenv("HYDE_TEMP", "0.7"))              # eval: 0.7
HYDE_N    = int(os.getenv("HYDE_N", "5"))                     # eval: 5 abstrak
HYDE_INCLUDE_QUERY = os.getenv("HYDE_INCLUDE_QUERY", "1") == "1"  # eval: sertakan query
HYDE_WORDS = os.getenv("HYDE_WORDS", "100-150")             # eval: 100-150 kata
COT_TEMP  = float(os.getenv("COT_TEMP", "0.2"))              # eval: 0.2

_tokenizer = _model = _device = _index = _metadata = _client = None
_papermeta = {}     # fallback regex
_curated = {}       # metadata kurasi (first_author + year)


def _meta(title: str):
    """Return (authors_display, year, apa_key) — prioritaskan metadata kurasi;
    tahun jatuh ke ekstraksi regex bila kurasi kosong / 'n.d.'."""
    cur = _curated.get(title) or {}
    pm  = _papermeta.get(title) or {}
    yr2 = (pm.get("year") or "").strip()               # tahun regex (fallback)
    fa = (cur.get("first_author") or "").strip()
    yr = (cur.get("year") or "").strip()
    if fa and fa != "Unknown":
        year = yr if (yr and yr.lower() != "n.d.") else (yr2 or "n.d.")
        return f"{fa} et al.", year, f"{fa} et al., {year}"

    # fallback ke ekstraksi regex lokal
    al = pm.get("authors") or []
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
    _build_llm_chain()


# ── Rantai LLM 3 tingkat: Groq (gratis) → OpenRouter/GPT-4o-mini → DeepSeek ──
# Tiap provider dicoba berurutan; 429/limit/saldo habis → lanjut provider berikut.
GROQ_API_KEY   = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL     = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
DEEPSEEK_KEY   = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
_llm_chain: list = []          # [(nama, client, model), ...] urut prioritas


def _build_llm_chain():
    global _llm_chain
    chain = []
    if GROQ_API_KEY:
        chain.append(("groq", OpenAI(api_key=GROQ_API_KEY,
                                     base_url="https://api.groq.com/openai/v1"), GROQ_MODEL))
    chain.append(("openrouter", _client, GEN_MODEL))
    if DEEPSEEK_KEY:
        chain.append(("deepseek", OpenAI(api_key=DEEPSEEK_KEY,
                                         base_url="https://api.deepseek.com"), DEEPSEEK_MODEL))
    _llm_chain = chain
    print("[LLM chain]", " -> ".join(f"{n}({m})" for n, _, m in chain))


def _call_llm(prompt: str, temperature: float = 0.3) -> str:
    """Coba tiap provider dalam rantai (2 percobaan per provider).
    Limit/error → jatuh ke provider berikutnya. Return "" bila semua gagal."""
    for name, client, model in (_llm_chain or [("openrouter", _client, GEN_MODEL)]):
        for attempt in range(2):
            try:
                r = client.chat.completions.create(
                    model=model, messages=[{"role": "user", "content": prompt}],
                    temperature=temperature, timeout=60)
                out = (r.choices[0].message.content or "").strip()
                if out:
                    return out
            except Exception as e:
                msg = str(e).lower()
                # limit/kuota/saldo → tak usah retry provider ini, langsung pindah
                if any(k in msg for k in ("429", "rate", "quota", "insufficient",
                                          "credit", "balance", "402")):
                    break
                time.sleep(0.5)
    return ""


def embed(text: str):
    with _embed_lock:                 # aman dipanggil dari beberapa thread
        x = _tokenizer(text, return_tensors="pt", truncation=True, max_length=512, padding=True)
        x = {k: v.to(_device) for k, v in x.items()}
        with torch.no_grad():
            o = _model(**x)
        e = torch.nn.functional.normalize(o.last_hidden_state[:, 0, :], dim=1)
        return e.squeeze().cpu().numpy()


def hyde_generate(paragraph: str) -> str:
    """Citation-Aware HyDE (domain-agnostic) — IDENTIK dgn pipeline eval: abstrak hipotetis
    yang mendukung klaim paragraf, menyimpulkan domain riset dari paragraf (BUKAN asumsi CS)."""
    prompt = (
        "You are an expert academic researcher writing in the style of a peer-reviewed "
        "scientific paper. Read the following draft paragraph that requires a technical "
        "citation. Generate a hypothetical paper abstract that would directly support the "
        "core claims in the paragraph. This abstract will be used for dense vector retrieval "
        "against a scientific paper database.\n\n"
        "Strict Rules:\n"
        f"1. Format & Length: Output ONLY one continuous abstract paragraph of approximately "
        f"{HYDE_WORDS} words. No title, no preamble, no closing remarks.\n"
        "2. Domain Fidelity: Infer the specific research domain from the paragraph "
        "(e.g., telecommunications, chemical sensing, computer vision, software engineering) "
        "and use the terminology, methods, and conventions native to THAT domain. "
        "Do not assume the domain is computer science.\n"
        "3. Semantic Density: Maximize specific technical terms — algorithms, frameworks, "
        "instruments, datasets, or evaluation metrics — that would plausibly appear in the "
        "paper being cited.\n"
        "4. IEEE Structure: Begin with the core contribution (e.g., 'This paper presents...', "
        "'We propose...'), briefly state the methodology or experimental setup, and conclude "
        "with the key empirical findings.\n"
        "5. Grounding: Stay faithful to the claims in the draft. Do not introduce findings "
        "that contradict or drift away from the paragraph's actual topic.\n\n"
        f"Draft Paragraph:\n{paragraph}"
    )
    return _call_llm(prompt, temperature=HYDE_TEMP)


def hyde_embed(paragraph: str):
    """Proper HyDE (Gao et al.) — SAMA PERSIS dgn pipeline eksperimen:
    generate HYDE_N abstrak hipotetis → embed tiap abstrak → (opsional) sertakan
    embedding paragraf asli → RATA-RATA + normalisasi L2.
    Fallback ke embedding paragraf bila semua generasi HyDE gagal."""
    # 5 generasi HyDE dijalankan PARALEL (I/O-bound) → potong latensi ~N× untuk web.
    # Hasil statistik tetap identik dgn eval (konten stokastik, urutan tak berpengaruh).
    if HYDE_N > 1:
        with ThreadPoolExecutor(max_workers=HYDE_N) as ex:
            hyps = [h for h in ex.map(lambda _: hyde_generate(paragraph), range(HYDE_N)) if h]
    else:
        hyps = [h for h in (hyde_generate(paragraph) for _ in range(HYDE_N)) if h]
    vecs = [embed(h) for h in hyps]           # embed tiap abstrak (torch, sekuensial)
    if HYDE_INCLUDE_QUERY or not vecs:        # sertakan paragraf asli (hybrid) / fallback
        vecs.append(embed(paragraph))
    qv = np.mean(np.vstack(vecs), axis=0)
    return (qv / (np.linalg.norm(qv) + 1e-12)).astype(np.float32)


def retrieve(query_emb, top_k: int = 5, source_paper: str = ""):
    """Kembalikan top_k CHUNK mentah (TANPA dedupe per paper) — IDENTIK dgn pipeline eval.
    Konsekuensi: satu paper bisa muncul >1 kali bila beberapa chunk-nya masuk top_k.
    Bila source_paper diisi, chunk dari paper sumber di-exclude (anti self-citation, prefix match)."""
    q = query_emb.reshape(1, -1).astype(np.float32)
    n_candidates = top_k * 5 if source_paper else top_k
    scores, idxs = _index.search(q, min(n_candidates, _index.ntotal))
    source_key = source_paper.strip().lower() if source_paper else ""
    out = []
    for s, i in zip(scores[0], idxs[0]):
        if not (0 <= i < len(_metadata)):
            continue
        title = _metadata[i]["paper_title"]
        if source_key and title.lower().startswith(source_key):   # exclude paper sumber
            continue
        authors, year, apa = _meta(title)
        out.append({"paper_title": title,
                    "authors": authors, "year": year, "citation": apa,
                    "chunk_text": _metadata[i]["chunk_text"], "score": float(s)})
        if len(out) >= top_k:
            break
    return out


def _extract_json(raw: str):
    """Ambil objek JSON dari keluaran LLM — tahan code-fence dan narasi pembuka
    (Llama sering menulis reasoning dulu baru JSON di akhir)."""
    raw = re.sub(r"^```(?:json)?\s*", "", (raw or "").strip())
    raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{.*\}", raw, re.S)          # blok {...} terluas di tengah narasi
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            return None
    return None

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
        "Step 4: Is the best reference truly relevant — does its content substantively "
        "support the claim (same method, finding, or subject matter)? Answer No only if "
        "the connection is merely tangential or superficial.\n"
        "Step 5: If relevant, write ONE coherent academic sentence (in the SAME language as the "
        "source paragraph) that explains what the chosen reference contributes or demonstrates "
        "in relation to the source claim, as it would appear in a literature review.\n"
        "  Rules for the sentence:\n"
        "  - Describe the method/approach/finding at a conceptual level (what & why), do NOT dump "
        "raw numbers, statistics, dataset sizes, or copy the abstract verbatim.\n"
        "  - It must be grounded in the chosen reference (no invented facts) but should READ "
        "naturally and clearly explain the connection — not just list facts.\n"
        "  - Do NOT include the paper title inside the sentence.\n\n"
        "IMPORTANT: Do NOT write your step-by-step reasoning as prose. "
        "Output ONLY the JSON object.\n"
        "Output format (JSON only):\n"
        '{ "relevant": true, "best_reference_paper": "title", '
        '"best_reference_chunk": "chunk", "citation_text": "sentence or null", "reasoning": "brief" }'
    )
    raw = _call_llm(prompt, temperature=COT_TEMP)
    r = _extract_json(raw)
    if r is None:
        return {"relevant": False, "citation_text": "", "best_reference_paper": "", "reasoning": ""}
    r["relevant"] = bool(r.get("relevant", False))
    for k in ("best_reference_paper", "best_reference_chunk", "citation_text", "reasoning"):
        v = r.get(k); r[k] = "" if v in (None, "null") else str(v)
    return r


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
    r = _extract_json(raw)
    if r is None:
        return {"relevant": False, "citation_text": "", "best_reference_paper": "", "reasoning": ""}
    r["relevant"] = bool(r.get("relevant", False))
    for k in ("best_reference_paper", "best_reference_chunk", "citation_text", "reasoning"):
        v = r.get(k); r[k] = "" if v in (None, "null") else str(v)
    return r


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


def recommend(paragraph: str, top_k: int = 5, use_hyde: bool = True, use_cot: bool = True,
              allow_external: bool = True) -> dict:
    """
    Pipeline lengkap: (HyDE) → embed → retrieve → (CoT/simple).
    Bila korpus lokal tak menemukan sitasi (relevant=False) dan allow_external=True,
    fallback otomatis ke sumber eksternal live (Semantic Scholar).
    Return: { citation_text, best_reference_paper, relevant, reasoning, candidates[], source_mode }
    """
    init()
    # HYBRID RETRIEVAL: fetch live Semantic Scholar dijalankan PARALEL dgn HyDE —
    # hasilnya MEMPERKAYA kandidat (bukan hanya fallback): konteks CoT lebih segar/kaya.
    fut, _hx = None, None
    if allow_external and S2_API_KEY:
        _hx = ThreadPoolExecutor(max_workers=1)
        fut = _hx.submit(lambda: fetch_external(
            _search_keywords(paragraph), limit=8, alt_query=paragraph[:300]))

    # HyDE proper (N=5, include-query, temp 0.7) — identik dengan setup evaluasi
    emb = hyde_embed(paragraph) if use_hyde else embed(paragraph)
    candidates = search_database(emb, top_k=top_k)          # basis data 163k (atau 100-paper)

    if fut is not None:
        try:
            papers = fut.result(timeout=20) or []
        except Exception:
            papers = []
        finally:
            _hx.shutdown(wait=False)
        seen = {c["paper_title"].strip().lower() for c in candidates}
        live = []
        for p in papers:
            if (p.get("title") or "").strip().lower() in seen:
                continue                                     # dedupe vs basis data
            v = embed(f"{p['title']} {p['abstract']}"[:2000])
            a, y, apa = _external_citation(p)
            live.append({"paper_title": p["title"], "authors": a, "year": y, "citation": apa,
                         "chunk_text": p["abstract"], "score": float(np.dot(emb, v)),
                         "doi": p.get("doi", ""), "cited_by": p.get("cited_by", 0),
                         "source": "Semantic Scholar (live)"})
        live.sort(key=lambda c: -c["score"])
        candidates = candidates + live[:3]                   # perkaya konteks: maks 3 live terbaik

    candidates = _gate_candidates(candidates)                # Lapis 1: buang kandidat lemah
    gen = (cot_generate(paragraph, candidates) if use_cot
           else simple_generate(paragraph, candidates))

    # Lapis 3: verifikasi independen atas referensi terpilih — gagal ⇒ dianggap reject
    if gen.get("relevant"):
        _ref0 = _match_ref(candidates, gen.get("best_reference_paper", ""))
        if not _verify_support(paragraph, _ref0):
            gen["relevant"] = False
            gen["reasoning"] = (gen.get("reasoning", "") +
                                " [Ditolak verifikasi: referensi hanya setopik, tidak mendukung klaim spesifik.]")

    # FALLBACK BERTINGKAT: bila korpus lokal tidak punya sitasi yang mendukung klaim
    # (CoT memutuskan relevant=False), ambil dari sumber eksternal live (Semantic Scholar).
    if allow_external and not gen.get("relevant", False):
        ext = recommend_external(paragraph, top_k=top_k, force_live=True)
        if ext.get("relevant") and ext.get("best_reference_paper"):
            ext["source_mode"] = "eksternal"
            ext["fallback_note"] = ("Tidak ditemukan di korpus lokal (100 paper) — "
                                    "sitasi diambil dari sumber eksternal.")
            return ext

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
    picked_live = bool(ref and "live" in str(ref.get("source", "")).lower())

    return {
        "citation_text":           gen.get("citation_text", ""),
        "best_reference_paper":    ref["paper_title"] if ref else best_title,
        "best_reference_authors":  ref.get("authors", "") if ref else "",
        "best_reference_year":     ref.get("year", "") if ref else "",
        "best_reference_score":    ref.get("score") if ref else None,
        "best_reference_citation": apa_key,
        "best_reference_doi":      ref.get("doi", "") if ref else "",
        "cited_paragraph":         cited_paragraph,
        "relevant":                gen.get("relevant", False),
        "reasoning":               gen.get("reasoning", ""),
        "candidates":              candidates,
        "source_mode":             "eksternal" if picked_live else "lokal",
    }


# ── Fetch eksternal (Semantic Scholar → fallback OpenAlex) ───────────────────
# Fitur tambahan pasca-evaluasi: kandidat paper dari LUAR korpus lokal.
# Pola retrieve-then-rerank: API = recall kasar (keyword), SPECTER2 = re-rank semantik.
# CATATAN: mode ini TIDAK tercakup evaluasi tesis (tidak ada ground truth eksternal).
S2_API_KEY   = os.getenv("S2_API_KEY", "")
S2_URL       = "https://api.semanticscholar.org/graph/v1/paper/search"
OPENALEX_URL = "https://api.openalex.org/works"
CONTACT_MAIL = os.getenv("OPENALEX_MAILTO", "yudhaprawira209@gmail.com")
# Bila ada S2 key, utamakan live Semantic Scholar (coverage lengkap & fresh) dibanding
# index offline 163k (harvest arbitrer, condong ke paper CS lama). Index = cadangan.
EXT_PREFER_LIVE = os.getenv("EXT_PREFER_LIVE", "1" if S2_API_KEY else "0") == "1"

# ── Index eksternal offline (SPECTER2 sebagai mesin utama, bukan re-rank keyword) ──
# Bila faiss_index_external.bin sudah dibangun (harvest→embed→build), pencarian eksternal
# jadi VEKTOR MURNI di korpus jutaan paper — arsitektur identik mode lokal, hanya korpus beda.
EXT_INDEX_FILE = ROOT / "external_index" / "faiss_index_external.bin"
EXT_META_FILE  = ROOT / "external_index" / "metadata_external.jsonl"
_ext_index = None
_ext_meta  = None


def _init_external_index():
    """Muat index eksternal sekali (lazy). Return True bila tersedia."""
    global _ext_index, _ext_meta
    if _ext_index is not None:
        return True
    if not (EXT_INDEX_FILE.exists() and EXT_META_FILE.exists()):
        return False
    _ext_index = faiss.read_index(str(EXT_INDEX_FILE))
    _ext_meta  = [json.loads(l) for l in open(EXT_META_FILE, encoding="utf-8")]
    return True


def _search_external_index(query_emb, top_k: int = 5, source_label: str = "Index Eksternal (SPECTER2)"):
    """Cari top_k paper di index eksternal (cosine SPECTER2 murni)."""
    q = query_emb.reshape(1, -1).astype(np.float32)
    scores, idxs = _ext_index.search(q, min(top_k, _ext_index.ntotal))
    out = []
    for s, i in zip(scores[0], idxs[0]):
        if not (0 <= i < len(_ext_meta)):
            continue
        p = _ext_meta[i]
        authors, year, apa = _external_citation(
            {"authors": p.get("authors", []), "year": p.get("year")})
        out.append({"paper_title": p.get("title", ""), "authors": authors, "year": year,
                    "citation": apa, "chunk_text": p.get("abstract", ""), "score": float(s),
                    "doi": p.get("doi", ""), "cited_by": p.get("cited_by", 0),
                    "source": source_label})
    return out


def search_database(query_emb, top_k: int = 5):
    """Basis data lokal sistem, urutan prioritas:
    1) PostgreSQL + pgvector (bila DATABASE_URL Postgres & tabel documents siap)
    2) FAISS index 163k offline
    3) korpus 100-paper (FAISS chunk)."""
    try:
        from backend import vectordb
        if vectordb.available():
            res = vectordb.search(query_emb, top_k=top_k, source="db_163k") \
                  or vectordb.search(query_emb, top_k=top_k)
            if res:
                for c in res:
                    c["source"] = "Basis data (Postgres/pgvector)"
                return res
    except Exception as e:
        print(f"[search_database] pgvector gagal ({e}); fallback FAISS.")
    if _init_external_index():
        return _search_external_index(query_emb, top_k, source_label="Basis data (163k)")
    return retrieve(query_emb, top_k)


def _search_keywords(paragraph: str) -> str:
    """Ringkas paragraf jadi kueri keyword pendek untuk API pencarian eksternal.
    One-shot: contoh menunjukkan agar memakai istilah teknis SPESIFIK (nama framework/
    metode/alat), bukan kata umum — kata generik menyeret hasil ke domain lain."""
    out = _call_llm(
        "Extract a concise academic search query (5-10 keywords, no quotes, no boolean "
        "operators) for finding papers on the SPECIFIC technical topic of a paragraph. "
        "Prefer named methods, frameworks, standards, tools, and domain-specific terms over "
        "generic words.\n"
        "Rules:\n"
        "- Output the query in ENGLISH (translate non-English text).\n"
        "- Preserve acronyms and technical terms EXACTLY as written — do NOT alter, expand, "
        "or 'correct' them (e.g., IOTN stays IOTN, not IoT).\n"
        "- Drop filler/request words (e.g., 'find papers about', 'carikan paper tentang').\n"
        "Output ONLY the query string.\n\n"
        "Example:\n"
        "Paragraph: Organizations increasingly rely on structured frameworks to manage "
        "their information technology, yet aligning IT processes with enterprise goals "
        "remains challenging, motivating automated recommendation of governance activities.\n"
        "Query: COBIT 2019 IT governance automated recommendation enterprise goal alignment\n\n"
        f"Paragraph: {paragraph[:1500]}\n"
        "Query:",
        temperature=0.2)
    return out.strip().strip('"') if out else " ".join(paragraph.split()[:12])


def _fetch_s2(query: str, limit: int) -> list:
    """Semantic Scholar; retry ringan. Return [] bila gagal/limit."""
    headers = {"x-api-key": S2_API_KEY} if S2_API_KEY else {}
    params = {"query": query, "limit": limit,
              "fields": "title,abstract,year,authors,citationCount,externalIds"}
    for attempt in range(3):
        try:
            r = requests.get(S2_URL, params=params, headers=headers, timeout=20)
            if r.status_code == 200:
                out = []
                for p in r.json().get("data", []) or []:
                    if not p.get("abstract"):
                        continue
                    doi = (p.get("externalIds") or {}).get("DOI", "")
                    out.append({"title": p.get("title", ""), "abstract": p["abstract"],
                                "year": str(p.get("year") or ""),
                                "authors": [a["name"] for a in (p.get("authors") or [])],
                                "cited_by": p.get("citationCount") or 0,
                                "doi": f"https://doi.org/{doi}" if doi else "",
                                "source": "Semantic Scholar"})
                return out
            if r.status_code == 429:
                time.sleep(2 * (attempt + 1)); continue
            break
        except requests.RequestException:
            time.sleep(1)
    return []


def _fetch_openalex(query: str, limit: int) -> list:
    """OpenAlex (tanpa key, polite pool). Abstrak disimpan sebagai inverted index → de-invert."""
    def deinvert(inv):
        if not inv:
            return ""
        pos = {i: w for w, idxs in inv.items() for i in idxs}
        return " ".join(pos[i] for i in sorted(pos))
    params = {"search": query, "per-page": limit, "mailto": CONTACT_MAIL,
              "select": "title,publication_year,authorships,cited_by_count,abstract_inverted_index,doi"}
    try:
        r = requests.get(OPENALEX_URL, params=params, timeout=20)
        if r.status_code != 200:
            return []
        out = []
        for w in r.json().get("results", []) or []:
            abstract = deinvert(w.get("abstract_inverted_index"))
            if not abstract:
                continue
            out.append({"title": w.get("title", ""), "abstract": abstract,
                        "year": str(w.get("publication_year") or ""),
                        "authors": [a["author"]["display_name"] for a in (w.get("authorships") or [])],
                        "cited_by": w.get("cited_by_count") or 0,
                        "doi": w.get("doi") or "",
                        "source": "OpenAlex"})
        return out
    except requests.RequestException:
        return []


def fetch_external(query: str, limit: int = 20, alt_query: str = "") -> list:
    """Fallback bertingkat: S2(keyword) → OpenAlex(keyword) → S2/OpenAlex(query mentah).
    alt_query = teks asli pengguna, dipakai bila kueri keyword tidak menghasilkan apa pun."""
    papers = _fetch_s2(query, limit)
    if not papers:
        papers = _fetch_openalex(query, limit)
    if not papers and alt_query and alt_query.strip() != query.strip():
        papers = _fetch_s2(alt_query, limit) or _fetch_openalex(alt_query, limit)
    return papers


def _external_citation(p: dict) -> tuple:
    """(authors_display, year, apa_key) dari metadata API eksternal."""
    year = p.get("year") or "n.d."
    al = p.get("authors") or []
    if not al:
        return "", year, ""
    surname = al[0].split()[-1]
    disp = f"{al[0]} et al." if len(al) > 1 else al[0]
    return disp, year, f"{surname} et al., {year}" if len(al) > 1 else f"{surname}, {year}"


def ask_external(question: str, top_k: int = 5) -> dict:
    """Pertanyaan / topik pendek ("paper tentang X?") → cari paper eksternal + jawaban singkat.
    Tanpa HyDE/CoT sitasi (input bukan draf klaim): keyword → fetch → re-rank SPECTER2 → ringkas."""
    init()
    if not EXT_PREFER_LIVE and _init_external_index():
        # (hanya bila tak ada S2 key) pencarian vektor di index offline
        candidates = _search_external_index(embed(question), top_k=top_k)
        keywords = "(pencarian vektor SPECTER2 di index eksternal)"
    else:
        # SUMBER EKSTERNAL = Semantic Scholar live (keyword → fetch → re-rank SPECTER2)
        keywords = _search_keywords(question)
        papers = fetch_external(keywords, limit=20, alt_query=question)
        if not papers:
            return {"answer": "Sumber eksternal tidak dapat dijangkau (rate limit / jaringan). Coba lagi.",
                    "candidates": [], "search_query": keywords}
        qv = embed(question)
        scored = sorted(((float(np.dot(qv, embed(f"{p['title']} {p['abstract']}"[:2000]))), p)
                         for p in papers), key=lambda x: -x[0])
        candidates = []
        for s, p in scored[:top_k]:
            authors, year, apa = _external_citation(p)
            candidates.append({"paper_title": p["title"], "authors": authors, "year": year,
                               "citation": apa, "chunk_text": p["abstract"], "score": s,
                               "doi": p["doi"], "cited_by": p["cited_by"], "source": p["source"]})
    listing = "\n".join(f"- [{c['year']}] {c['paper_title']} ({c['citation']}): {c['chunk_text'][:400]}"
                        for c in candidates)
    ans = _call_llm(
        "You are a research assistant. The papers below were retrieved and RANKED BY SEMANTIC "
        "RELEVANCE to the user's question via an external academic search. Briefly present the "
        "papers that relate to the question — for each, one sentence on what it covers. "
        "Answer in the SAME language as the question (Indonesian → Indonesian). "
        "Only dismiss a paper if it is clearly about an unrelated topic.\n\n"
        f"Papers:\n{listing}\n\nQuestion: {question}\n\nAnswer:", temperature=0.4)
    return {"answer": ans or "Tidak ada jawaban.", "candidates": candidates,
            "search_query": keywords}


def recommend_external(paragraph: str, top_k: int = 5, force_live: bool = False) -> dict:
    """
    Mode eksternal (retrieve-then-rerank):
    keyword search API (recall kasar) → embed abstrak kandidat dgn SPECTER2 →
    re-rank cosine thd embedding proper-HyDE paragraf → CoT pilih & tulis sitasi.
    Komponen inti (HyDE, SPECTER2, CoT) identik dgn mode lokal; hanya sumber kandidat beda.
    """
    init()
    # HyDE proper (N=5, include-query) — SAMA dgn mode lokal
    q = hyde_embed(paragraph)

    if not force_live and not EXT_PREFER_LIVE and _init_external_index():
        # (hanya bila tak ada S2 key) pencarian vektor di index offline
        candidates = _search_external_index(q, top_k=top_k)
        keywords = "(pencarian vektor SPECTER2 di index eksternal)"
    else:
        # FALLBACK: keyword API + re-rank SPECTER2 (kueri diperkaya abstrak HyDE)
        hyps = [h for h in (hyde_generate(paragraph) for _ in range(HYDE_N)) if h]
        kw_source = paragraph + ("\n\nRelated abstract: " + hyps[0] if hyps else "")
        keywords = _search_keywords(kw_source)
        papers = fetch_external(keywords, limit=20, alt_query=paragraph[:300])
        if not papers:
            return {"citation_text": "", "best_reference_paper": "", "best_reference_authors": "",
                    "best_reference_year": "", "best_reference_score": None,
                    "best_reference_citation": "", "cited_paragraph": "", "relevant": False,
                    "reasoning": "Sumber eksternal tidak dapat dijangkau (rate limit / jaringan).",
                    "candidates": [], "search_query": keywords}
        scored = sorted(((float(np.dot(q, embed(f"{p['title']} {p['abstract']}"[:2000]))), p)
                         for p in papers), key=lambda x: -x[0])
        candidates = []
        for s, p in scored[:top_k]:
            authors, year, apa = _external_citation(p)
            candidates.append({"paper_title": p["title"], "authors": authors, "year": year,
                               "citation": apa, "chunk_text": p["abstract"], "score": s,
                               "doi": p["doi"], "cited_by": p["cited_by"], "source": p["source"]})

    gen = cot_generate(paragraph, candidates)
    best_title = gen.get("best_reference_paper", "")
    ref = next((c for c in candidates if c["paper_title"] == best_title), None)
    if ref is None and best_title:
        ref = next((c for c in candidates
                    if best_title.lower() in c["paper_title"].lower()
                    or c["paper_title"].lower() in best_title.lower()), None)
    if ref is None and candidates:
        ref = candidates[0]

    apa_key = ref.get("citation", "") if ref else ""
    cited_paragraph = cite_rewrite(paragraph, apa_key) if (gen.get("relevant") and apa_key) else ""

    return {
        "citation_text":           gen.get("citation_text", ""),
        "best_reference_paper":    ref["paper_title"] if ref else best_title,
        "best_reference_authors":  ref.get("authors", "") if ref else "",
        "best_reference_year":     ref.get("year", "") if ref else "",
        "best_reference_score":    ref.get("score") if ref else None,
        "best_reference_citation": apa_key,
        "best_reference_doi":      ref.get("doi", "") if ref else "",
        "cited_paragraph":         cited_paragraph,
        "relevant":                gen.get("relevant", False),
        "reasoning":               gen.get("reasoning", ""),
        "candidates":              candidates,
        "search_query":            keywords,
    }


# ── Auto-sitasi abstrak: sisipkan (Penulis, Tahun) per kalimat + daftar referensi ──
# Paste abstrak/paragraf → tiap kalimat dicarikan referensi (lokal → fallback eksternal live)
# → penanda sitasi disisipkan inline. Retrieval per-kalimat pakai embedding langsung
# (tanpa HyDE) — dijustifikasi temuan bahwa HyDE ≈ baseline pada korpus ini.
def _split_sentences(text: str) -> list:
    parts = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text).strip())
    return [p.strip() for p in parts if len(p.strip()) >= 25]


def _insert_cite(sentence: str, cite: str) -> str:
    m = re.search(r"[.!?]+\s*$", sentence)
    return (sentence[:m.start()] + f" ({cite})" + sentence[m.start():]) if m else f"{sentence} ({cite})"


def _match_ref(cands: list, best_title: str):
    if not cands:
        return None
    r = next((c for c in cands if c["paper_title"] == best_title), None)
    if r is None and best_title:
        r = next((c for c in cands if best_title.lower() in c["paper_title"].lower()
                  or c["paper_title"].lower() in best_title.lower()), None)
    return r or cands[0]


def _find_external_ref(sentence: str, top_k: int = 5):
    """Fetch ringan (tanpa HyDE) utk 1 kalimat: keyword → fetch → rerank → CoT relevansi."""
    papers = fetch_external(_search_keywords(sentence), limit=15, alt_query=sentence)
    if not papers:
        return None
    qv = embed(sentence)
    scored = sorted(((float(np.dot(qv, embed(f"{p['title']} {p['abstract']}"[:2000]))), p)
                     for p in papers), key=lambda x: -x[0])
    cand = []
    for s, p in scored[:top_k]:
        a, y, apa = _external_citation(p)
        cand.append({"paper_title": p["title"], "authors": a, "year": y, "citation": apa,
                     "chunk_text": p["abstract"], "score": s, "doi": p.get("doi", "")})
    cand = _gate_candidates(cand)                            # Lapis 1
    if not cand:
        return None
    gen = cot_generate(sentence, cand)
    if not gen.get("relevant"):
        return None
    ref = _match_ref(cand, gen.get("best_reference_paper", ""))
    return ref if _verify_support(sentence, ref) else None   # Lapis 3


def _rewrite_with_reference(sentence: str, ref: dict) -> str:
    """Tulis ulang kalimat agar memuat kontribusi referensi (grounded pada abstraknya),
    diakhiri penanda sitasi. TIDAK mengarang fakta di luar abstrak referensi."""
    cite = ref.get("citation", "")
    prompt = (
        "Rewrite the sentence below in an academic literature-review style so it naturally "
        "integrates and attributes what the cited reference contributes. Use ONLY information "
        "supported by the reference abstract — do NOT invent findings, numbers, or claims not "
        "present in it. Preserve the author's original point, add a brief phrase reflecting what "
        "the reference shows, and END the sentence with the marker "
        f"\"({cite})\" right before the final period. Write in the SAME language as the sentence. "
        "Output ONLY the rewritten sentence.\n\n"
        f"Sentence: {sentence}\n"
        f"Reference: {ref.get('paper_title','')}\n"
        f"Reference abstract: {(ref.get('chunk_text') or '')[:900]}\n"
    )
    out = _call_llm(prompt, temperature=0.3)
    out = (out or "").strip().strip('"')
    if not out:
        return _insert_cite(sentence, cite)
    if cite and f"({cite})" not in out:          # pastikan penanda ada
        out = _insert_cite(out, cite)
    return out


def _cite_one_sentence(sent: str, top_k: int, allow_external: bool, prefer_external: bool):
    """Proses 1 kalimat (dipanggil paralel): cari referensi → rewrite dgn sitasi.
    Return (kalimat_hasil, ref|None, source)."""
    ref, source = None, "lokal"
    if prefer_external:                                       # 🌐 ON → eksternal langsung
        ref = _find_external_ref(sent, top_k)
        if ref:
            source = "eksternal"
    else:
        cand = _gate_candidates(search_database(embed(sent), top_k=top_k))  # Lapis 1
        gen = cot_generate(sent, cand) if cand else {"relevant": False}
        if gen.get("relevant"):
            ref = _match_ref(cand, gen.get("best_reference_paper", ""))
            if not _verify_support(sent, ref):                # Lapis 3
                ref = None
        if ref is None and allow_external:                    # fallback eksternal live
            ref = _find_external_ref(sent, top_k)
            if ref:
                source = "eksternal"
    if ref and ref.get("citation"):
        return _rewrite_with_reference(sent, ref), ref, source
    return sent, None, source


def cite_abstract(paragraph: str, top_k: int = 5, allow_external: bool = True,
                  prefer_external: bool = False) -> dict:
    """Tiap kalimat abstrak: cari referensi → tulis ulang memuat kontribusi paper + sitasi.
    Kalimat diproses PARALEL (independen) → latensi ~1 kalimat, bukan jumlah kalimat.
    prefer_external=True (toggle 🌐): ambil langsung dari eksternal live, lewati korpus lokal."""
    init()
    sents = _split_sentences(paragraph)
    with ThreadPoolExecutor(max_workers=min(len(sents), 4) or 1) as ex:
        results = list(ex.map(
            lambda s: _cite_one_sentence(s, top_k, allow_external, prefer_external), sents))
    out_sents, refs, seen = [], [], {}
    for text, ref, source in results:                         # urutan kalimat terjaga
        out_sents.append(text)
        if ref and ref.get("citation") and ref["citation"] not in seen:
            seen[ref["citation"]] = len(refs) + 1
            refs.append({"n": len(refs) + 1, "citation": ref["citation"],
                         "paper_title": ref["paper_title"], "authors": ref.get("authors", ""),
                         "year": ref.get("year", ""), "doi": ref.get("doi", ""),
                         "source": source})
    return {"cited_abstract": " ".join(out_sents), "references": refs,
            "n_sentences": len(out_sents), "n_cited": len(refs)}

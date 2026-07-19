"""
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
VERIFY_STRICT   = os.getenv("VERIFY_STRICT", "1") == "1"   # 1=ketat, 0=sedang (lenient)

# ── Penjaga sitasi ABSTRAK (per kalimat) — hasil pengukuran: skor semua tinggi, ────
# jadi threshold TAK cukup. Perlu: cap per-paper + skip kalimat non-klaim + verify ketat.
CITE_MAX_PER_PAPER  = int(os.getenv("CITE_MAX_PER_PAPER", "2"))     # 1 paper max N sitasi/dokumen
CITE_STRICT_VERIFY  = os.getenv("CITE_STRICT_VERIFY", "1") == "1"   # verify ketat khusus abstrak
CITE_SKIP_NONCLAIM  = os.getenv("CITE_SKIP_NONCLAIM", "1") == "1"   # skip kalimat tanpa klaim
# Penyisipan sitasi: default DETERMINISTIK (sisip penanda apa adanya → bersih, tanpa klausa
# jembatan retoris, hemat 1 panggilan LLM/kalimat). CITE_POLISH=1 → poles kalimat via LLM.
CITE_POLISH         = os.getenv("CITE_POLISH", "0") == "1"

# Penjaga SUMBER EKSTERNAL (anti "pintu belakang maksa"): S2 punya jutaan paper → utk klaim
# apapun (bahkan ngawur) hampir selalu ada yang nyerempet kata. Maka eksternal butuh floor
# absolut LEBIH TINGGI + verify KETAT (bukan lenient) sebelum boleh jadi sitasi.
EXT_MIN_SIM       = float(os.getenv("EXT_MIN_SIM", "0.72"))       # floor cosine absolut eksternal
EXT_VERIFY_STRICT = os.getenv("EXT_VERIFY_STRICT", "1") == "1"    # verify ketat utk sitasi eksternal
# Rekomendasi 1-sitasi (klaim tunggal, sering ngawur/berdiri sendiri): verify SELALU ketat +
# anti-substitusi. Klaim tunggal tak punya konteks kalimat lain utk kalibrasi → butuh gerbang
# independen yang tak bergantung prompt CoT.
REC_VERIFY_STRICT = os.getenv("REC_VERIFY_STRICT", "1") == "1"

# Preferensi KEBARUAN (tier): paper dikelompokkan per "band" relevansi (lebar RECENCY_BAND).
# Di dalam band yang sama → paper TERBARU diutamakan. Beda band → yang lebih relevan tetap
# menang. Jadi relevansi tetap dominan, kebaruan hanya menentukan urutan antar-paper setara.
RECENCY_BAND = float(os.getenv("RECENCY_BAND", "0.05"))   # lebar band cosine (0 = matikan preferensi)


def _year_int(c: dict) -> int:
    try:
        return int(str(c.get("year") or "")[:4])
    except Exception:
        return 0


def _rank_key(c: dict):
    """Kunci urut (dipakai dgn reverse=True): (tier_relevansi, tahun, cosine).
    Paper dgn relevansi SETARA (band cosine sama) → yang lebih BARU di atas."""
    score = c.get("score", 0.0)
    tier = round(score / RECENCY_BAND) if RECENCY_BAND > 0 else score
    return (tier, _year_int(c), score)


# Porsi hasil dari sumber EKSTERNAL (S2 live) — S2 punya jauh lebih banyak kebaruan/cakupan.
# Target, bukan paksaan: bila eksternal kurang, sisa ditutup korpus lokal (graceful).
EXT_QUOTA = float(os.getenv("EXT_QUOTA", "0.70"))

# Filter relevansi PER-PAPER di mode cari: buang paper yang cuma setopik luas / nyerempet,
# tidak SPESIFIK menjawab maksud query. 1 panggilan batch (menilai semua kandidat sekaligus).
RELEVANCE_FILTER = os.getenv("RELEVANCE_FILTER", "1") == "1"


def _filter_relevant(question: str, candidates: list) -> list:
    """Sisakan hanya paper yang SPESIFIK menjawab query (bukan sekadar setopik luas).
    Satu panggilan batch; fail-open bila parsing gagal (tak membuang apa pun)."""
    if not candidates or not RELEVANCE_FILTER:
        return candidates
    listing = "\n".join(
        f"{i + 1}. {c.get('paper_title','')} — {(c.get('chunk_text') or '')[:220]}"
        for i, c in enumerate(candidates))
    out = _call_llm(
        "You screen search results. For EACH numbered paper, decide whether it SPECIFICALLY "
        "addresses the user's query intent — not merely sharing a broad field, an isolated "
        "keyword, or an adjacent subtopic. Be strict: if the paper is only loosely/tangentially "
        "related, answer NO.\n"
        "Output a numbered list, one line per paper: '<n>: YES' or '<n>: NO'. Nothing else.\n\n"
        f"Query: {question}\n\nPapers:\n{listing}",
        temperature=0, prefer="openrouter")
    verdict = {}
    for line in (out or "").splitlines():
        m = re.match(r"\s*(\d+)\s*[:.)-]\s*(YES|NO)\b", line, re.I)
        if m:
            verdict[int(m.group(1))] = m.group(2).upper() == "YES"
    if not verdict:                                  # parse gagal total → fail-open
        return candidates
    return [c for i, c in enumerate(candidates, 1) if verdict.get(i, True)]


def _is_external(c: dict) -> bool:
    s = str(c.get("source", "")).lower()
    return "live" in s or "semantic" in s or "openalex" in s


def _apply_ext_quota(cands: list, top_k: int) -> list:
    """Pilih top_k dgn target ~EXT_QUOTA porsi eksternal. Tiap grup diurut _rank_key
    (relevansi-tier + kebaruan). Kekurangan satu sumber ditutup sumber lain."""
    if not cands:
        return []
    ext = sorted((c for c in cands if _is_external(c)), key=_rank_key, reverse=True)
    loc = sorted((c for c in cands if not _is_external(c)), key=_rank_key, reverse=True)
    n_ext = min(len(ext), round(top_k * EXT_QUOTA))
    n_loc = min(len(loc), top_k - n_ext)
    n_ext = min(len(ext), top_k - n_loc)                 # isi sisa dari eksternal bila lokal kurang
    picked = ext[:n_ext] + loc[:n_loc]
    picked.sort(key=_rank_key, reverse=True)             # urutan tampil
    return picked[:top_k]

# Gerbang relevansi untuk mode CARI/TANYA (eksplorasi, lebih longgar dari sitasi).
# Tanpa ini, pencarian yang nyasar (mis. akronim ambigu) tetap "memaksa" 10 hasil.
ASK_MIN_SIM = float(os.getenv("ASK_MIN_SIM", "0.50"))   # floor absolut; di bawah ini = sampah
ASK_REL_WIN = float(os.getenv("ASK_REL_WIN", "0.18"))   # buang yang jauh di bawah hasil terbaik


def _gate_ask(scored: list) -> list:
    """Saring hasil cari/tanya (list of (score, item)). Simpan yang >= ASK_MIN_SIM DAN
    dalam ASK_REL_WIN dari skor tertinggi. Kembalikan [] bila tak ada yang lolos
    (→ jujur 'tidak ditemukan', bukan memaksa hasil nyasar)."""
    if not scored:
        return []
    top = scored[0][0]
    return [(s, p) for s, p in scored
            if s >= ASK_MIN_SIM and s >= top - ASK_REL_WIN]


def _gate_candidates(cands: list) -> list:
    """Saring kandidat: skor >= MIN_SIM dan tidak jauh di bawah kandidat terbaik."""
    if not cands:
        return []
    top = max(c.get("score", 0.0) for c in cands)
    return [c for c in cands
            if c.get("score", 0.0) >= MIN_SIM and c.get("score", 0.0) >= top - REL_WIN]


def _verify_support(claim: str, ref: dict, strict: bool = None) -> bool:
    """Lapis 3: pemeriksaan independen — apakah referensi BENAR-BENAR mendukung klaim
    spesifik (bukan sekadar setopik). Gagal verifikasi → sitasi ditolak.
    strict=None → pakai VERIFY_STRICT global; True/False → paksa mode (cite_abstract pakai True)."""
    if not VERIFY_CITATION or not ref:
        return True
    use_strict = VERIFY_STRICT if strict is None else strict
    if use_strict:
        rule = ("Decide whether the reference can LEGITIMATELY be cited for the SPECIFIC statement. "
                "Answer NO if EITHER: (a) the statement is absurd, nonsensical, or a spurious "
                "causal claim that no credible paper would support (e.g. 'models are more accurate "
                "on Tuesdays'), OR (b) the reference actually concerns a DIFFERENT assertion and "
                "overlaps only in broad topic or isolated keywords. "
                "Answer YES if the reference substantively supports the statement's ACTUAL "
                "assertion — it may be a general statement, and identical wording is not required. "
                "Do NOT accept mere topical overlap, and do NOT reinterpret the statement to fit "
                "the reference.")
    else:   # mode sedang: terima bila relevan-substantif, tolak hanya bila jelas tak nyambung
        rule = ("Decide whether the reference could reasonably serve as a citation for the "
                "statement — i.e. it is on the same subject and does not contradict it. "
                "Accept general/introductory statements if the reference covers that subject. "
                "Answer NO only if the reference is clearly about an unrelated topic.")
    out = _call_llm(
        f"You are a citation auditor. {rule}\n\n"
        f"Statement:\n{claim[:800]}\n\n"
        f"Reference title: {ref.get('paper_title','')}\n"
        f"Reference abstract: {(ref.get('chunk_text') or '')[:900]}\n\n"
        "Answer with exactly one word: YES or NO.",
        temperature=0, prefer="openrouter")
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


def _call_llm(prompt: str, temperature: float = 0.3, prefer: str = None) -> str:
    """Coba tiap provider dalam rantai (2 percobaan per provider).
    prefer = nama provider yang diutamakan untuk tugas ini (mis. 'groq' utk HyDE,
    'openrouter' utk CoT); sisanya tetap jadi fallback. Return "" bila semua gagal."""
    chain = _llm_chain or [("openrouter", _client, GEN_MODEL)]
    if prefer:
        chain = sorted(chain, key=lambda x: 0 if x[0] == prefer else 1)   # utamakan 'prefer'
    for name, client, model in chain:
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


EMBED_BATCH = int(os.getenv("EMBED_BATCH", "32"))   # ukuran sub-batch GPU


def embed_many(texts: list) -> np.ndarray:
    """Embed banyak teks dalam SATU forward pass (batched) → kunci lebih jarang dipegang,
    GPU lebih efisien. Return array (N, 768) L2-normalized."""
    if not texts:
        return np.zeros((0, 768), dtype=np.float32)
    out = []
    with _embed_lock:                 # satu kali kunci untuk seluruh batch
        for i in range(0, len(texts), EMBED_BATCH):
            chunk = texts[i:i + EMBED_BATCH]
            x = _tokenizer(chunk, return_tensors="pt", truncation=True, max_length=512, padding=True)
            x = {k: v.to(_device) for k, v in x.items()}
            with torch.no_grad():
                o = _model(**x)
            e = torch.nn.functional.normalize(o.last_hidden_state[:, 0, :], dim=1)
            out.append(e.cpu().numpy().astype(np.float32))
    return np.vstack(out)


def embed(text: str):
    return embed_many([text])[0]      # jalur tunggal lewat batch (1 baris)


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
    return _call_llm(prompt, temperature=HYDE_TEMP, prefer="groq")  # HyDE cepat/gratis


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
    texts = list(hyps)
    if HYDE_INCLUDE_QUERY or not texts:       # sertakan paragraf asli (hybrid) / fallback
        texts.append(paragraph)
    vecs = embed_many(texts)                  # SATU forward pass batched utk semua abstrak
    qv = np.mean(vecs, axis=0)
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
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, list):              # Llama kadang membungkus dlm list
            return next((x for x in parsed if isinstance(x, dict)), None)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{.*\}", raw, re.S)          # blok {...} terluas di tengah narasi
    if m:
        try:
            parsed = json.loads(m.group())
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
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
        "Step 4: Does the reference DIRECTLY support the SPECIFIC assertion the paragraph actually "
        "makes — the same finding/method/fact AS WRITTEN? Sharing only the broad subject is NOT "
        "enough. CRITICAL ANTI-SUBSTITUTION RULE: do NOT reinterpret, generalize, or change what "
        "the claim asserts in order to fit a reference. If the only way to connect them is to cite "
        "a DIFFERENT claim than what the paragraph literally states (e.g. the paragraph says 'X on "
        "Tuesdays' but the paper is about 'batch size'), answer No. If the paragraph's specific "
        "assertion is not actually supported by any reference, answer No. When in doubt, answer No.\n"
        "Step 5: If relevant, write ONE coherent academic sentence (in the SAME language as the "
        "source paragraph) that PRESERVES the paragraph's original claim and attributes it to the "
        "reference, as in a literature review.\n"
        "  Rules for the sentence:\n"
        "  - Keep the original claim's meaning — do NOT replace it with a different claim from the "
        "reference. If you cannot keep the original meaning while grounding it in the reference, "
        "this means the reference does not support it → go back to Step 4 and answer No.\n"
        "  - Describe at a conceptual level (what & why), do NOT dump raw numbers, statistics, or "
        "copy the abstract verbatim.\n"
        "  - It must be grounded in the chosen reference (no invented facts).\n"
        "  - Do NOT include the paper title inside the sentence.\n\n"
        "IMPORTANT: Do NOT write your step-by-step reasoning as prose. "
        "Output ONLY the JSON object.\n"
        "Output format (JSON only):\n"
        '{ "relevant": true, "best_reference_paper": "title", '
        '"best_reference_chunk": "chunk", "citation_text": "sentence or null", "reasoning": "brief" }'
    )
    raw = _call_llm(prompt, temperature=COT_TEMP, prefer="openrouter")  # CoT akurat
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
    raw = _call_llm(prompt, temperature=0.2, prefer="openrouter")
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
        "- If it is a general question, you may answer from your own knowledge — but only when you "
        "are confident it is correct.\n"
        "ANTI-FABRICATION (critical):\n"
        "- NEVER invent or guess the expansion/definition of an acronym or technical term. If you are "
        "not certain what an acronym stands for, say it is ambiguous and ask the user for the full term "
        "(e.g. 'Singkatan ini ambigu — maksudnya apa? Coba tulis kepanjangannya'). Do NOT fabricate a "
        "plausible-sounding expansion.\n"
        "- Do not state specific facts, figures, or definitions you are unsure of.\n"
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
        fresh = [p for p in papers if (p.get("title") or "").strip().lower() not in seen]
        fvecs = embed_many([f"{p['title']} {p['abstract']}"[:2000] for p in fresh])  # batch
        live = []
        for p, v in zip(fresh, fvecs):
            a, y, apa = _external_citation(p)
            live.append({"paper_title": p["title"], "authors": a, "year": y, "citation": apa,
                         "chunk_text": p["abstract"], "score": float(np.dot(emb, v)),
                         "doi": p.get("doi", ""), "cited_by": p.get("cited_by", 0),
                         "tldr": p.get("tldr", ""), "source": "Semantic Scholar (live)"})
        live.sort(key=lambda c: -c["score"])
        # Live BERSAING dgn basis data dalam kuota yang sama: gabung, urutkan skor,
        # ambil top_k TOTAL (maks 10) — bukan 10+3.
        candidates = sorted(candidates + live[:5], key=lambda c: -c.get("score", 0))[:top_k]

    candidates = _apply_ext_quota(_gate_candidates(candidates), top_k)   # Lapis 1 + ~70% eksternal + kebaruan
    gen = (cot_generate(paragraph, candidates) if use_cot
           else simple_generate(paragraph, candidates))

    # Lapis 3: verifikasi independen atas referensi terpilih — gagal ⇒ dianggap reject.
    # Verify KETAT untuk SEMUA pick (klaim tunggal ngawur = pintu belakang; strict wajib, tak boleh
    # bergantung prompt CoT). Pick eksternal juga butuh floor absolut tinggi.
    if gen.get("relevant"):
        _ref0 = _match_ref(candidates, gen.get("best_reference_paper", ""))
        _is_ext = bool(_ref0 and "live" in str(_ref0.get("source", "")).lower())
        _strict = True if REC_VERIFY_STRICT else (EXT_VERIFY_STRICT if _is_ext else None)
        _ok = _ref0 is not None and not (_is_ext and _ref0.get("score", 0.0) < EXT_MIN_SIM)
        if _ok and not _verify_support(paragraph, _ref0, strict=_strict):
            _ok = False
        if not _ok:
            gen["relevant"] = False
            gen["reasoning"] = (gen.get("reasoning", "") +
                                " [Ditolak verifikasi: referensi tidak mendukung klaim SPESIFIK yang ditulis.]")

    # FALLBACK BERTINGKAT: bila korpus lokal tidak punya sitasi yang mendukung klaim
    # (CoT memutuskan relevant=False), ambil dari sumber eksternal live (Semantic Scholar).
    if allow_external and not gen.get("relevant", False):
        ext = recommend_external(paragraph, top_k=top_k, force_live=True)
        if ext.get("relevant") and ext.get("best_reference_paper"):
            try:
                cands = sorted(ext.get("candidates") or [], key=_rank_key, reverse=True)
                bt = ext.get("best_reference_paper", "")
                rx = next((c for c in cands if c.get("paper_title") == bt),
                          cands[0] if cands else None)
                relx = [c for c in cands if c is not rx][:3]
                _attach_summaries(paragraph[:600], ([rx] if rx else []) + relx)
                ext["best_reference_summary"] = (rx or {}).get("summary", "")
                ext["related"] = [{k: c.get(k, "") for k in
                                   ("paper_title", "authors", "year", "citation", "doi", "summary")}
                                  for c in relx]
            except Exception:
                pass
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

    # Gaya AI-assistant (ala Elicit): ringkasan utk referensi terpilih + 3 terkait
    related = [c for c in candidates if c is not ref][:3]
    try:
        _attach_summaries(paragraph[:600], ([ref] if ref else []) + related)
    except Exception:
        pass

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
        "best_reference_summary":  ref.get("summary", "") if ref else "",
        "related": [{k: c.get(k, "") for k in
                     ("paper_title", "authors", "year", "citation", "doi", "summary")}
                    for c in related],
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
    # Query PENDEK (mis. akronim/istilah tunggal): jangan diekstraksi-ulang — cukup
    # terjemahkan + buang filler. Cegah LLM "mengarang" konteks domain yang menyeret hasil
    # nyasar (mis. "HyDE" → "HyDE ontology development framework").
    if len(paragraph.split()) <= 6:
        out = _call_llm(
            "Turn the short text below into a plain English search query.\n"
            "- Translate to English if it is not English.\n"
            "- Remove request/filler words (e.g. 'apa itu', 'carikan paper tentang', 'find papers about').\n"
            "- Do NOT add, expand, or invent ANY new terms, domains, related concepts, or acronym "
            "expansions. Keep acronyms EXACTLY as written.\n"
            "Output ONLY the resulting query words, nothing else.\n\n"
            f"Text: {paragraph}",
            temperature=0, prefer="openrouter")   # gpt-4o-mini: patuh 'jangan ekspansi' (llama tidak)
        return (out or paragraph).strip().strip('"') or paragraph.strip()
    out = _call_llm(
        "Extract a concise academic search query (up to 10 keywords, no quotes, no boolean "
        "operators) for finding papers on the SPECIFIC technical topic of a paragraph. "
        "Prefer named methods, frameworks, standards, tools, and domain-specific terms that are "
        "ACTUALLY PRESENT in the input over generic words.\n"
        "Rules:\n"
        "- Output the query in ENGLISH (translate non-English text).\n"
        "- Preserve acronyms and technical terms EXACTLY as written — do NOT alter, expand, "
        "or 'correct' them (e.g., IOTN stays IOTN, not IoT).\n"
        "- Do NOT invent or add topics, domains, or descriptive terms that are not in the input. "
        "Use ONLY concepts the input actually mentions.\n"
        "- If the input is very short (a single term or acronym with no surrounding context), "
        "output ONLY that term — do NOT pad it with a guessed domain (e.g. input 'HyDE' → query 'HyDE', "
        "NOT 'HyDE ontology development framework').\n"
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
    # 'tldr' = ringkasan 1-kalimat AI bawaan S2 (SciTLDR) → pakai langsung, hemat panggilan LLM.
    params = {"query": query, "limit": limit,
              "fields": "title,abstract,year,authors,citationCount,externalIds,tldr"}
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
                                "tldr": (p.get("tldr") or {}).get("text", "") or "",
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


_ACRONYM_FILLER = {"apa", "itu", "apakah", "yang", "tentang", "paper", "papers", "cari",
                   "carikan", "cariin", "temukan", "find", "search", "about", "what", "is",
                   "are", "the", "a", "an", "dan", "atau", "makalah", "jurnal", "of", "for", "on"}


def _acronym_hint(query: str):
    """Deteksi ringan (tanpa LLM): bila query PENDEK dan mengandung token mirip singkatan
    (mis. 'HyDE', 'RAG', 'MBG', 'IOTN') → kembalikan token itu untuk peringatan UI.
    Singkatan ambigu sering menyesatkan embedding → sarankan user tulis kepanjangannya."""
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z0-9\-]*", query or "")
             if w.lower() not in _ACRONYM_FILLER]
    if not words or len(words) > 2:            # cuma untuk query pendek
        return None
    for w in words:
        caps = sum(1 for ch in w if ch.isupper())
        if 2 <= len(w) <= 8 and (caps >= 2 or (w.isupper() and len(w) >= 2)):
            return w
    return None


def ask_external(question: str, top_k: int = 5) -> dict:
    """Pertanyaan / topik pendek ("paper tentang X?") → cari paper + jawaban singkat.
    HYBRID: korpus lokal 163k (vektor SPECTER2) + live Semantic Scholar/OpenAlex,
    digabung → dedup → rerank cosine → gate relevansi → ringkas (ala Elicit).
    Query di-embed dengan HyDE (query-expansion) — recall paper 'nama teknik' setara mode
    sitasi & mengurangi bias korpus (abstrak hipotetis lebih topikal)."""
    init()
    ac = _acronym_hint(question)
    note = (f"“{ac}” terdeteksi sebagai singkatan/istilah teknis. Jika hasil kurang tepat, "
            "coba tulis kepanjangannya atau tambah konteks (mis. bidang/metodenya).") if ac else None
    qv = hyde_embed(question)                    # opsi B: HyDE juga di mode cari
    pool = []

    # (1) Korpus lokal 163k — vektor SPECTER2 murni (cepat, offline)
    if _init_external_index():
        pool += _search_external_index(qv, top_k=max(top_k * 2, 12),
                                       source_label="Basis data (163k)")

    # (2) Live Semantic Scholar / OpenAlex — keyword → fetch → embed → skor cosine
    keywords = _search_keywords(question)
    papers = fetch_external(keywords, limit=20, alt_query=question)
    if papers:
        pvecs = embed_many([f"{p['title']} {p['abstract']}"[:2000] for p in papers])  # batch
        for p, v in zip(papers, pvecs):
            authors, year, apa = _external_citation(p)
            pool.append({"paper_title": p["title"], "authors": authors, "year": year,
                         "citation": apa, "chunk_text": p["abstract"],
                         "score": float(np.dot(qv, v)), "doi": p["doi"],
                         "cited_by": p["cited_by"], "tldr": p.get("tldr", ""),
                         "source": p["source"]})

    if not pool:
        return {"answer": "Sumber tidak dapat dijangkau (korpus lokal & live keduanya kosong). Coba lagi.",
                "candidates": [], "search_query": keywords, "query_note": note}

    # Dedup by judul (simpan skor tertinggi), rerank, lalu gate relevansi
    best = {}
    for c in pool:
        k = (c.get("paper_title") or "").strip().lower()
        if k and (k not in best or c["score"] > best[k]["score"]):
            best[k] = c
    scored = _gate_ask(sorted(((c["score"], c) for c in best.values()), key=lambda x: -x[0]))
    if not scored:
        return {"answer": "Tidak ditemukan paper yang cukup relevan dengan pencarian ini. "
                          "Coba istilah yang lebih lengkap/spesifik (mis. kepanjangan dari singkatan).",
                "candidates": [], "search_query": keywords, "query_note": note}
    candidates = _apply_ext_quota([c for _, c in scored], top_k)  # ~70% eksternal + urut relevansi/kebaruan
    candidates = _filter_relevant(question, candidates)          # buang yang tak SPESIFIK menjawab query
    if not candidates:
        return {"answer": f"Tidak ditemukan paper yang secara spesifik membahas \"{question[:80]}\". "
                          "Paper yang ada hanya menyinggung topik ini secara umum. Coba kata kunci yang "
                          "lebih tepat, atau topiknya mungkin belum tercakup di korpus.",
                "candidates": [], "search_query": keywords, "query_note": note}

    _attach_summaries(question, candidates)                  # kolom "Summary" ala Elicit
    listing = "\n".join(f"- [{c['year']}] {c['paper_title']} ({c['citation']}): {c['chunk_text'][:400]}"
                        for c in candidates)
    ans = _call_llm(
        "You are a research assistant. The papers below were retrieved for the user's query.\n"
        "FIRST, on its own first line, output a verdict: 'RELEVANT: YES' if these papers genuinely "
        "address the query's topic, or 'RELEVANT: NO' if the query is nonsensical/incoherent OR the "
        "papers merely share isolated keywords WITHOUT actually addressing it.\n"
        "THEN write a short synthesis (2-4 sentences) of what the papers collectively say, referring "
        "to the most relevant ones by author.\n"
        "STRICT GROUNDING RULES:\n"
        "- Base the synthesis ONLY on the papers listed below. Do NOT add facts from your own knowledge.\n"
        "- NEVER invent or guess the meaning/expansion of an acronym or term.\n"
        "- If RELEVANT is NO, the synthesis must plainly say the papers do not address the query "
        "(e.g. 'Tidak ditemukan paper yang benar-benar membahas topik ini').\n"
        "- Answer in the SAME language as the query (Indonesian → Indonesian).\n\n"
        f"Papers:\n{listing}\n\nQuery: {question}\n\nOutput:", temperature=0.2)
    ans = ans or ""
    relevant = True                                          # parse verdict baris pertama
    m = re.match(r"\s*RELEVANT\s*:?\s*(YES|NO)\b", ans, re.I)
    if m:
        relevant = m.group(1).upper() == "YES"
        ans = ans[m.end():].lstrip("\n :.-")                 # buang baris verdict dari jawaban
    if not relevant:
        candidates = []                                      # jauh dari konteks → JANGAN tampilkan referensi ngawur
    return {"answer": ans.strip() or "Tidak ada jawaban.", "candidates": candidates,
            "search_query": keywords, "query_note": note}


def _summarize_source(question: str, c: dict) -> str:
    """Ringkasan 1-2 kalimat: apa isi paper INI yang relevan dengan pertanyaan (gaya Elicit)."""
    out = _call_llm(
        "Ringkas dalam 1-2 kalimat: apa kontribusi/temuan paper INI, dikaitkan dengan "
        "pertanyaan pengguna. HANYA berdasarkan abstrak di bawah — jangan menambah fakta dari "
        "pengetahuanmu sendiri, dan jangan mengarang kepanjangan akronim. Bila abstrak ini "
        "sebenarnya tidak membahas topik pertanyaan, katakan apa adanya (mis. 'Paper ini membahas "
        "X, tidak spesifik ke topik yang ditanya').\n"
        "WAJIB tulis ringkasan dalam BAHASA INDONESIA (istilah teknis seperti nama metode/"
        "model boleh tetap bahasa Inggris). Output HANYA kalimat ringkasannya, tanpa pembuka.\n\n"
        f"Pertanyaan: {question}\n"
        f"Paper: {c.get('paper_title','')}\n"
        f"Abstrak: {(c.get('chunk_text') or '')[:1200]}",
        temperature=0.3, prefer="groq")            # Groq: gratis & cepat utk ringkasan massal
    return (out or "").strip()


def _translate_batch_id(texts: list) -> list:
    """Terjemahkan BANYAK kalimat ke Indonesia dalam SATU panggilan LLM (hemat kuota).
    Return list sejajar; fallback ke teks asli bila baris gagal diparse."""
    if not texts:
        return []
    numbered = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(texts))
    out = _call_llm(
        "Translate each numbered sentence to Indonesian. Keep technical terms and method/model "
        "names in English. Return EXACTLY the same numbered list — one translation per line, "
        "same numbers, no extra text.\n\n" + numbered,
        temperature=0, prefer="groq")
    trans = {}
    for line in (out or "").splitlines():
        m = re.match(r"\s*(\d+)[.)]\s*(.+)", line)
        if m:
            trans[int(m.group(1))] = m.group(2).strip()
    return [trans.get(i + 1, texts[i]) for i in range(len(texts))]


def _attach_summaries(question: str, candidates: list):
    """Isi field 'summary'. Paper S2 yang punya 'tldr' (ringkasan AI bawaan) → diterjemahkan
    ke Indonesia secara BATCH (1 panggilan utk semua → hemat kuota, bahasa konsisten).
    Paper lokal/OpenAlex (tanpa tldr) → ringkasan kontekstual paralel via Groq."""
    if not candidates:
        return
    tldr_cands = [c for c in candidates if (c.get("tldr") or "").strip()]
    need       = [c for c in candidates if not (c.get("tldr") or "").strip()]
    if tldr_cands:                                # S2 tldr → 1 panggilan terjemah utk semua
        trans = _translate_batch_id([c["tldr"].strip() for c in tldr_cands])
        for c, t in zip(tldr_cands, trans):
            c["summary"] = t
    if need:                                      # lokal/OpenAlex → ringkas kontekstual (paralel)
        with ThreadPoolExecutor(max_workers=min(len(need), 6)) as ex:
            sums = list(ex.map(lambda c: _summarize_source(question, c), need))
        for c, s in zip(need, sums):
            c["summary"] = s or (c.get("chunk_text", "")[:200])   # fallback: cuplikan abstrak


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
        pvecs = embed_many([f"{p['title']} {p['abstract']}"[:2000] for p in papers])  # batch
        scored = sorted(zip((float(np.dot(q, v)) for v in pvecs), papers), key=lambda x: -x[0])
        candidates = []
        for s, p in scored[:top_k]:
            authors, year, apa = _external_citation(p)
            candidates.append({"paper_title": p["title"], "authors": authors, "year": year,
                               "citation": apa, "chunk_text": p["abstract"], "score": s,
                               "doi": p["doi"], "cited_by": p["cited_by"],
                               "tldr": p.get("tldr", ""), "source": p["source"]})

    gen = cot_generate(paragraph, candidates)
    best_title = gen.get("best_reference_paper", "")
    ref = next((c for c in candidates if c["paper_title"] == best_title), None)
    if ref is None and best_title:
        ref = next((c for c in candidates
                    if best_title.lower() in c["paper_title"].lower()
                    or c["paper_title"].lower() in best_title.lower()), None)
    if ref is None and candidates:
        ref = candidates[0]

    # Lapis 1+3 utk fallback eksternal (sebelumnya TAK ADA): floor absolut tinggi + verify KETAT.
    # Tutup pintu belakang "maksa/ganti klaim" pada klaim tunggal ngawur.
    if gen.get("relevant") and ref:
        if ref.get("score", 0.0) < EXT_MIN_SIM or not _verify_support(paragraph, ref, strict=True):
            gen["relevant"] = False
            gen["reasoning"] = (gen.get("reasoning", "") +
                                " [Ditolak: tidak ada paper yang mendukung klaim SPESIFIK yang ditulis.]")

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
    pvecs = embed_many([f"{p['title']} {p['abstract']}"[:2000] for p in papers])  # batch
    scored = sorted(zip((float(np.dot(qv, v)) for v in pvecs), papers), key=lambda x: -x[0])
    cand = []
    for s, p in scored[:top_k]:
        a, y, apa = _external_citation(p)
        cand.append({"paper_title": p["title"], "authors": a, "year": y, "citation": apa,
                     "chunk_text": p["abstract"], "score": s, "doi": p.get("doi", ""),
                     "tldr": p.get("tldr", "")})
    # Floor absolut TINGGI dulu: eksternal luas → buang yang cuma nyerempet kata.
    cand = [c for c in cand if c.get("score", 0.0) >= EXT_MIN_SIM]
    cand = _gate_candidates(cand)                            # Lapis 1
    if not cand:
        return None
    gen = cot_generate(sentence, cand)
    if not gen.get("relevant"):
        return None
    ref = _match_ref(cand, gen.get("best_reference_paper", ""))
    # Lapis 3 KETAT: harus mendukung klaim spesifik (setopik tak cukup) → tutup pintu belakang.
    return ref if _verify_support(sentence, ref, strict=EXT_VERIFY_STRICT) else None


def _rewrite_with_reference(sentence: str, ref: dict) -> str:
    """Sisipkan sitasi. DEFAULT deterministik: taruh penanda sebelum titik akhir — bersih,
    tanpa klausa jembatan, kata-kata asli utuh, tanpa panggilan LLM. CITE_POLISH=1 → poles LLM
    (routed ke GPT-4o-mini yang patuh; llama cenderung tetap menambah klausa retoris)."""
    cite = ref.get("citation", "")
    if not CITE_POLISH:
        return _insert_cite(sentence, cite)
    prompt = (
        "Return the sentence below almost verbatim: fix only grammar/formality if strictly needed, "
        f"and append the citation marker \"({cite})\" at the end, right before the final period. "
        "Add NOTHING else — no explanatory or bridging clause about the reference "
        "('as evidenced by', 'which shows', 'demonstrating', etc.). The output must be essentially "
        "the same sentence plus the citation. Keep the SAME language. Output ONLY the sentence.\n\n"
        f"Sentence: {sentence}"
    )
    out = _call_llm(prompt, temperature=0, prefer="openrouter").strip().strip('"')
    if not out:
        return _insert_cite(sentence, cite)
    if cite and f"({cite})" not in out:          # pastikan penanda ada
        out = _insert_cite(out, cite)
    return out


def _is_citable_claim(sent: str) -> bool:
    """True bila kalimat = klaim latar/prior-work yang PANTAS disitasi. False bila kontribusi/
    metode/hasil penulis sendiri atau kalimat generik. (Hasil ukur: kalimat kosong 'experiments
    demonstrate SOTA' skornya 0.93 → threshold buta, harus difilter di sini.)"""
    if not CITE_SKIP_NONCLAIM:
        return True
    out = _call_llm(
        "In academic writing, would the sentence below normally carry a citation to prior work? "
        "Answer NO if it states the authors' OWN contribution/aim/method/result (e.g. 'we propose', "
        "'in this paper', 'our experiments show', 'results demonstrate ... performance'), a mere "
        "transition, or generic filler with no citable factual claim about background/prior work.\n"
        "Answer with exactly one word: YES or NO.\n\n"
        f"Sentence: {sent}", temperature=0, prefer="groq")
    return (out or "").strip().upper().startswith("Y")


def _select_citation(sent: str, top_k: int, allow_external: bool, prefer_external: bool) -> dict:
    """Fase SELEKSI 1 kalimat (belum rewrite). Return {sent, ref, alts, source, skipped}.
    alts = kandidat lokal ter-gate (utk reassignment saat kena cap). Error → skip graceful."""
    try:
        if not _is_citable_claim(sent):                       # kalimat non-klaim → tak disitasi
            return {"sent": sent, "ref": None, "alts": [], "source": "lokal", "skipped": True}
        ref, source, alts = None, "lokal", []
        if prefer_external:                                   # 🌐 ON → eksternal langsung
            ref = _find_external_ref(sent, top_k)
            if ref:
                source = "eksternal"
        else:
            alts = _gate_candidates(search_database(embed(sent), top_k=top_k))   # Lapis 1
            gen = cot_generate(sent, alts) if alts else {"relevant": False}
            if gen.get("relevant"):
                ref = _match_ref(alts, gen.get("best_reference_paper", ""))
                if not _verify_support(sent, ref, strict=CITE_STRICT_VERIFY):    # Lapis 3 (ketat)
                    ref = None
            if ref is None and allow_external:                # fallback eksternal live
                ref = _find_external_ref(sent, top_k)
                if ref:
                    source = "eksternal"
        return {"sent": sent, "ref": ref, "alts": alts, "source": source, "skipped": False}
    except Exception as e:
        print(f"[cite_abstract] kalimat gagal ({type(e).__name__}: {e}) — dilewati")
        return {"sent": sent, "ref": None, "alts": [], "source": "lokal", "skipped": True}


def _reassign_under_cap(pick: dict, used: dict) -> dict:
    """Paper terpilih sudah mentok cap → cari alternatif di kandidat lain yang masih di bawah
    cap DAN lolos verify ketat (biar variatif, bukan asal ganti). None bila tak ada."""
    chosen_cit = (pick.get("ref") or {}).get("citation")
    for c in pick.get("alts", []):
        cit = c.get("citation")
        if not cit or cit == chosen_cit or used.get(cit, 0) >= CITE_MAX_PER_PAPER:
            continue
        if _verify_support(pick["sent"], c, strict=CITE_STRICT_VERIFY):
            return c
    return None


def cite_abstract(paragraph: str, top_k: int = 5, allow_external: bool = True,
                  prefer_external: bool = False) -> dict:
    """Tiap kalimat abstrak: cari referensi → tulis ulang memuat kontribusi paper + sitasi.
    Penjaga kualitas (hasil pengukuran skor): (1) skip kalimat non-klaim, (2) verify ketat,
    (3) cap per-paper max CITE_MAX_PER_PAPER + reassign ke alternatif variatif.
    Fase: seleksi PARALEL → cap SEKUENSIAL → rewrite PARALEL.
    prefer_external=True (🌐): ambil langsung eksternal live, lewati korpus lokal."""
    init()
    sents = _split_sentences(paragraph)
    with ThreadPoolExecutor(max_workers=min(len(sents), 4) or 1) as ex:
        picks = list(ex.map(
            lambda s: _select_citation(s, top_k, allow_external, prefer_external), sents))

    # Cap per-paper + reassign — SEKUENSIAL (jaga urutan kalimat; sitasi pertama dipertahankan).
    used, finals = {}, []
    for p in picks:
        ref, source = p["ref"], p["source"]
        cit = (ref or {}).get("citation")
        if ref and cit and used.get(cit, 0) >= CITE_MAX_PER_PAPER:   # sudah mentok → variasikan
            alt = _reassign_under_cap(p, used)
            ref, source = (alt, "lokal") if alt else (None, source)
            cit = (ref or {}).get("citation")
        if ref and cit:
            used[cit] = used.get(cit, 0) + 1
        finals.append((p["sent"], ref, source))

    # Rewrite PARALEL (kalimat tanpa ref → dibiarkan apa adanya).
    def _rw(item):
        sent, ref, source = item
        if ref and ref.get("citation"):
            return _rewrite_with_reference(sent, ref), ref, source
        return sent, None, source
    with ThreadPoolExecutor(max_workers=min(len(finals), 4) or 1) as ex:
        results = list(ex.map(_rw, finals))

    out_sents, refs, seen = [], [], {}
    for text, ref, source in results:                         # urutan kalimat terjaga
        out_sents.append(text)
        if ref and ref.get("citation") and ref["citation"] not in seen:
            seen[ref["citation"]] = len(refs) + 1
            refs.append({"n": len(refs) + 1, "citation": ref["citation"],
                         "paper_title": ref["paper_title"], "authors": ref.get("authors", ""),
                         "year": ref.get("year", ""), "doi": ref.get("doi", ""),
                         "cited_by": ref.get("cited_by", 0), "score": ref.get("score"),
                         "chunk_text": (ref.get("chunk_text") or "")[:1200],
                         "source": source})
    refs.sort(key=_rank_key, reverse=True)                    # daftar referensi: paper baru diutamakan
    for i, rf in enumerate(refs, 1):                          # penomoran ulang (in-text pakai penanda, bukan nomor)
        rf["n"] = i
    _attach_summaries(paragraph[:800], refs)                  # ringkasan AI per referensi (panel)
    return {"cited_abstract": " ".join(out_sents), "references": refs,
            "n_sentences": len(out_sents), "n_cited": len(refs)}

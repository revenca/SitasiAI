"""
pipeline.py — HyDE + CoT + RAG untuk citation recommendation.
Baca dataset_v1.csv, proses setiap source paragraph, simpan ke hasil_prediksi.csv.
Pastikan indexing.py sudah dijalankan terlebih dahulu.
"""

import os
# Hindari konflik OpenMP (torch + faiss + numpy) di Windows — harus diset SEBELUM import lib
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import json
import re
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np
import faiss
import pandas as pd
import torch
from pathlib import Path
from openai import OpenAI
from transformers import AutoTokenizer
from adapters import AutoAdapterModel

# Muat variabel dari file .env jika ada
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── CONFIG ─────────────────────────────────────────────────────────────────────
FAISS_INDEX_FILE = os.getenv("FAISS_INDEX_FILE", "faiss_index.bin")
METADATA_FILE    = os.getenv("METADATA_FILE", "metadata.json")
DATASET_FILE     = "ground_truth_human.csv"   # ambil query langsung dari GT resmi
GT_COL           = "ground_truth"             # kolom label 0/1
RESULTS_DIR      = "hasil_eksperimen"
OUTPUT_FILE      = f"{RESULTS_DIR}/hasil_prediksi.csv"

TOP_K       = int(os.getenv("TOP_K", "5"))   # bisa diatur via env utk variasi K
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "8"))   # turunkan kalau jalan paralel 2 terminal
GT_FILE     = "ground_truth_human.csv"
GT_COL      = "ground_truth"

# Hyperparameter (untuk analisis sensitivitas — bisa diatur via env)
HYDE_TEMP   = float(os.getenv("HYDE_TEMP", "0.7"))   # temperature HyDE
COT_TEMP    = float(os.getenv("COT_TEMP",  "0.2"))   # temperature CoT
HYDE_WORDS  = os.getenv("HYDE_WORDS", "100-150")     # panjang abstrak HyDE (kata)
HYDE_N             = int(os.getenv("HYDE_N", "1"))                # jumlah abstrak hipotetis (Gao et al. multi-gen; 1=single-shot lama)
HYDE_INCLUDE_QUERY = os.getenv("HYDE_INCLUDE_QUERY", "0") == "1"  # sertakan embedding paragraf asli dlm rata-rata (hybrid query+HyDE)
RUN_TAG     = os.getenv("RUN_TAG", "")               # suffix nama file output
RETRIEVAL_ONLY = os.getenv("RETRIEVAL_ONLY", "0") == "1"  # uji retrieval murni: hanya embed+retrieve, lewati generasi & judge

# MODE ablation:
#   baseline      = embed source langsung, generate simple
#   hyde          = HyDE → embed, generate simple
#   cot           = embed source langsung, generate CoT
#   proposed      = HyDE → embed, generate CoT
#   query_extract = ekstrak klaim → embed, generate CoT  ← query expansion baru
MODE = os.getenv("PIPELINE_MODE", "proposed")

# OpenRouter API — GPT-4o-mini (diambil dari .env / env var)
OPENROUTER_API_KEY  = os.getenv("OPENROUTER_API_KEY", "sk-or-GANTI_DENGAN_API_KEY_ANDA")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
GEN_MODEL           = os.getenv("GEN_MODEL", "openai/gpt-4o-mini")

MODEL_NAME   = "allenai/specter2_base"   # SPECTER2 base
ADAPTER_NAME = "allenai/specter2"        # proximity adapter

# Kolom di dataset_v1.csv
COL_SOURCE = "page_content_sumber"

# Kolom judul paper sumber → dipakai untuk exclude chunk dari paper yang sama.
# CATATAN: nilai di kolom ini TERPOTONG (~98 char), jadi pencocokan dengan
# paper_title di metadata FAISS memakai PREFIX (startswith), bukan exact match.
COL_SOURCE_PAPER = "title_paper_sumber"
# ───────────────────────────────────────────────────────────────────────────────


def norm_title(s: str) -> str:
    """Normalisasi judul sumber yang terpotong: buang sisa ekstensi .pdf/.pd/.p/. di akhir."""
    s = str(s).strip()
    s = re.sub(r"\.p?d?f?$", "", s)
    return s.strip()


# ── SPECTER2 ───────────────────────────────────────────────────────────────────
print(f"Memuat encoder embedding '{MODEL_NAME}' + adapter '{ADAPTER_NAME}'...")
_tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
_model     = AutoAdapterModel.from_pretrained(MODEL_NAME)
_model.load_adapter(ADAPTER_NAME, source="hf", load_as="proximity", set_active=True)
_model.set_active_adapters("proximity")
_model.eval()
_device = "cuda" if torch.cuda.is_available() else "cpu"
_model.to(_device)
print(f"  Device: {_device} | Adapter: proximity\n")


def embed(text: str) -> np.ndarray:
    inputs = _tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        max_length=512,
        padding=True,
    )
    inputs = {k: v.to(_device) for k, v in inputs.items()}
    with torch.no_grad():
        output = _model(**inputs)
    embedding = output.last_hidden_state[:, 0, :]
    embedding = torch.nn.functional.normalize(embedding, dim=1)
    return embedding.squeeze().cpu().numpy()


# ── OpenRouter client (GPT-4o-mini) ────────────────────────────────────────────
_client = OpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url=OPENROUTER_BASE_URL,
    default_headers={
        "HTTP-Referer": "thesis-citation-rag",
        "X-Title":      "Citation RAG Pipeline",
    },
)


def _call_llm(prompt: str, temperature: float = 0.3, retries: int = 3) -> str:
    """Panggil GPT-4o-mini via OpenRouter dengan retry sederhana."""
    for attempt in range(1, retries + 1):
        try:
            resp = _client.chat.completions.create(
                model=GEN_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            print(f"    [GPT-4o-mini] Attempt {attempt}/{retries} gagal: {e}")
            if attempt < retries:
                time.sleep(2 ** attempt)
    return ""


# ── Step A: HyDE ───────────────────────────────────────────────────────────────
def extract_query(source_paragraph: str) -> str:
    """
    Ekstraksi Kueri: reduksi paragraf panjang → klaim atomik padat.
    Output berupa 1-2 kalimat yang berisi klaim spesifik + keyword teknis
    → lebih cocok untuk SPECTER embedding daripada paragraf panjang.
    """
    prompt = (
        "You are an academic research assistant. Given a paragraph from a scientific paper, "
        "extract the single most specific and citable claim, finding, method, or result "
        "that requires a citation.\n\n"
        "Requirements:\n"
        "- Output ONLY 1-2 sentences maximum.\n"
        "- Include specific technical terms, model names, dataset names, or metrics.\n"
        "- Make it dense with keywords that would appear in the cited paper.\n"
        "- Do NOT include context or explanation — just the core citable claim.\n\n"
        f"Paragraph:\n{source_paragraph}\n\n"
        "Extracted claim (1-2 sentences only):"
    )
    return _call_llm(prompt, temperature=0.1)


def hyde_generate(source_paragraph: str) -> str:
    """
    Citation-Aware HyDE (domain-agnostic): abstrak hipotetis yang mendukung klaim paragraf,
    menyimpulkan domain riset dari paragraf (BUKAN asumsi CS) + grounding agar tidak melenceng.
    """
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
        f"Draft Paragraph:\n{source_paragraph}"
    )
    return _call_llm(prompt, temperature=HYDE_TEMP)


# ── FAISS retrieve ─────────────────────────────────────────────────────────────
def retrieve(
    query_embedding: np.ndarray,
    index: faiss.Index,
    metadata: list,
    source_paper: str = "",
    top_k: int = TOP_K,
) -> list:
    """
    Cari top_k chunks paling relevan dari FAISS index.
    Jika source_paper tidak kosong, exclude chunks dari paper yang sama.

    Pencocokan paper sumua memakai PREFIX karena judul di dataset terpotong:
    chunk di-exclude bila paper_title diawali oleh judul sumber (ternormalisasi).
    """
    query         = query_embedding.reshape(1, -1).astype(np.float32)
    # Ambil lebih banyak kandidat untuk kompensasi filtering same-paper
    n_candidates  = top_k * 5 if source_paper else top_k
    scores, idxs  = index.search(query, min(n_candidates, index.ntotal))

    source_key = norm_title(source_paper).lower() if source_paper else ""

    results = []
    for score, idx in zip(scores[0], idxs[0]):
        if idx < 0 or idx >= len(metadata):
            continue
        chunk_meta = metadata[idx]
        # Exclude chunks dari paper sumber yang sama (prefix match, judul terpotong)
        if source_key and chunk_meta["paper_title"].lower().startswith(source_key):
            continue
        results.append({
            "paper_title": chunk_meta["paper_title"],
            "chunk_text":  chunk_meta["chunk_text"],
            "score":       float(score),
        })
        if len(results) >= top_k:
            break

    return results


# ── Step B: CoT Citation Generation ───────────────────────────────────────────
def cot_generate(source_paragraph: str, retrieved_chunks: list) -> dict:
    """
    Gunakan CoT prompt ke GPT-4o-mini untuk memilih referensi terbaik
    dan menghasilkan kalimat sitasi akademik.
    """
    chunks_formatted = "\n---\n".join(
        f"[Referensi {i + 1}] {c['paper_title']}:\n{c['chunk_text']}"
        for i, c in enumerate(retrieved_chunks)
    )

    prompt = (
        "You are an academic citation assistant. Use chain-of-thought reasoning "
        "to determine if the retrieved reference is relevant and generate a "
        "proper academic citation sentence.\n\n"
        f"Source paragraph (needs citation):\n{source_paragraph}\n\n"
        f"Retrieved reference content:\n{chunks_formatted}\n\n"
        "Think step by step:\n"
        "Step 1: What is the main claim, method, or finding in the source paragraph?\n"
        "Step 2: What specific facts/methods/results does each retrieved reference contain?\n"
        "Step 3: Which retrieved reference contains content that most directly supports the "
        "source claim? Pick based on overlap of specific facts, not just topic similarity.\n"
        "Step 4: Is the best reference truly relevant? (Yes/No and reason)\n"
        "Step 5: If relevant, write a one-sentence academic citation. "
        "CRITICAL GROUNDING RULE: the citation must state ONLY specific facts, methods, "
        "or findings that are EXPLICITLY present in the chosen reference content above. "
        "Do NOT add general background claims, and do NOT include information that is not "
        "written in the reference text. Paraphrase the reference's actual content.\n\n"
        "Output format (JSON only, no markdown, no extra text):\n"
        "{\n"
        '  "relevant": true,\n'
        '  "best_reference_paper": "paper title here",\n'
        '  "best_reference_chunk": "chunk text used",\n'
        '  "citation_text": "generated citation sentence or null",\n'
        '  "reasoning": "brief explanation"\n'
        "}"
    )

    raw = _call_llm(prompt, temperature=COT_TEMP)

    # Bersihkan markdown code block jika ada
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    raw = re.sub(r"\s*```$", "", raw)

    try:
        result = json.loads(raw)
        # Normalisasi tipe
        result["relevant"] = bool(result.get("relevant", False))
        # Pastikan semua field string tidak None (LLM bisa kirim null)
        for key in ("best_reference_paper", "best_reference_chunk", "citation_text", "reasoning"):
            val = result.get(key)
            result[key] = "" if val in (None, "null") else str(val)
        return result
    except json.JSONDecodeError:
        return {
            "relevant":             False,
            "best_reference_paper": "",
            "best_reference_chunk": "",
            "citation_text":        "",
            "reasoning":            f"JSON parse error. Raw output: {raw[:300]}",
        }


# ── Step B alt: Simple Generation (tanpa CoT, untuk baseline & HyDE mode) ─────
def simple_generate(source_paragraph: str, retrieved_chunks: list) -> dict:
    """Generate sitasi langsung tanpa chain-of-thought (untuk mode baseline & hyde)."""
    if not retrieved_chunks:
        return {"relevant": False, "best_reference_paper": "",
                "best_reference_chunk": "", "citation_text": "", "reasoning": "Tidak ada chunk."}

    chunks_formatted = "\n---\n".join(
        f"[Ref {i+1}] {c['paper_title']}\n{c['chunk_text']}"
        for i, c in enumerate(retrieved_chunks[:5])
    )
    prompt = (
        "You are an academic citation assistant. Given a source paragraph and retrieved "
        "references, select the reference whose content most directly supports the source "
        "claim (based on overlap of specific facts, not just topic), then write a "
        "one-sentence academic citation.\n\n"
        f"Source paragraph:\n{source_paragraph}\n\n"
        f"Retrieved references:\n{chunks_formatted}\n\n"
        "CRITICAL GROUNDING RULE: the citation must state ONLY specific facts, methods, or "
        "findings EXPLICITLY present in the chosen reference content. Do NOT add general "
        "claims or information not written in the reference text.\n\n"
        "Output format (JSON only):\n"
        "{\n"
        '  "relevant": true,\n'
        '  "best_reference_paper": "paper title",\n'
        '  "best_reference_chunk": "chunk text used",\n'
        '  "citation_text": "one-sentence citation or null",\n'
        '  "reasoning": "brief reason"\n'
        "}"
    )
    raw = _call_llm(prompt, temperature=0.2)
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    raw = re.sub(r"\s*```$", "", raw)
    try:
        result = json.loads(raw)
        result["relevant"] = bool(result.get("relevant", False))
        for key in ("best_reference_paper", "best_reference_chunk", "citation_text", "reasoning"):
            val = result.get(key)
            result[key] = "" if val in (None, "null") else str(val)
        return result
    except json.JSONDecodeError:
        return {"relevant": False, "best_reference_paper": "", "best_reference_chunk": "",
                "citation_text": "", "reasoning": f"JSON parse error: {raw[:200]}"}


# ── Filter gold reference ──────────────────────────────────────────────────────
def _source_paragraphs_with_gold(df: pd.DataFrame = None):
    """
    Kembalikan set page_content_sumber yang punya MINIMAL satu referensi valid,
    diambil langsung dari ground_truth_human.csv (kolom ground_truth = 1).
    Return None jika file tidak tersedia (→ proses semua paragraf).
    """
    if not Path(GT_FILE).exists():
        print(f"  [WARN] '{GT_FILE}' tidak ada — PROCESS_ONLY_GOLD dilewati, proses semua.")
        return None

    gt = pd.read_csv(GT_FILE)
    label = gt[GT_COL].map(
        {"TRUE": 1, "FALSE": 0, True: 1, False: 0, 1: 1, 0: 0}
    ).fillna(0).astype(int)
    gold_sources = set(gt[COL_SOURCE][label == 1].tolist())
    return gold_sources


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    # Validasi file yang dibutuhkan
    for required in (FAISS_INDEX_FILE, METADATA_FILE, DATASET_FILE):
        if not Path(required).exists():
            print(f"[ERROR] File '{required}' tidak ditemukan.", file=sys.stderr)
            if required in (FAISS_INDEX_FILE, METADATA_FILE):
                print("  → Jalankan indexing.py terlebih dahulu.", file=sys.stderr)
            sys.exit(1)

    # Load FAISS index + metadata
    print("Memuat FAISS index dan metadata...")
    index    = faiss.read_index(FAISS_INDEX_FILE)
    with open(METADATA_FILE, encoding="utf-8") as f:
        metadata = json.load(f)
    print(f"  {index.ntotal} vektor dimuat dari '{FAISS_INDEX_FILE}'.\n")

    # Load ground_truth_human.csv — ambil langsung baris yang ground_truth==1
    df = pd.read_csv(DATASET_FILE)
    if COL_SOURCE not in df.columns:
        print(
            f"[ERROR] Kolom '{COL_SOURCE}' tidak ditemukan di '{DATASET_FILE}'.\n"
            f"  Kolom tersedia: {list(df.columns)}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Filter hanya baris gold (ground_truth==1), dedup per paragraf sumber
    df_gold = df[df[GT_COL].map(
        {"TRUE":1,"FALSE":0,True:1,False:0,1:1,0:0}).fillna(0).astype(int) == 1
    ]
    cols = [COL_SOURCE]
    if COL_SOURCE_PAPER and COL_SOURCE_PAPER in df_gold.columns:
        cols.append(COL_SOURCE_PAPER)
    paragraphs_df = df_gold[cols].drop_duplicates(subset=[COL_SOURCE]).reset_index(drop=True)

    print(f"MODE          : {MODE.upper()}")
    print(f"  HyDE        : {'Ya' if MODE in ('hyde','proposed') else 'Tidak'}")
    print(f"  CoT         : {'Ya' if MODE in ('cot','proposed') else 'Tidak'}")
    print(f"Sumber query  : {DATASET_FILE} (ground_truth==1)")
    print(f"Paragraf unik : {len(paragraphs_df)}\n")

    # Output per mode (+ RUN_TAG untuk eksperimen sensitivitas)
    os.makedirs(RESULTS_DIR, exist_ok=True)
    _tag = f"_{RUN_TAG}" if RUN_TAG else ""
    out_file = OUTPUT_FILE.replace(".csv", f"_{MODE}_k{TOP_K}{_tag}.csv")
    print(f"  HyDE temp   : {HYDE_TEMP} | CoT temp: {COT_TEMP} | HyDE words: {HYDE_WORDS}")
    if RUN_TAG:
        print(f"  RUN_TAG     : {RUN_TAG}  → {out_file}")
    total = len(paragraphs_df)

    # Lock embedding: inference torch dari banyak thread di-serialkan (cepat di GPU),
    # sedangkan panggilan API HyDE+CoT (lambat, I/O) tetap berjalan paralel.
    embed_lock = threading.Lock()
    progress = {"done": 0}
    progress_lock = threading.Lock()

    use_hyde          = MODE in ("hyde", "proposed")
    use_cot           = MODE in ("cot", "proposed", "query_extract")
    use_query_extract = MODE == "query_extract"

    def process_one(i, para, source_paper):
        # ── A. Query expansion ────────────────────────────────────────────────
        hyde_fallback = False
        if use_hyde:
            # HyDE (Gao et al. 2022): generate HYDE_N abstrak hipotetis (LLM, I/O paralel-friendly),
            # embed tiap abstrak, (opsional) sertakan embedding paragraf asli, lalu RATA-RATA + normalisasi L2.
            hyps = [h for h in (hyde_generate(para) for _ in range(HYDE_N)) if h]
            hyde_fallback = (len(hyps) == 0)           # semua generasi HyDE gagal → fallback ke paragraf
            with embed_lock:
                vecs = [embed(h) for h in hyps]
                if HYDE_INCLUDE_QUERY or not vecs:     # sertakan paragraf asli (hybrid), atau fallback bila HyDE gagal
                    vecs.append(embed(para))
            qv = np.mean(np.vstack(vecs), axis=0)
            query_emb = (qv / (np.linalg.norm(qv) + 1e-12)).astype(np.float32)
        elif use_query_extract:
            query_text = extract_query(para) or para   # ekstrak klaim atomik
            with embed_lock:
                query_emb = embed(query_text)
        else:
            query_text = para                          # source langsung
            with embed_lock:
                query_emb = embed(query_text)

        # ── Retrieve top-K ───────────────────────────────────────────────────
        retrieved = retrieve(query_emb, index, metadata, source_paper=source_paper)
        if not retrieved:
            return {
                "citation_id":        i + 1,
                "source_paragraph":   para,
                "retrieved_paper":    "",
                "retrieved_chunk":    "",
                "retrieved_contexts": "[]",
                "relevant":           False,
                "citation_text":      "",
                "reasoning":          "Tidak ada chunk yang di-retrieve.",
                "hyde_fallback":      hyde_fallback,
            }

        # ── B. Generation (CoT atau Simple) ──────────────────────────────────
        if RETRIEVAL_ONLY:                     # uji retrieval murni: lewati generasi (& judge di evaluate)
            return {
                "citation_id":        i + 1,
                "source_paragraph":   para,
                "retrieved_paper":    "",
                "retrieved_chunk":    "",
                "retrieved_contexts": json.dumps([c["chunk_text"] for c in retrieved], ensure_ascii=False),
                "relevant":           False,
                "citation_text":      "",
                "reasoning":          "retrieval-only",
                "hyde_fallback":      hyde_fallback,
            }
        gen = cot_generate(para, retrieved) if use_cot else simple_generate(para, retrieved)
        return {
            "citation_id":        i + 1,
            "source_paragraph":   para,
            "retrieved_paper":    gen.get("best_reference_paper", ""),
            "retrieved_chunk":    gen.get("best_reference_chunk", ""),
            "retrieved_contexts": json.dumps([c["chunk_text"] for c in retrieved], ensure_ascii=False),
            "relevant":           gen.get("relevant", False),
            "citation_text":      gen.get("citation_text", ""),
            "reasoning":          gen.get("reasoning", ""),
            "hyde_fallback":      hyde_fallback,
        }

    print(f"Memproses paralel dengan {MAX_WORKERS} worker...\n")
    rows_by_idx = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {
            ex.submit(process_one, i, row[COL_SOURCE],
                      row[COL_SOURCE_PAPER] if COL_SOURCE_PAPER and COL_SOURCE_PAPER in row.index else ""): i
            for i, row in paragraphs_df.iterrows()
        }
        for fut in as_completed(futures):
            i = futures[fut]
            try:
                res = fut.result()
            except Exception as e:
                res = {
                    "citation_id": i + 1, "source_paragraph": paragraphs_df.iloc[i][COL_SOURCE],
                    "retrieved_paper": "", "retrieved_chunk": "", "retrieved_contexts": "[]",
                    "relevant": False, "citation_text": "", "reasoning": f"Error: {e}",
                    "hyde_fallback": False,
                }
            rows_by_idx[i] = res
            with progress_lock:
                progress["done"] += 1
                d = progress["done"]
            rel = "RELEVAN" if res.get("relevant") else "tidak relevan"
            print(f"[{d:4d}/{total}] [{rel}] → {str(res.get('retrieved_paper',''))[:55]}")

    # Susun ulang sesuai urutan asli
    rows = [rows_by_idx[i] for i in sorted(rows_by_idx)]
    result_df = pd.DataFrame(rows)
    result_df.to_csv(out_file, index=False, encoding="utf-8")

    n_relevant = result_df["relevant"].sum()
    print(f"\nSelesai! {len(rows)} paragraf diproses.")
    print(f"  Relevan    : {n_relevant} ({n_relevant / len(rows) * 100:.1f}%)")
    print(f"  Tidak rel. : {len(rows) - n_relevant}")
    if use_hyde and "hyde_fallback" in result_df.columns:
        n_fb = int(result_df["hyde_fallback"].sum())
        if n_fb:
            print(f"  ⚠️ HyDE gagal: {n_fb} baris fallback ke paragraf mentah — baris ini TIDAK benar-benar pakai HyDE")
        else:
            print(f"  HyDE OK    : semua {len(rows)} kueri benar-benar pakai HyDE (0 fallback)")
    print(f"  Output     : '{out_file}'")


if __name__ == "__main__":
    main()

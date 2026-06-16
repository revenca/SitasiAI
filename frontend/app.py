"""
frontend/app.py — Antarmuka Streamlit bergaya Elicit untuk rekomendasi sitasi.
Jalankan dari root proyek:  streamlit run frontend/app.py
"""
import os, sys
from pathlib import Path

# Tambahkan root proyek ke path agar bisa import backend
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)  # agar path index relatif benar

import streamlit as st
from backend import rag_engine

st.set_page_config(page_title="Citation Recommender", page_icon="📚", layout="wide")

# ── CSS gaya Elicit ──────────────────────────────────────────────────────────
st.markdown("""
<style>
#MainMenu, footer, header {visibility: hidden;}
.block-container {padding-top: 2rem; max-width: 820px;}
section[data-testid="stSidebar"] {background:#f7f7f5; border-right:1px solid #ececec;}
section[data-testid="stSidebar"] .stMarkdown {font-size:0.9rem;}
/* judul tengah */
.hero {text-align:center; margin: 8vh 0 1.5rem 0;}
.hero h1 {font-size:1.9rem; font-weight:700; color:#1a1a1a; margin-bottom:.3rem;}
.hero p {color:#6b7280; font-size:1rem;}
/* kotak input */
.stTextArea textarea {
    border:1.5px solid #d9d9d6 !important; border-radius:16px !important;
    padding:16px !important; font-size:1rem !important; box-shadow:0 1px 3px rgba(0,0,0,.04);
    background:#fff !important;
}
.stTextArea textarea:focus {border-color:#0f766e !important; box-shadow:0 0 0 3px rgba(15,118,110,.1) !important;}
/* tombol utama teal */
.stButton button[kind="primary"] {
    background:#0f766e !important; border:none !important; border-radius:12px !important;
    font-weight:600 !important; padding:.5rem 1.4rem !important;
}
.stButton button[kind="primary"]:hover {background:#0c5d56 !important;}
/* kartu kandidat */
div[data-testid="stContainer"] {border-radius:14px;}
.score-pill {background:#ecfdf5; color:#0f766e; padding:3px 10px; border-radius:999px;
    font-size:.8rem; font-weight:600;}
.brand {font-size:1.25rem; font-weight:700; color:#0f766e; padding:.5rem 0 1rem 0;}
</style>
""", unsafe_allow_html=True)

# ── Muat engine (cache) ──────────────────────────────────────────────────────
@st.cache_resource(show_spinner="Memuat SPECTER2 + FAISS...")
def boot():
    rag_engine.init()
    return True
boot()

# ── Sidebar (gaya Elicit) ────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="brand">📚 SitasiAI</div>', unsafe_allow_html=True)
    st.markdown("**WORKFLOWS**")
    st.markdown("🔎 &nbsp;Rekomendasi Sitasi")
    st.markdown("📄 &nbsp;Laporan")
    st.divider()
    st.markdown("**PENGATURAN**")
    top_k    = st.slider("Top-K rekomendasi", 3, 10, 5)
    use_hyde = st.checkbox("HyDE (query expansion)", value=True)
    use_cot  = st.checkbox("CoT (penalaran)", value=True)
    st.divider()
    st.caption(f"Index: {rag_engine._index.ntotal} chunk")
    st.caption("Encoder: SPECTER2 · Generator: GPT-4o-mini")

# ── Hero + input (tengah, gaya Elicit) ───────────────────────────────────────
if "result" not in st.session_state:
    st.markdown('<div class="hero"><h1>Temukan sitasi yang tepat</h1>'
                '<p>Tempel paragraf draf akademikmu, dapatkan rekomendasi paper + kalimat sitasi.</p></div>',
                unsafe_allow_html=True)

para = st.text_area("", height=160,
    placeholder="How does consecutive sampling bias affect clinical trial validity?  "
                "(tempel paragraf draf yang membutuhkan sitasi di sini...)",
    label_visibility="collapsed")

c1, c2, c3 = st.columns([1, 1, 1])
with c2:
    go = st.button("🔍  Cari Rekomendasi", type="primary", use_container_width=True)

# ── Proses & hasil ───────────────────────────────────────────────────────────
if go:
    if not para.strip():
        st.warning("Masukkan paragraf terlebih dahulu.")
        st.stop()
    with st.spinner("Memproses (HyDE → retrieval → CoT)..."):
        res = rag_engine.recommend(para, top_k=top_k, use_hyde=use_hyde, use_cot=use_cot)
    st.session_state["result"] = res

if "result" in st.session_state and go:
    res = st.session_state["result"]
    st.divider()
    if res["relevant"] and res["citation_text"]:
        st.markdown("#### ✅ Kalimat Sitasi yang Direkomendasikan")
        st.success(res["citation_text"])
        st.caption(f"📄 Referensi terbaik: **{res['best_reference_paper']}**")
        if res["reasoning"]:
            with st.expander("Penalaran (CoT)"):
                st.write(res["reasoning"])
    else:
        st.info("Tidak ditemukan referensi yang cukup relevan.")

    st.markdown(f"#### 📑 Top-{top_k} Paper Kandidat")
    for i, c in enumerate(res["candidates"], 1):
        with st.container(border=True):
            a, b = st.columns([0.82, 0.18])
            with a:
                st.markdown(f"**{i}. {c['paper_title']}**")
                st.caption(c["chunk_text"][:280] + ("..." if len(c["chunk_text"]) > 280 else ""))
            with b:
                st.markdown(f'<div class="score-pill">{c["score"]:.3f}</div>', unsafe_allow_html=True)

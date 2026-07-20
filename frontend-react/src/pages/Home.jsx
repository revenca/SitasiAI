import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import api from "../api";
import {
  IconCheck, IconFile, IconArrowRight, IconLibrary,
  IconClose, IconSparkles,
} from "../components/Icons.jsx";
import BookLogo from "../components/BookLogo.jsx";
import { useChat } from "../chat.jsx";

const EXAMPLES = [
  "Deep learning telah meningkatkan akurasi diagnosis pada citra medis.",
  "Cari paper tentang deteksi objek menggunakan UAV",
  "Accurate three-dimensional segmentation of brain structures from MRI scans is often constrained by limited GPU memory, motivating patch-based approaches that process smaller sub-volumes.",
];

// Deteksi: pertanyaan (tanya-jawab) vs paragraf draf (rekomendasi sitasi)
function isQuestion(t) {
  const s = t.trim();
  if (s.endsWith("?")) return true;
  const words = s.split(/\s+/);
  return words.length <= 18 &&
    /^(apa|apakah|kenapa|mengapa|bagaimana|gimana|siapa|kapan|dimana|di\s?mana|berapa|jelaskan|sebutkan|tolong|bisakah|cari|carikan|cariin|temukan|rekomendasikan|find|search|recommend|what|why|how|who|when|where|which|explain|list|tell|can|is|are|does|do)\b/i.test(s);
}

// Contoh prompt untuk animasi placeholder (typewriter)
const PH_PROMPTS = [
  "Tempel paragraf draf yang butuh sitasi…",
  "Electronic nose systems based on gas sensor arrays…",
  "Deep learning telah meningkatkan akurasi diagnosis citra medis…",
  "Accurate 3D segmentation of brain structures from MRI…",
  "Cari paper tentang deteksi objek menggunakan UAV…",
];

export default function Home() {
  const { active, setActiveMessages: setMessages, newChat: newChatCtx } = useChat();
  const messages = active?.messages ?? [];
  const [input, setInput] = useState("");
  const topK = 10;                                  // tetap 10 (dropdown dihapus)
  // Dua mode saja: "sitasi" (auto-deteksi: 1 kalimat → rekomendasi tunggal,
  // multi-kalimat → sitasi per kalimat) dan "cari" (pencarian paper/topik).
  const [mode, setMode] = useState("sitasi");
  const [thinkMode, setThinkMode] = useState("recommend");   // utk indikator proses
  const [loading, setLoading] = useState(false);
  const [drawer, setDrawer] = useState(null);   // candidates[] atau null
  const [focused, setFocused] = useState(false);
  const [ph, setPh] = useState(PH_PROMPTS[0]);
  const endRef = useRef(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, loading]);

  // Panel kanan terbuka -> konten utama menyisih (layar lebar); tutup saat unmount
  useEffect(() => {
    document.body.classList.toggle("panel-open", !!drawer);
    return () => document.body.classList.remove("panel-open");
  }, [drawer]);

  // Animasi placeholder typewriter (ketik → jeda → hapus → ganti) — berhenti saat fokus/mengetik
  useEffect(() => {
    if (focused || input) return;
    let pi = Math.floor(Math.random() * PH_PROMPTS.length), ci = 0, del = false, t;
    const tick = () => {
      const full = PH_PROMPTS[pi];
      ci += del ? -1 : 1;
      setPh(full.slice(0, ci) || " ");
      if (!del && ci >= full.length) { del = true; t = setTimeout(tick, 1500); return; }
      if (del && ci <= 0) { del = false; pi = (pi + 1) % PH_PROMPTS.length; }
      t = setTimeout(tick, del ? 28 : 55);
    };
    t = setTimeout(tick, 600);
    return () => clearTimeout(t);
  }, [focused, input]);

  const send = async (text) => {
    const q = (text ?? input).trim();
    if (!q || loading) return;
    setInput("");
    const userMsg = { id: Date.now(), role: "user", text: q };
    setMessages((m) => [...m, userMsg]);
    setLoading(true);
    try {
      // jumlah kalimat bermakna (≥25 huruf) — penentu rekomendasi tunggal vs per-kalimat
      const nSent = q.split(/(?<=[.!?])\s+/).filter((s) => s.trim().length >= 25).length;
      if (mode === "cari") {
        // Cari paper: pencarian topik (basis data / Semantic Scholar live)
        setThinkMode("external");
        const { data } = await api.post("/ask-external", { question: q, top_k: topK });
        setMessages((m) => [...m, { id: Date.now() + 1, role: "assistant", kind: "ask", query: q, answer: data.answer, candidates: data.candidates, note: data.query_note }]);
        if (data.candidates?.length) setDrawer(data.candidates);   // panel kanan auto-buka
      } else if (isQuestion(q)) {
        setThinkMode("recommend");
        const { data } = await api.post("/ask", { question: q, top_k: topK });
        setMessages((m) => [...m, { id: Date.now() + 1, role: "assistant", kind: "ask", query: q, answer: data.answer, candidates: data.candidates }]);
      } else if (nSent >= 2) {
        // Multi-kalimat → auto-sitasi per kalimat + daftar referensi
        setThinkMode("cite");
        const { data } = await api.post("/cite-abstract", { paragraph: q, top_k: topK });
        setMessages((m) => [...m, { id: Date.now() + 1, role: "assistant", kind: "cite", query: q, cite: data }]);
        if (data.references?.length) setDrawer(data.references);   // panel kanan: daftar referensi + summary
      } else {
        // Satu kalimat/klaim → rekomendasi 1 sitasi terbaik
        setThinkMode("recommend");
        const { data } = await api.post("/recommend", { paragraph: q, top_k: topK });
        setMessages((m) => [...m, { id: Date.now() + 1, role: "assistant", query: q, result: data }]);
        const refs = refListFromResult(data);
        if (refs.length) setDrawer(refs);   // panel kanan: referensi + terkait
      }
    } catch (e) {
      setMessages((m) => [...m, { id: Date.now() + 1, role: "assistant", error: e?.response?.data?.detail || "Terjadi kesalahan." }]);
    } finally {
      setLoading(false);
    }
  };

  // Rakit daftar referensi hasil rekomendasi utk panel kanan (terpilih dulu, lalu terkait)
  const refListFromResult = (r) => {
    if (!r || !r.best_reference_paper) return [];
    const chosen = {
      paper_title: r.best_reference_paper, authors: r.best_reference_authors,
      year: r.best_reference_year, citation: r.best_reference_citation,
      doi: r.best_reference_doi, summary: r.best_reference_summary,
      source: r.source_mode === "eksternal" ? "Semantic Scholar (live)" : "Basis data",
    };
    return [chosen, ...(r.related || [])];
  };

  const newChat = () => { newChatCtx(); setDrawer(null); };

  const onKey = (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  };

  return (
    <div className="chat">
      {/* Thread */}
      <div className="chat-thread">
        {messages.length === 0 && !loading && (
          <div className="chat-empty">
            <div className="chat-empty-logo"><BookLogo size={44} rounded={13} /></div>
            <h2>Halo! Ada yang bisa dibantu?</h2>
            <p>Pilih mode di bawah, lalu tempel paragraf/abstrak atau ketik topik pencarian.</p>
            <div className="chips">
              {EXAMPLES.map((ex, i) => (
                <button key={i} className="chip" onClick={() => send(ex)}>{ex.slice(0, 70)}…</button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m) => (
          <motion.div key={m.id} className={`msg ${m.role}`}
            initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, ease: [0.22, 0.61, 0.36, 1] }}>
            {m.role === "user" ? (
              <div className="bubble user">{m.text}</div>
            ) : m.error ? (
              <div className="bubble bot"><div className="alert error">{m.error}</div></div>
            ) : m.kind === "cite" ? (
              <CiteBubble cite={m.cite} onRefs={() => m.cite?.references?.length && setDrawer(m.cite.references)} />
            ) : m.kind === "ask" ? (
              <div className="bubble bot">
                <div className="bot-label"><IconSparkles size={15} /> Ringkasan</div>
                {m.note && (
                  <div className="query-note">
                    <span className="query-note-ic">💡</span>
                    <span>{m.note}</span>
                  </div>
                )}
                <p className="answer-text"><MdLite text={m.answer} /></p>
                {m.candidates?.length > 0 && (
                  <button className="papers-btn" onClick={() => setDrawer(m.candidates)}>
                    <IconLibrary size={15} /> Lihat sumber ({m.candidates.length}) →
                  </button>
                )}
              </div>
            ) : (
              <BotBubble m={m} onRefs={() => { const refs = refListFromResult(m.result); if (refs.length) setDrawer(refs); }} />
            )}
          </motion.div>
        ))}

        {loading && (
          <div className="msg assistant">
            <ThinkingIndicator mode={thinkMode} />
          </div>
        )}
        <div ref={endRef} />
      </div>

      {/* Composer (selalu tampil — layout lama yang fungsional) */}
      <div className="composer">
        <div className="composer-opts">
          <div className="opt-k">
            <span>Mode</span>
            <select value={mode} onChange={(e) => setMode(e.target.value)}>
              <option value="sitasi">Buat sitasi</option>
              <option value="cari">Cari paper</option>
            </select>
          </div>
        </div>
        <div className="composer-input">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKey}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            placeholder={focused ? "Tulis di sini…  (Enter kirim · Shift+Enter baris baru)" : ph}
            rows={2}
          />
          <motion.button className="send" onClick={() => send()} disabled={loading || !input.trim()}
            whileHover={{ scale: 1.06 }} whileTap={{ scale: 0.92 }}>
            <IconArrowRight size={20} />
          </motion.button>
        </div>
      </div>

      {/* Panel sumber DOCK KANAN (ala Elicit): persisten, scroll sendiri, tanpa backdrop */}
      <AnimatePresence>
        {drawer && (
          <motion.div key="scrim" className="panel-scrim" onClick={() => setDrawer(null)}
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} />
        )}
        {drawer && (
          <motion.aside key="panel" className="side-panel"
            initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }}
            transition={{ type: "spring", stiffness: 340, damping: 36 }}>
            <div className="side-panel-head">
              <span><IconLibrary size={16} /> Sumber ({drawer.length})</span>
              <button onClick={() => setDrawer(null)} aria-label="Tutup panel">
                <IconClose size={17} />
              </button>
            </div>
            <div className="side-panel-body">
              <SourcesTable sources={drawer} bare />
            </div>
          </motion.aside>
        )}
      </AnimatePresence>
    </div>
  );
}

// ── Indikator proses ala "thinking" — shimmer + timer + tahapan ─────
const STAGES = {
  recommend: [
    "Membuat abstrak hipotetis (HyDE)",
    "Menghitung embedding SPECTER2",
    "Mencari di basis data",
    "Menimbang relevansi referensi",
    "Menyusun kalimat sitasi",
  ],
  cite: [
    "Memecah abstrak per kalimat",
    "Mencari referensi tiap kalimat",
    "Memverifikasi relevansi",
    "Menulis ulang kalimat + sitasi",
    "Menyusun daftar referensi",
  ],
  external: [
    "Menyusun kueri pencarian",
    "Mengambil kandidat dari Semantic Scholar",
    "Re-ranking dengan SPECTER2",
    "Menyusun jawaban",
  ],
};

function ThinkingIndicator({ mode = "recommend" }) {
  const [sec, setSec] = useState(0);
  const stages = STAGES[mode] || STAGES.recommend;
  useEffect(() => {
    const t = setInterval(() => setSec((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, []);
  // tahap maju tiap ~6 dtk, berhenti di tahap terakhir (jujur: estimasi, bukan telemetri)
  const idx = Math.min(Math.floor(sec / 6), stages.length - 1);
  return (
    <div className="thinking">
      <div className="thinking-head">
        <svg className="thinking-spin" width="15" height="15" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity=".2" strokeWidth="3" />
          <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
        </svg>
        <span className="thinking-shimmer">{stages[idx]}…</span>
        <span className="thinking-time">{sec}s</span>
      </div>
      <div className="thinking-steps" aria-hidden="true">
        {stages.map((s, i) => (
          <span key={i} className={`thinking-dot${i < idx ? " done" : i === idx ? " now" : ""}`} />
        ))}
      </div>
    </div>
  );
}

// Render markdown ringan pada jawaban: **teks** → tebal, baris baru dipertahankan.
function MdLite({ text }) {
  const parts = String(text || "").split(/\*\*(.+?)\*\*/g);
  return (
    <span style={{ whiteSpace: "pre-wrap" }}>
      {parts.map((p, i) => (i % 2 ? <b key={i}>{p}</b> : p))}
    </span>
  );
}

// Sisipkan penanda sitasi (Author, Year) di akhir kalimat, sebelum tanda titik.
function withCite(text, cite) {
  const t = (text || "").trim();
  if (!cite) return t;
  if (t.includes(`(${cite})`)) return t;            // model sudah menaruhnya → jangan dobel
  const m = t.match(/[.!?]+\s*$/);
  const body = m ? t.slice(0, t.length - m[0].length) : t;
  const end = m ? m[0].trim() : ".";
  return (<>{body} <span className="cited-mark">({cite})</span>{end}</>);
}

// ── Tabel sumber ala Elicit — 2 kolom: Sumber | Ringkasan ───────────
function SourcesTable({ sources, bare = false }) {
  return (
    <div className={`srctable${bare ? " srctable-bare" : ""}`}>
      {!bare && (
        <div className="srctable-head">
          <IconLibrary size={14} /> Sumber ({sources.length})
        </div>
      )}
      <div className="srctab-hrow">
        <div className="srctab-hcell">Sumber</div>
        <div className="srctab-hcell">Ringkasan</div>
      </div>
      {sources.map((s, i) => {
        const meta = [s.authors, s.year, s.cited_by ? `dikutip ${Number(s.cited_by).toLocaleString("id-ID")}×` : null]
          .filter(Boolean).join(" · ");
        const sum = s.summary || s.chunk_text || "";
        return (
          <div className="srctab-row" key={i}>
            <div className="srctab-src">
              <div className="src-title">
                <span className="src-num">{i + 1}</span>
                {s.doi
                  ? <a href={s.doi} target="_blank" rel="noreferrer">{s.paper_title}</a>
                  : s.paper_title}
              </div>
              {meta && <div className="src-meta">{meta}</div>}
              <div className="src-tags">
                {s.source && <span className="src-tag">{s.source}</span>}
                {s.doi && <a className="src-tag src-tag-link" href={s.doi} target="_blank" rel="noreferrer">DOI ↗</a>}
              </div>
            </div>
            <div className="srctab-sum">
              {sum.slice(0, 520)}{sum.length > 520 ? "…" : ""}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Bubble auto-sitasi abstrak ──────────────────────────────────────
function CiteBubble({ cite, onRefs }) {
  if (!cite || !cite.cited_abstract) {
    return <div className="bubble bot"><div className="alert">Gagal memproses abstrak.</div></div>;
  }
  // tebalkan penanda sitasi (…) di teks
  const parts = cite.cited_abstract.split(/(\([^()]*\d{4}[^()]*\))/g);
  return (
    <div className="bubble bot">
      <div className="bot-label"><IconCheck size={15} /> Abstrak Ter-sitasi
        <span style={{ marginLeft: 8, fontSize: 11, color: "#2AA198" }}>
          {cite.n_cited} sitasi · {cite.n_sentences} kalimat
        </span>
      </div>
      <p className="citation-text" style={{ lineHeight: 1.7 }}>
        {parts.map((p, i) => /^\([^()]*\d{4}[^()]*\)$/.test(p)
          ? <span key={i} className="cited-mark">{p}</span> : p)}
      </p>
      {cite.references?.length > 0 && onRefs && (
        <button className="papers-btn" onClick={onRefs}>
          <IconLibrary size={15} /> Lihat referensi ({cite.references.length}) →
        </button>
      )}
      {cite.references?.length > 0 && (
        <div className="ref-box">
          <div className="ref-title"><IconLibrary size={14} /> Daftar Referensi ({cite.references.length})</div>
          <ol style={{ margin: "6px 0 0", paddingLeft: 18, fontSize: 13, lineHeight: 1.6 }}>
            {cite.references.map((r) => (
              <li key={r.n}>
                {r.doi ? <a href={r.doi} target="_blank" rel="noreferrer">{r.paper_title}</a> : r.paper_title}
                {" "}<b>{r.citation}</b>
                <span style={{ fontSize: 11, marginLeft: 6, color: r.source === "eksternal" ? "#0D6CB5" : "#2AA198" }}>
                  {r.source === "eksternal" ? "🌐" : "📚"}
                </span>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}

// ── Bubble jawaban asisten ──────────────────────────────────────────
function BotBubble({ m, onRefs }) {
  const r = m.result;
  if (!r.relevant || !r.best_reference_citation) {
    return <div className="bubble bot"><div className="alert">Tidak ditemukan referensi yang cukup relevan.</div></div>;
  }

  const isExternal = r.source_mode === "eksternal";
  return (
    <div className="bubble bot">
      <div className="bot-label"><IconCheck size={15} /> Recommended Citation
        <span style={{
          marginLeft: 8, fontSize: 11, padding: "2px 8px", borderRadius: 10,
          background: isExternal ? "rgba(13,108,181,.12)" : "rgba(79,185,175,.16)",
          color: isExternal ? "#0D6CB5" : "#2AA198",
        }}>{isExternal ? "🌐 Sumber eksternal" : "📚 Korpus lokal"}</span>
      </div>
      {r.fallback_note && <div className="alert" style={{ marginBottom: 8, fontSize: 12 }}>{r.fallback_note}</div>}
      <p className="citation-text">{withCite(r.citation_text, r.best_reference_citation)}</p>

      <div className="ref-box">
        <div className="ref-title"><IconFile size={14} /> {r.best_reference_paper}
          {r.best_reference_doi && <> · <a href={r.best_reference_doi} target="_blank" rel="noreferrer">DOI</a></>}
        </div>
        <div className="ref-meta">
          <span><b>Author:</b> {r.best_reference_authors || "-"}</span>
          <span><b>Year:</b> {r.best_reference_year || "-"}</span>
        </div>
        {r.best_reference_summary && (
          <p className="ref-summary">{r.best_reference_summary}</p>
        )}
      </div>

      {r.related?.length > 0 && onRefs && (
        <button className="papers-btn" onClick={onRefs}>
          {/* hitung SAMA dgn isi panel: 1 referensi terpilih + n terkait */}
          <IconLibrary size={15} /> Lihat referensi ({(r.best_reference_paper ? 1 : 0) + r.related.length}) →
        </button>
      )}
    </div>
  );
}

import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { useAuth } from "../auth.jsx";
import BookLogo from "../components/BookLogo.jsx";
import {
  IconSearch, IconSparkles, IconQuote, IconFile, IconChart,
  IconCheck, IconArrowRight, IconArrowLeft,
} from "../components/Icons.jsx";
import "./landing.css";

const EASE = [0.22, 0.61, 0.36, 1];
const reveal = {
  initial: { opacity: 0, y: 22 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: false, amount: 0.3 },
  transition: { duration: 0.55, ease: EASE },
};

const SLIDES = ["hero", "tentang", "cara-kerja", "teknologi", "faq", "cta"];
const NAV = [["tentang", "Tentang"], ["cara-kerja", "Cara Kerja"], ["teknologi", "Teknologi"], ["faq", "FAQ"]];

const PIPE = [
  { ic: <IconFile size={18} />,     t: "Paragraf draf",   s: "Teks yang butuh sitasi" },
  { ic: <IconSparkles size={18} />, t: "Query Expansion", s: "HyDE → abstrak hipotetis" },
  { ic: <IconSearch size={18} />,   t: "Retrieval",       s: "SPECTER2 + FAISS" },
  { ic: <IconQuote size={18} />,    t: "Kalimat sitasi",  s: "Disusun dengan CoT" },
];
const STATS = [
  { to: 100,   lbl: "paper IEEE" },
  { to: 11066, lbl: "vektor FAISS" },
  { to: 144,   lbl: "kueri uji" },
  { to: 768,   lbl: "dimensi vektor" },
];
const TABS = [
  { k: "Masalah", sub: "Kenapa sitasi itu sulit", h: "Mencari referensi yang tepat itu melelahkan",
    p: ["Saat menulis, kamu sering tahu apa yang ingin dikatakan tetapi tidak ingat paper mana yang mendukungnya. Pencarian kata kunci biasa hanya cocok pada istilah yang persis sama — padahal paper relevan kerap memakai diksi berbeda.",
        "Akibatnya banyak waktu habis menelusuri daftar pustaka manual, dan klaim penting bisa lolos tanpa sitasi memadai."],
    list: ["Pencarian kata kunci melewatkan kecocokan makna", "Menelusuri referensi manual memakan waktu", "Risiko klaim tanpa dukungan sitasi"] },
  { k: "Pendekatan", sub: "Bagaimana SitasiAI bekerja", h: "Retrieval-Augmented Generation + query expansion",
    p: ["SitasiAI memperluas paragraf draf menjadi abstrak hipotetis (HyDE) agar maksud akademiknya tertangkap lebih kaya, lalu mencari paper paling mirip secara makna dengan embedding SPECTER2 dan indeks FAISS.",
        "Paper terpilih kemudian dinalar bertahap (Chain-of-Thought) untuk menyusun satu kalimat sitasi yang setia pada isi sumber — bukan sekadar menempelkan judul."],
    list: ["Pencocokan berbasis makna, bukan kata kunci", "Kalimat sitasi yang ter-grounding ke sumber", "Sumber referensi selalu ditampilkan"] },
  { k: "Untuk Siapa", sub: "Siapa yang terbantu", h: "Mahasiswa & peneliti yang sedang menulis",
    p: ["Cocok untuk siapa pun yang menyusun tulisan akademik dan ingin menemukan referensi dengan cepat: tugas akhir, paper, atau tinjauan pustaka.",
        "Cukup tempel paragraf yang membutuhkan sitasi — sistem menyarankan paper sumber sekaligus kalimat sitasinya, dan kamu tetap memegang kendali untuk meninjau."],
    list: ["Penulisan tugas akhir & paper", "Penyusunan tinjauan pustaka", "Verifikasi cepat sumber sitasi"] },
];
const STEPS = [
  { ic: <IconSparkles size={22} />, t: "Query Expansion (HyDE)",
    p: "Paragraf draf diperluas menjadi abstrak hipotetis oleh LLM, sehingga maksud akademiknya tertangkap lebih kaya sebelum pencarian.",
    more: "Hypothetical Document Embeddings (Gao et al., 2023): sistem membayangkan 'paper ideal' yang menjawab paragraf lalu mencocokkannya — menjembatani celah kosakata antara draf dan korpus." },
  { ic: <IconSearch size={22} />, t: "Retrieval (SPECTER2 + FAISS)",
    p: "Teks diubah menjadi vektor 768 dimensi oleh SPECTER2, lalu FAISS membandingkannya dengan 11.066 vektor korpus.",
    more: "SPECTER2 dilatih khusus untuk relasi antar-paper ilmiah. Vektor dinormalisasi-L2 dan dicari dengan FAISS IndexFlatIP, sehingga skornya setara dengan cosine similarity." },
  { ic: <IconQuote size={22} />, t: "Generation (CoT)",
    p: "GPT-4o-mini menalar bertahap (chain-of-thought) atas paper terpilih, menilai relevansi, lalu menyusun kalimat sitasi.",
    more: "Penalaran bertahap menilai relevansi tiap kandidat sebelum menulis, lalu menghasilkan satu kalimat yang menjelaskan kontribusi referensi — terikat pada isi paper, tanpa mengarang fakta." },
];
const TECH = [
  ["Frontend", "React 18 + Vite · React Router · Framer Motion", <IconSparkles size={18} />],
  ["Backend", "FastAPI + Uvicorn · JWT + bcrypt", <IconChart size={18} />],
  ["Database", "SQLite (akun, paper, riwayat) · SQLAlchemy", <IconFile size={18} />],
  ["Vector DB", "FAISS — 11.066 embedding SPECTER2", <IconSearch size={18} />],
  ["Generator", "GPT-4o-mini via OpenRouter", <IconQuote size={18} />],
  ["Evaluasi", "RAGAS — Faithfulness & Answer Relevancy", <IconCheck size={18} />],
];
const FAQ = [
  { q: "Apa itu HyDE?", a: "HyDE (Hypothetical Document Embeddings) adalah teknik query expansion: paragraf draf diubah menjadi abstrak hipotetis oleh LLM, lalu abstrak itulah yang dipakai untuk pencarian — menjembatani perbedaan kosakata antara draf dan paper di korpus." },
  { q: "Dari mana sumber papernya?", a: "Korpus terdiri dari 100 paper akademik (IEEE) yang telah diindeks. Sistem hanya menyarankan sitasi dari paper di dalam korpus ini, sehingga sumbernya selalu dapat ditelusuri." },
  { q: "Seberapa akurat sitasinya?", a: "Sistem dievaluasi pada 144 kueri ground truth yang divalidasi manusia, dengan Precision/Recall/Hit untuk ketepatan paper dan Faithfulness/Answer Relevancy (RAGAS) untuk kualitas kalimat. Hasilnya tetap perlu ditinjau sebelum dipakai." },
  { q: "Apakah draf saya aman?", a: "Paragraf yang kamu tempel hanya diproses untuk menghasilkan rekomendasi dan disimpan sebagai riwayat di akunmu sendiri. Sistem tidak membagikannya ke pihak lain." },
];

function CountUp({ to, dur = 1500 }) {
  const ref = useRef(null);
  const [val, setVal] = useState(0);
  useEffect(() => {
    const el = ref.current; if (!el) return;
    let raf, done = false;
    const obs = new IntersectionObserver(([e]) => {
      if (e.isIntersecting && !done) {
        done = true;
        const t0 = performance.now();
        const tick = (t) => {
          const p = Math.min(1, (t - t0) / dur);
          setVal(Math.round(to * (1 - Math.pow(1 - p, 3))));
          if (p < 1) raf = requestAnimationFrame(tick);
        };
        raf = requestAnimationFrame(tick);
      }
    }, { threshold: 0.4 });
    obs.observe(el);
    return () => { obs.disconnect(); cancelAnimationFrame(raf); };
  }, [to, dur]);
  return <span ref={ref}>{val.toLocaleString("id-ID")}</span>;
}

export default function Landing() {
  const { user } = useAuth();
  const nav = useNavigate();
  const deckRef = useRef(null);
  const lock = useRef(false);
  const [active, setActive] = useState(0);
  const [stage, setStage] = useState(0);
  const [tab, setTab] = useState(0);
  const [openStep, setOpenStep] = useState(0);
  const [faq, setFaq] = useState(0);

  const mulai = () => (user ? nav("/app", { state: { fromLogin: true } }) : nav("/login"));

  const goIndex = (i) => {
    const el = deckRef.current; if (!el) return;
    const n = Math.max(0, Math.min(SLIDES.length - 1, i));
    el.scrollTo({ left: n * el.clientWidth, behavior: "smooth" });
  };
  const goId = (id) => goIndex(SLIDES.indexOf(id));

  // Pipeline auto-cycle
  useEffect(() => {
    const t = setInterval(() => setStage((s) => (s + 1) % PIPE.length), 1500);
    return () => clearInterval(t);
  }, []);

  // Wheel vertikal → geser horizontal + panah keyboard + IntersectionObserver
  useEffect(() => {
    const el = deckRef.current; if (!el) return;
    const curIdx = () => Math.round(el.scrollLeft / el.clientWidth);
    const onWheel = (e) => {
      if (Math.abs(e.deltaY) < Math.abs(e.deltaX)) return;
      e.preventDefault();
      if (lock.current) return;
      goIndex(curIdx() + (e.deltaY > 0 ? 1 : -1));
      lock.current = true; setTimeout(() => { lock.current = false; }, 620);
    };
    const onKey = (e) => {
      if (e.key === "ArrowRight" || e.key === "PageDown") goIndex(curIdx() + 1);
      if (e.key === "ArrowLeft" || e.key === "PageUp") goIndex(curIdx() - 1);
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    window.addEventListener("keydown", onKey);
    const obs = new IntersectionObserver(
      (ents) => ents.forEach((en) => { if (en.isIntersecting) { const i = SLIDES.indexOf(en.target.id); if (i >= 0) setActive(i); } }),
      { root: el, threshold: 0.55 }
    );
    SLIDES.forEach((id) => { const s = document.getElementById(id); if (s) obs.observe(s); });
    return () => { el.removeEventListener("wheel", onWheel); window.removeEventListener("keydown", onKey); obs.disconnect(); };
  }, []);

  return (
    <div className="lp">
      {/* ---------- Navbar ---------- */}
      <motion.nav className="lp-nav" initial={{ y: -20, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ duration: 0.5, ease: EASE }}>
        <button className="lp-brand" onClick={() => goIndex(0)}>
          <BookLogo size={30} /><span><b>Sitasi</b>AI</span>
        </button>
        <div className="lp-nav-links">
          {NAV.map(([id, label]) => (
            <a key={id} className={SLIDES[active] === id ? "on" : ""} onClick={() => goId(id)}>{label}</a>
          ))}
        </div>
        <div className="lp-nav-cta">
          <Link to="/login" className="lp-nav-signin">Masuk</Link>
          <Link to="/register" className="lp-btn">Daftar</Link>
        </div>
      </motion.nav>

      {/* ---------- Panah & dots ---------- */}
      <button className="lp-arrow left" onClick={() => goIndex(active - 1)} disabled={active === 0} aria-label="Sebelumnya"><IconArrowLeft size={20} /></button>
      <button className="lp-arrow right" onClick={() => goIndex(active + 1)} disabled={active === SLIDES.length - 1} aria-label="Berikutnya"><IconArrowRight size={20} /></button>
      <div className="lp-dots">
        {SLIDES.map((id, i) => <button key={id} className={`lp-dot ${active === i ? "on" : ""}`} onClick={() => goIndex(i)} aria-label={id} />)}
      </div>

      {/* ---------- Deck ---------- */}
      <div className="lp-deck" ref={deckRef}>

        {/* Slide 1 — Hero */}
        <section id="hero" className="lp-slide">
          <div className="lp-hero-grid">
            <motion.div initial="hidden" animate="show" variants={{ hidden: {}, show: { transition: { staggerChildren: 0.09, delayChildren: 0.1 } } }}>
              <motion.span className="lp-eyebrow" variants={{ hidden: { opacity: 0, y: 12 }, show: { opacity: 1, y: 0 } }}>REKOMENDASI SITASI BERBASIS RAG</motion.span>
              <motion.h1 variants={{ hidden: { opacity: 0, y: 18 }, show: { opacity: 1, y: 0, transition: { duration: 0.6, ease: EASE } } }}>
                Temukan sitasi yang <em>tepat</em> untuk setiap paragraf.
              </motion.h1>
              <motion.p className="lp-hero-sub" variants={{ hidden: { opacity: 0, y: 14 }, show: { opacity: 1, y: 0 } }}>
                SitasiAI memperluas kueri dengan HyDE, mencari paper paling relevan memakai SPECTER2 + FAISS, lalu menyusun kalimat sitasi yang setia pada sumbernya.
              </motion.p>
              <motion.div className="lp-hero-cta" variants={{ hidden: { opacity: 0, y: 14 }, show: { opacity: 1, y: 0 } }}>
                <button className="lp-btn" onClick={mulai}>Mulai Cari Sitasi <IconArrowRight size={17} /></button>
                <button className="lp-btn-ghost" onClick={() => goId("cara-kerja")}>Lihat cara kerja</button>
              </motion.div>
              <motion.div className="lp-hero-stats" variants={{ hidden: { opacity: 0 }, show: { opacity: 1 } }}>
                {STATS.map((s) => (<div key={s.lbl}><b><CountUp to={s.to} /></b><span>{s.lbl}</span></div>))}
              </motion.div>
            </motion.div>

            <motion.div className="lp-pipe" initial={{ opacity: 0, scale: 0.96, y: 16 }} animate={{ opacity: 1, scale: 1, y: 0 }} transition={{ duration: 0.7, ease: EASE, delay: 0.2 }}>
              <div className="lp-pipe-top"><span className="d" /><span className="d" /><span className="d" /><span>alur sistem</span></div>
              {PIPE.map((p, i) => (
                <div key={i} className={`lp-stage ${stage === i ? "on" : ""}`}>
                  <span className="lp-stage-ic">{p.ic}</span>
                  <span className="lp-stage-txt"><b>{p.t}</b><span>{p.s}</span></span>
                  <span className="lp-stage-no">0{i + 1}</span>
                </div>
              ))}
            </motion.div>
          </div>
        </section>

        {/* Slide 2 — Tentang (tabs) */}
        <section id="tentang" className="lp-slide tint">
          <div className="lp-wrap">
            <motion.div className="lp-head" {...reveal}>
              <span className="lp-eyebrow">TENTANG SITASIAI</span>
              <h2>Asisten sitasi untuk penulisan akademik</h2>
              <p>Klik tiap aspek untuk menelusuri masalah yang dipecahkan, pendekatan teknisnya, dan untuk siapa SitasiAI dibuat.</p>
            </motion.div>
            <div className="lp-about-grid">
              <motion.div className="lp-tabs" {...reveal}>
                {TABS.map((t, i) => (
                  <button key={t.k} className={`lp-tab ${tab === i ? "on" : ""}`} onClick={() => setTab(i)}><b>{t.k}</b><span>{t.sub}</span></button>
                ))}
              </motion.div>
              <motion.div className="lp-tab-panel" {...reveal}>
                <AnimatePresence mode="wait">
                  <motion.div key={tab} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.3, ease: EASE }}>
                    <h3>{TABS[tab].h}</h3>
                    {TABS[tab].p.map((para, j) => <p key={j}>{para}</p>)}
                    <ul className="lp-tab-list">{TABS[tab].list.map((li) => (<li key={li}><span className="ck"><IconCheck size={13} /></span>{li}</li>))}</ul>
                  </motion.div>
                </AnimatePresence>
              </motion.div>
            </div>
          </div>
        </section>

        {/* Slide 3 — Cara Kerja */}
        <section id="cara-kerja" className="lp-slide">
          <div className="lp-wrap">
            <motion.div className="lp-head center" {...reveal}>
              <span className="lp-eyebrow center">ALUR SISTEM</span>
              <h2>Tiga tahap, dari draf ke sitasi</h2>
              <p>Klik tiap kartu untuk melihat detail teknisnya.</p>
            </motion.div>
            <motion.div className="lp-flow" {...reveal}>
              <span className="lp-flow-chip in">Paragraf draf</span><span className="lp-flow-arr">→</span>
              <span className="lp-flow-chip">HyDE</span><span className="lp-flow-arr">→</span>
              <span className="lp-flow-chip">Retrieval</span><span className="lp-flow-arr">→</span>
              <span className="lp-flow-chip">Generation</span><span className="lp-flow-arr">→</span>
              <span className="lp-flow-chip out">Kalimat sitasi</span>
            </motion.div>
            <div className="lp-steps">
              {STEPS.map((s, i) => (
                <motion.div key={i} className={`lp-step ${openStep === i ? "on" : ""}`} {...reveal} onClick={() => setOpenStep(openStep === i ? -1 : i)}>
                  <div className="lp-step-no">TAHAP 0{i + 1}</div>
                  <div className="lp-step-ic">{s.ic}</div>
                  <h3>{s.t}</h3>
                  <p>{s.p}</p>
                  <AnimatePresence initial={false}>
                    {openStep === i && (
                      <motion.div className="lp-step-more" initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.32, ease: EASE }}>
                        <p>{s.more}</p>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </motion.div>
              ))}
            </div>
          </div>
        </section>

        {/* Slide 4 — Teknologi */}
        <section id="teknologi" className="lp-slide tint">
          <div className="lp-wrap">
            <motion.div className="lp-head" {...reveal}>
              <span className="lp-eyebrow">STACK TEKNOLOGI</span>
              <h2>Dibangun dengan perkakas modern</h2>
            </motion.div>
            <div className="lp-tech">
              {TECH.map(([k, v, ic]) => (
                <motion.div className="lp-tech-card" key={k} {...reveal}>
                  <span className="lp-tech-ic">{ic}</span>
                  <div><div className="lp-tech-k">{k}</div><div className="lp-tech-v">{v}</div></div>
                </motion.div>
              ))}
            </div>
          </div>
        </section>

        {/* Slide 5 — FAQ */}
        <section id="faq" className="lp-slide">
          <div className="lp-wrap">
            <motion.div className="lp-head center" {...reveal}>
              <span className="lp-eyebrow center">PERTANYAAN UMUM</span>
              <h2>Hal yang sering ditanyakan</h2>
            </motion.div>
            <div className="lp-faq">
              {FAQ.map((f, i) => (
                <motion.div key={i} className={`lp-faq-item ${faq === i ? "on" : ""}`} {...reveal}>
                  <button className="lp-faq-q" onClick={() => setFaq(faq === i ? -1 : i)} aria-expanded={faq === i}>{f.q}<span className="pm"><IconPlusMini /></span></button>
                  <AnimatePresence initial={false}>
                    {faq === i && (
                      <motion.div className="lp-faq-a" initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.3, ease: EASE }}>
                        <p>{f.a}</p>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </motion.div>
              ))}
            </div>
          </div>
        </section>

        {/* Slide 6 — CTA */}
        <section id="cta" className="lp-slide dark lp-cta">
          <motion.div className="lp-wrap" {...reveal}>
            <span className="lp-eyebrow center" style={{ color: "#9FD3CB" }}>MULAI SEKARANG</span>
            <h2 style={{ marginTop: 14 }}>Siap menyitasi lebih cepat?</h2>
            <p>Buat akun dan mulai cari sitasi untuk draf akademikmu — gratis.</p>
            <div className="lp-cta-row">
              <button className="lp-btn" onClick={mulai}>Mulai Cari Sitasi <IconArrowRight size={17} /></button>
              <Link to="/login" className="lp-link">Sudah punya akun? Masuk <IconArrowRight size={16} /></Link>
            </div>
          </motion.div>
          <footer className="lp-deck-footer"><span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}><BookLogo size={20} /> © 2026 SitasiAI · Tugas Akhir Teknik Informatika ITS</span></footer>
        </section>

      </div>
    </div>
  );
}

function IconPlusMini() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
      <path d="M12 5v14M5 12h14" />
    </svg>
  );
}

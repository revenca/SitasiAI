import { useEffect, useState } from "react";
import api from "../api";

// Library — langsung menampilkan isi basis data vektor (163k paper, Postgres/pgvector);
// fallback otomatis ke korpus 100-paper bila basis data belum tersedia.
export default function Papers() {
  const [papers, setPapers] = useState([]);
  const [total, setTotal] = useState(0);
  const [source, setSource] = useState("");
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const t = setTimeout(async () => {
      setLoading(true);
      try {
        const { data } = await api.get("/papers", { params: { q, limit: 50 } });
        setPapers(data.papers || []);
        setTotal(data.total || 0);
        setSource(data.source || "");
      } finally {
        setLoading(false);
      }
    }, 300);                                  // debounce ketikan
    return () => clearTimeout(t);
  }, [q]);

  return (
    <div className="papers-page">
      <h1>Library</h1>
      <p className="muted">
        {total.toLocaleString("id-ID")} paper di basis data
        {source === "korpus" ? " (korpus lokal)" : ""} — menampilkan {papers.length}
      </p>

      <div className="papers-filter">
        <input placeholder="Cari judul paper…" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>

      {loading && <p className="muted">Mencari…</p>}
      <div className="papers-grid">
        {papers.map((p, i) => (
          <div className="paper-card stagger-item" style={{ animationDelay: `${Math.min(i, 12) * 0.03}s` }} key={`${p.title}-${i}`}>
            <div className="paper-cat">{p.year || "—"}{p.cited_by ? ` · dikutip ${p.cited_by.toLocaleString("id-ID")}×` : ""}</div>
            <div className="paper-title">
              {p.doi ? <a href={p.doi} target="_blank" rel="noreferrer">{p.title}</a> : p.title}
            </div>
            <div className="paper-meta">{p.authors || ""}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

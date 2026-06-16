import { useEffect, useState } from "react";
import api from "../api";

export default function Papers() {
  const [papers, setPapers] = useState([]);
  const [cats, setCats] = useState([]);
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("");

  const load = async () => {
    const { data } = await api.get("/papers", { params: { q, category: cat } });
    setPapers(data);
  };

  useEffect(() => { api.get("/papers/categories").then(({ data }) => setCats(data)); }, []);
  useEffect(() => { load(); }, [q, cat]);

  return (
    <div className="papers-page">
      <h1>Daftar Paper Korpus</h1>
      <p className="muted">{papers.length} paper diindeks dalam sistem</p>

      <div className="papers-filter">
        <input placeholder="Cari judul paper..." value={q} onChange={(e) => setQ(e.target.value)} />
        <select value={cat} onChange={(e) => setCat(e.target.value)}>
          <option value="">Semua kategori</option>
          {cats.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>

      <div className="papers-grid">
        {papers.map((p, i) => (
          <div className="paper-card stagger-item" style={{ animationDelay: `${Math.min(i, 12) * 0.04}s` }} key={p.id}>
            <div className="paper-cat">{p.category}</div>
            <div className="paper-title">{p.title}</div>
            <div className="paper-meta">{p.n_chunks} chunk</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// Buku-buku melayang menyeberangi hero (kiri → kanan), beragam ukuran & kecepatan.
function Book({ s = 1 }) {
  return (
    <svg width={40 * s} height={40 * s} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M12 7.5c-1.5-1-3.2-1.5-5.2-1.5-.7 0-1.3.06-1.8.18v10.9c.5-.12 1.1-.18 1.8-.18 2 0 3.7.5 5.2 1.5 1.5-1 3.2-1.5 5.2-1.5.7 0 1.3.06 1.8.18V6.18C18.5 6.06 17.9 6 17.2 6c-2 0-3.7.5-5.2 1.5Z"
        fill="currentColor" fillOpacity="0.9"
      />
      <path d="M12 7.5v10.9" stroke="#1e3a8a" strokeOpacity="0.5" strokeWidth="1" />
    </svg>
  );
}

// top% , scale , durasi(s) , delay(s-negatif biar langsung tersebar)
const ROWS = [
  { top: 8,  s: 0.7, dur: 26, delay: -2 },
  { top: 16, s: 1.1, dur: 34, delay: -14 },
  { top: 24, s: 0.6, dur: 22, delay: -8 },
  { top: 34, s: 0.9, dur: 30, delay: -20 },
  { top: 44, s: 1.3, dur: 40, delay: -5 },
  { top: 55, s: 0.7, dur: 24, delay: -17 },
  { top: 63, s: 1.0, dur: 32, delay: -11 },
  { top: 72, s: 0.6, dur: 21, delay: -3 },
  { top: 80, s: 1.2, dur: 38, delay: -25 },
  { top: 88, s: 0.8, dur: 28, delay: -9 },
  { top: 12, s: 0.9, dur: 36, delay: -30 },
  { top: 50, s: 0.7, dur: 23, delay: -13 },
];

export default function FloatingBooks() {
  return (
    <div className="books-layer" aria-hidden="true">
      {ROWS.map((r, i) => (
        <span
          key={i}
          className="float-book"
          style={{
            top: `${r.top}%`,
            animationDuration: `${r.dur}s`,
            animationDelay: `${r.delay}s`,
            opacity: 0.08 + r.s * 0.08,
          }}
        >
          <span className="float-book-bob" style={{ animationDelay: `${r.delay}s` }}>
            <Book s={r.s} />
          </span>
        </span>
      ))}
    </div>
  );
}

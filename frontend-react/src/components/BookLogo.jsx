/**
 * Logo SitasiAI — buku terbuka + topi toga, gaya flat biru ITS.
 *
 * Catatan desain (penting, jangan diubah tanpa alasan):
 *  · Seluruh bentuk memakai `currentColor` → logo bisa diwarnai lewat prop `color`
 *    (putih di sidebar gelap, biru di latar terang) tanpa perlu aset terpisah.
 *  · Garis teks pada halaman dibuat sebagai LUBANG (fillRule="evenodd"), BUKAN garis putih.
 *    Kalau memakai garis putih, saat logo diwarnai putih di sidebar gelap garisnya melebur
 *    dan logo jadi gumpalan padat. Dengan lubang, latar apa pun menembus → selalu terbaca.
 *  · Ketebalan lubang sengaja tebal agar tetap jelas saat dikecilkan ke 16px (avatar).
 *
 * Prop `rounded` masih diterima demi kompatibilitas pemanggil lama (tidak dipakai:
 * logo baru tanpa badge kotak).
 */
export default function BookLogo({ size = 32, color, rounded }) {   // eslint-disable-line no-unused-vars
  return (
    <svg
      width={size} height={size} viewBox="0 0 48 48" fill="none"
      style={{ color: color || "var(--blue, #12558A)", display: "block" }}
      role="img" aria-label="SitasiAI"
    >
      <g fill="currentColor">
        {/* halaman kiri (nada sedikit lebih muda) — garis teks = lubang evenodd */}
        <path
          fillOpacity="0.78" fillRule="evenodd"
          d="M23.3 24.4C17.2 20.2 11.2 18.2 7 18.4C5.6 18.47 4.6 19.6 4.6 21L4.6 34.4C4.6 35.5 5.4 36.4 6.5 36.5C11.6 36.9 17.6 38.8 23.3 42.2ZM21.8 26.2C17 22.8 12.4 21.1 8.6 21.2L8.6 23.2C12.4 23.1 17 24.8 21.8 28.2ZM21.8 31.2C17 27.8 12.4 26.1 8.6 26.2L8.6 28.2C12.4 28.1 17 29.8 21.8 33.2ZM21.8 36.2C17 32.8 12.4 31.1 8.6 31.2L8.6 33.2C12.4 33.1 17 34.8 21.8 38.2Z"
        />
        {/* halaman kanan */}
        <path
          fillRule="evenodd"
          d="M24.7 24.4C30.8 20.2 36.8 18.2 41 18.4C42.4 18.47 43.4 19.6 43.4 21L43.4 34.4C43.4 35.5 42.6 36.4 41.5 36.5C36.4 36.9 30.4 38.8 24.7 42.2ZM26.2 26.2C31 22.8 35.6 21.1 39.4 21.2L39.4 23.2C35.6 23.1 31 24.8 26.2 28.2ZM26.2 31.2C31 27.8 35.6 26.1 39.4 26.2L39.4 28.2C35.6 28.1 31 29.8 26.2 33.2ZM26.2 36.2C31 32.8 35.6 31.1 39.4 31.2L39.4 33.2C35.6 33.1 31 34.8 26.2 38.2Z"
        />
        {/* papan topi toga */}
        <path d="M24 4.6L35.2 9.3L24 13.2L12.8 9.3Z" />
        {/* kepala topi */}
        <path d="M20.4 10.2L27.6 10.2L27.1 19.4C27.1 20.06 26.56 20.6 25.9 20.6L22.1 20.6C21.44 20.6 20.9 20.06 20.9 19.4Z" />
        {/* tali tassel + bandul */}
        <path fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round"
              d="M34.6 9.8C36.7 10.6 37.6 11.8 37.6 13.6" />
        <circle cx="37.6" cy="15.4" r="1.8" />
      </g>
    </svg>
  );
}

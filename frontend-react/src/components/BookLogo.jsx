// Logo SitasiAI: buku terbuka + tanda kutip sitasi, badge bergradien teal.
let _id = 0;

export default function BookLogo({ size = 32, rounded = 9 }) {
  const gid = `sg-${_id++}`;
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" fill="none" aria-hidden="true">
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="48" y2="48" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#14635B" />
          <stop offset="1" stopColor="#093833" />
        </linearGradient>
      </defs>
      <rect width="48" height="48" rx={rounded} fill={`url(#${gid})`} />
      {/* buku terbuka */}
      <path
        d="M24 15c-2.6-1.6-5.5-2.4-9-2.4-1.2 0-2.2.1-3 .3v18.7c.9-.2 1.9-.3 3-.3 3.5 0 6.4.8 9 2.4 2.6-1.6 5.5-2.4 9-2.4 1.1 0 2.1.1 3 .3V12.9c-.8-.2-1.8-.3-3-.3-3.5 0-6.4.8-9 2.4Z"
        fill="#fff" fillOpacity="0.96"
      />
      <path d="M24 15v18.7" stroke="#093833" strokeWidth="1.6" strokeLinecap="round" />
      {/* tanda kutip sitasi (lime) */}
      <path
        d="M19.5 22.2c0 1.6-1.2 2.8-2.7 2.9m2.7-2.9c0-1.2-.9-2.1-2.1-2.1s-2.1.9-2.1 2.1.9 2.1 2.1 2.1M30.6 22.2c0 1.6-1.2 2.8-2.7 2.9m2.7-2.9c0-1.2-.9-2.1-2.1-2.1s-2.1.9-2.1 2.1.9 2.1 2.1 2.1"
        stroke="#0C4A45" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"
      />
    </svg>
  );
}

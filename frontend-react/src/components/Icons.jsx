// Ikon garis (stroke) gaya Lucide — konsisten, tanpa emoji.
const base = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round",
  strokeLinejoin: "round",
};

function Svg({ size = 20, children, ...rest }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...base} {...rest} aria-hidden="true">
      {children}
    </svg>
  );
}

export const IconSearch = (p) => (
  <Svg {...p}><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></Svg>
);

export const IconSparkles = (p) => (
  <Svg {...p}>
    <path d="M12 3v3M12 18v3M3 12h3M18 12h3" />
    <path d="M12 7.5 13.6 11l3.4 1-3.4 1L12 16.5 10.4 13 7 12l3.4-1L12 7.5Z" />
  </Svg>
);

export const IconLibrary = (p) => (
  <Svg {...p}>
    <path d="M4 4v16M8 4v16" />
    <path d="m12 5 3.6-.6 2.8 15.8-3.6.6z" />
    <path d="M4 20h6" />
  </Svg>
);

export const IconFile = (p) => (
  <Svg {...p}>
    <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
    <path d="M14 3v5h5" /><path d="M9 13h6M9 17h6" />
  </Svg>
);

export const IconChat = (p) => (
  <Svg {...p}>
    <path d="M21 12a8 8 0 0 1-11.4 7.2L4 20l.8-5.6A8 8 0 1 1 21 12Z" />
    <path d="M9 11h6M9 14h4" />
  </Svg>
);

export const IconChart = (p) => (
  <Svg {...p}>
    <path d="M4 4v16h16" /><path d="M8 16v-4M12 16V8M16 16v-6" />
  </Svg>
);

export const IconArrowRight = (p) => (
  <Svg {...p}><path d="M5 12h14M13 6l6 6-6 6" /></Svg>
);

export const IconArrowLeft = (p) => (
  <Svg {...p}><path d="M19 12H5M11 6l-6 6 6 6" /></Svg>
);

export const IconCheck = (p) => (
  <Svg {...p}><circle cx="12" cy="12" r="9" /><path d="m8.5 12 2.5 2.5 4.5-5" /></Svg>
);

export const IconQuote = (p) => (
  <Svg {...p}>
    <path d="M7 7H4v5h3a3 3 0 0 1-3 3M17 7h-3v5h3a3 3 0 0 1-3 3" />
  </Svg>
);

export const IconPlane = (p) => (
  <Svg {...p}><path d="M22 2 11 13" /><path d="M22 2 15 22l-4-9-9-4 20-7Z" /></Svg>
);

export const IconPlus = (p) => (
  <Svg {...p}><path d="M12 5v14M5 12h14" /></Svg>
);

export const IconClose = (p) => (
  <Svg {...p}><path d="M6 6l12 12M18 6 6 18" /></Svg>
);

export const IconHelp = (p) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.8.4-1 .9-1 1.7M12 17h.01" />
  </Svg>
);

export const IconEdit = (p) => (
  <Svg {...p}><path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" /></Svg>
);

export const IconTrash = (p) => (
  <Svg {...p}><path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14M10 11v6M14 11v6" /></Svg>
);

export const IconChatBubble = (p) => (
  <Svg {...p}><path d="M21 11.5a8.5 8.5 0 0 1-12.5 7.5L3 21l2-5.5A8.5 8.5 0 1 1 21 11.5Z" /></Svg>
);

export const IconMenu = (p) => (
  <Svg {...p}><path d="M4 6h16M4 12h16M4 18h16" /></Svg>
);

import { createContext, useContext, useEffect, useRef, useState } from "react";

const ChatCtx = createContext(null);

// Mode tools (tanpa login): riwayat chat disimpan per-browser (localStorage), satu ruang "anon".
const keyFor = () => "sitasi_chats_anon";
const uid = () => `c_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 7)}`;
const mkSession = () => ({ id: uid(), title: "Chat baru", messages: [], updatedAt: Date.now() });

function load(key) {
  try { const a = JSON.parse(localStorage.getItem(key)); return Array.isArray(a) ? a : []; }
  catch { return []; }
}

export function ChatProvider({ children }) {
  const key = keyFor();

  const [sessions, setSessions] = useState(() => {
    const s = load(key); return s.length ? s : [mkSession()];
  });
  const [activeId, setActiveId] = useState(() => sessions[0]?.id ?? null);
  const skipPersist = useRef(true);

  // Ganti akun → muat riwayat akun tsb (jangan tertimpa)
  useEffect(() => {
    const s = load(key);
    skipPersist.current = true;
    const list = s.length ? s : [mkSession()];
    setSessions(list);
    setActiveId(list[0].id);
  }, [key]);

  // Persist (lewati commit yang dipicu pemuatan)
  useEffect(() => {
    if (skipPersist.current) { skipPersist.current = false; return; }
    localStorage.setItem(key, JSON.stringify(sessions.slice(0, 50)));
  }, [sessions]); // eslint-disable-line react-hooks/exhaustive-deps

  // Jaga selalu ada ≥1 sesi & activeId valid
  useEffect(() => {
    if (sessions.length === 0) { const ns = [mkSession()]; setSessions(ns); setActiveId(ns[0].id); }
    else if (!sessions.some((s) => s.id === activeId)) setActiveId(sessions[0].id);
  }, [sessions, activeId]);

  const active = sessions.find((s) => s.id === activeId) || null;

  const newChat = () => {
    const s = mkSession();
    setSessions((prev) => [s, ...prev]);
    setActiveId(s.id);
    return s.id;
  };
  const openChat = (id) => setActiveId(id);
  const renameChat = (id, title) =>
    setSessions((prev) => prev.map((x) => (x.id === id ? { ...x, title: (title || "").trim() || "Tanpa judul" } : x)));
  const deleteChat = (id) => setSessions((prev) => prev.filter((x) => x.id !== id));

  // Tulis pesan ke sesi aktif + auto-judul dari pesan user pertama
  const setActiveMessages = (updater) =>
    setSessions((prev) => prev.map((x) => {
      if (x.id !== activeId) return x;
      const msgs = typeof updater === "function" ? updater(x.messages) : updater;
      let title = x.title;
      if (title === "Chat baru" || !title) {
        const fu = msgs.find((m) => m.role === "user");
        if (fu?.text) title = fu.text.slice(0, 46);
      }
      return { ...x, messages: msgs, title, updatedAt: Date.now() };
    }));

  return (
    <ChatCtx.Provider value={{ sessions, active, activeId, newChat, openChat, renameChat, deleteChat, setActiveMessages }}>
      {children}
    </ChatCtx.Provider>
  );
}

export const useChat = () => useContext(ChatCtx);

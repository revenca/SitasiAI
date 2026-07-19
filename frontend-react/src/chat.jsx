import { createContext, useContext, useEffect, useRef, useState } from "react";
import api from "./api";

const ChatCtx = createContext(null);

// Tanpa login: riwayat chat disimpan per-browser (localStorage) DAN di-mirror ke server
// per-ID anonim (UUID) → persist walau cache lokal terhapus, bisa dipulihkan via kode.
const keyFor = () => "sitasi_chats_anon";
const uid = () => `c_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 7)}`;
const mkSession = () => ({ id: uid(), title: "Chat baru", messages: [], updatedAt: Date.now() });

// ID anonim stabil per-browser (dipakai sebagai kunci history di server)
function getAnonId() {
  let id = localStorage.getItem("sitasi_anon_id");
  if (!id || !/^[A-Za-z0-9_-]{8,64}$/.test(id)) {
    id = (window.crypto?.randomUUID?.() ||
          `a_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 12)}`);
    localStorage.setItem("sitasi_anon_id", id);
  }
  return id;
}

function load(key) {
  try { const a = JSON.parse(localStorage.getItem(key)); return Array.isArray(a) ? a : []; }
  catch { return []; }
}

export function ChatProvider({ children }) {
  const key = keyFor();
  const anonId = useRef(getAnonId());
  const [sessions, setSessions] = useState(() => {
    const s = load(key); return s.length ? s : [mkSession()];
  });
  const [activeId, setActiveId] = useState(() => sessions[0]?.id ?? null);
  const skipPersist = useRef(true);
  const syncTimer = useRef(null);

  // Saat mount: tarik dari SERVER. Bila lokal kosong tapi server punya → pulihkan otomatis.
  useEffect(() => {
    let alive = true;
    api.get(`/anon-history/${anonId.current}`).then(({ data }) => {
      if (!alive || !Array.isArray(data?.data) || data.data.length === 0) return;
      if (load(key).length === 0) {                  // lokal kosong → adopsi server
        skipPersist.current = true;
        setSessions(data.data);
        setActiveId(data.data[0]?.id ?? null);
      }
    }).catch(() => {});
    return () => { alive = false; };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Persist lokal + sync ke SERVER (debounced 1.2s biar tak spam tiap ketikan)
  useEffect(() => {
    if (skipPersist.current) { skipPersist.current = false; return; }
    const slice = sessions.slice(0, 50);
    localStorage.setItem(key, JSON.stringify(slice));
    clearTimeout(syncTimer.current);
    syncTimer.current = setTimeout(() => {
      api.put(`/anon-history/${anonId.current}`, { data: slice }).catch(() => {});
    }, 1200);
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

  // Pulihkan history dari kode (ID) lain — mis. di browser baru / setelah cache terhapus
  const restoreFrom = async (code) => {
    const id = (code || "").trim();
    if (!/^[A-Za-z0-9_-]{8,64}$/.test(id)) return { ok: false, reason: "Kode tidak valid" };
    try {
      const { data } = await api.get(`/anon-history/${id}`);
      if (Array.isArray(data?.data) && data.data.length) {
        localStorage.setItem("sitasi_anon_id", id);
        anonId.current = id;
        skipPersist.current = true;
        setSessions(data.data);
        setActiveId(data.data[0]?.id ?? null);
        return { ok: true, count: data.data.length };
      }
      return { ok: false, reason: "Tidak ada history untuk kode ini" };
    } catch { return { ok: false, reason: "Gagal menghubungi server" }; }
  };

  return (
    <ChatCtx.Provider value={{
      sessions, active, activeId, newChat, openChat, renameChat, deleteChat, setActiveMessages,
      anonId: anonId.current, restoreFrom,
    }}>
      {children}
    </ChatCtx.Provider>
  );
}

export const useChat = () => useContext(ChatCtx);

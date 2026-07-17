import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { useChat } from "../chat.jsx";
import BookLogo from "./BookLogo.jsx";
import { IconSearch, IconFile, IconHelp, IconPlus, IconEdit, IconTrash, IconChatBubble } from "./Icons.jsx";

const EASE = [0.22, 0.61, 0.36, 1];

export default function Layout({ children }) {
  const { sessions, activeId, newChat, openChat, renameChat, deleteChat } = useChat();
  const loc = useLocation();
  const nav = useNavigate();
  const [editingId, setEditingId] = useState(null);
  const [editText, setEditText] = useState("");

  const goChat = (id) => { openChat(id); if (loc.pathname !== "/") nav("/"); };
  const startRename = (e, s) => { e.stopPropagation(); setEditingId(s.id); setEditText(s.title); };
  const commitRename = () => { if (editingId) renameChat(editingId, editText); setEditingId(null); };

  const NavItem = ({ to, icon, label }) => (
    <motion.div whileTap={{ scale: 0.97 }}>
      <Link to={to} className={`nav-item ${loc.pathname === to ? "active" : ""}`}>
        <span className="nav-icon">{icon}</span> {label}
      </Link>
    </motion.div>
  );
  const ICON = 18;

  return (
    <div className="app-shell">
      {/* Sidebar */}
      <aside className="sidebar">
        <Link to="/" className="brand"><BookLogo size={24} color="#fff" /> <span><b>Sitasi</b>AI</span></Link>

        <div className="nav-section">WORKFLOWS</div>
        <NavItem to="/" icon={<IconSearch size={ICON} />} label="Pembuatan Sitasi" />
        <NavItem to="/papers" icon={<IconFile size={ICON} />} label="Library" />

        <div className="nav-section">RIWAYAT CHAT</div>
        <button className="newchat-btn" onClick={() => { newChat(); if (loc.pathname !== "/") nav("/"); }}>
          <IconPlus size={15} /> Chat baru
        </button>
        <div className="chat-list">
          {sessions.map((s) => (
            <div key={s.id} className={`chat-list-item ${s.id === activeId ? "active" : ""}`} onClick={() => goChat(s.id)}>
              <span className="cli-ic"><IconChatBubble size={14} /></span>
              {editingId === s.id ? (
                <input className="cli-input" value={editText} autoFocus
                  onClick={(e) => e.stopPropagation()}
                  onChange={(e) => setEditText(e.target.value)}
                  onBlur={commitRename}
                  onKeyDown={(e) => { if (e.key === "Enter") commitRename(); if (e.key === "Escape") setEditingId(null); }} />
              ) : (
                <span className="cli-title">{s.title}</span>
              )}
              <span className="cli-actions">
                <button title="Ubah nama" onClick={(e) => startRename(e, s)}><IconEdit size={13} /></button>
                <button title="Hapus" onClick={(e) => { e.stopPropagation(); deleteChat(s.id); }}><IconTrash size={13} /></button>
              </span>
            </div>
          ))}
        </div>

        <div className="sidebar-footer">
          <div className="user-chip">
            <div className="avatar"><BookLogo size={16} color="#fff" /></div>
            <div>
              <div className="user-name">SitasiAI</div>
              <div className="user-email">Tools Sitasi — ITS</div>
            </div>
          </div>
        </div>
      </aside>

      {/* Main */}
      <main className="main">
        <div className="topbar">
          <div />
          <div className="topbar-right">
            <span className="help"><IconHelp size={16} /> Help</span>
          </div>
        </div>
        <div className="content">
          <AnimatePresence mode="wait">
            <motion.div
              key={loc.pathname}
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.32, ease: EASE }}
            >
              {children}
            </motion.div>
          </AnimatePresence>
        </div>
      </main>
    </div>
  );
}

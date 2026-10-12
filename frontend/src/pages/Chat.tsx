import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, fmt, getUser } from "../api";
import { AuthImg, Lightbox } from "../components";

export default function Chat() {
  const u = getUser();
  const isAgent = ["facility_manager", "super_admin"].includes(u.role);
  const [threads, setThreads] = useState<any[]>([]);
  const [active, setActive] = useState<number | null>(null);
  const [msgs, setMsgs] = useState<any[]>([]);
  const [mode, setMode] = useState("bot");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [zoom, setZoom] = useState("");
  const lastId = useRef(0);
  const endRef = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const loadThreads = () => api("/chat/threads").then(setThreads).catch(() => {});
  useEffect(() => { loadThreads(); const i = setInterval(loadThreads, 4000); return () => clearInterval(i); }, []);

  const merge = (incoming: any[]) => setMsgs(prev => {
    const ids = new Set(prev.map(x => x.id));
    const add = incoming.filter(x => !ids.has(x.id));
    return add.length ? [...prev, ...add].sort((a, b) => a.id - b.id) : prev;
  });
  useEffect(() => { if (msgs.length) lastId.current = msgs[msgs.length - 1].id; endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs]);

  useEffect(() => {
    setMsgs([]); lastId.current = 0; setErr("");
    if (active == null) return;
    let dead = false;
    const poll = async () => {
      try { const r = await api(`/chat/threads/${active}/messages?after=${lastId.current}`); if (dead) return; setMode(r.mode); if (r.messages.length) merge(r.messages); } catch { }
    };
    poll(); const i = setInterval(poll, 2000);
    return () => { dead = true; clearInterval(i); };
  }, [active]);

  const th = threads.find(t => t.id === active);
  const last = msgs[msgs.length - 1];
  const quick = last && last.sender_type === "bot" && mode === "bot" && last.options?.length ? last.options : [];

  async function run(fn: () => Promise<any>) {
    setBusy(true); setErr("");
    try { const r = await fn(); if (r?.messages) { merge(r.messages); setMode(r.mode); } loadThreads(); } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  }
  const send = (choice?: string) => {
    const body = choice ? { text: choice, choice } : { text };
    if (!(body.text || "").trim()) return;
    run(async () => { const r = await api(`/chat/threads/${active}/messages`, { method: "POST", body }); setText(""); return r; });
  };
  const newChat = () => run(async () => { const t = await api("/chat/threads", { method: "POST" }); setActive(t.id); return null; });
  const upload = (e: any) => {
    const files: File[] = Array.from(e.target.files || []);
    run(async () => { let r: any = null; for (const f of files) { const fd = new FormData(); fd.append("file", f); r = await api(`/chat/threads/${active}/upload`, { method: "POST", body: fd }); merge(r.messages); } return r; });
    e.target.value = "";
  };
  const action = (path: string) => run(async () => { await api(`/chat/threads/${active}/${path}`, { method: "POST" }); return null; });

  return (
    <div className="chat">
      <aside className="chat-list card">
        <button onClick={newChat} disabled={busy}>＋ New chat</button>
        <p className="muted">{isAgent ? "Inbox — customer chats at your sites" : "Your conversations"}</p>
        {threads.length === 0 && <p className="muted">No chats yet. Start one to report an issue or reach an agent.</p>}
        {threads.map(t => (
          <div key={t.id} className={`thread ${t.id === active ? "sel" : ""}`} onClick={() => setActive(t.id)}>
            <div><b>{t.own ? t.title : `${t.requester}`}</b> {t.unread > 0 && <span className="dot">{t.unread}</span>}</div>
            <div className="muted small">{t.mode === "agent" ? "🎧 With agent" : t.mode === "closed" ? "✔ Closed" : "🤖 Assistant"}{!t.own && t.title !== "New chat" ? ` · ${t.title}` : ""}</div>
            <div className="muted small ellipsis">{t.preview}</div>
          </div>))}
      </aside>

      <section className="chat-main card">
        {active == null ? <p className="muted">Select a chat or start a new one. The assistant can raise a ticket, check a status, or connect you to a live helpdesk agent.</p> : <>
          <div className="chat-head">
            <div><b>{th?.own ? "FM Helpdesk" : th?.requester}</b> <span className="badge">{mode === "agent" ? "Live agent" : mode === "closed" ? "Closed" : "Assistant"}</span>
              {th?.ticket && <> · <Link to="/tickets">{th.ticket}</Link></>}</div>
            <div>
              {th?.own && mode === "bot" && <button className="secondary" onClick={() => action("handoff")}>🎧 Talk to an agent</button>}
              {th?.own && mode === "agent" && <button className="secondary" onClick={() => action("bot")}>🤖 Back to assistant</button>}
              {isAgent && mode !== "closed" && <button className="secondary" onClick={() => action("close")}>Close chat</button>}
            </div>
          </div>
          <div className="chat-body">
            {msgs.map(m => (
              <div key={m.id} className={`bubble ${m.sender_type}`}>
                {m.sender_type !== "system" && <div className="who">{m.sender_type === "bot" ? "🤖 " : m.sender_type === "agent" ? "🎧 " : ""}{m.sender}</div>}
                {m.file && (m.file.content_type.startsWith("image/") ? <AuthImg path={`/api/chat/files/${m.file.id}`} className="chat-img" onOpen={setZoom} /> : <span>📎 {m.file.filename}</span>)}
                {m.text && <div className="txt">{m.text}</div>}
                {m.meta?.number && <div className="ticket-card">
                  🎫 <Link to={`/tickets/${m.meta.ticket_id}`}>{m.meta.number}</Link>
                  {m.meta.wa_link && <a className="wa" target="_blank" rel="noreferrer" href={`${m.meta.wa_link}?text=${encodeURIComponent(`Hello ${m.meta.rep_name}, this is about ticket ${m.meta.number}.`)}`}>💬 WhatsApp {m.meta.whatsapp}</a>}
                </div>}
                <div className="time">{fmt(m.created_at)}</div>
              </div>))}
            <div ref={endRef} />
          </div>
          {quick.length > 0 && <div className="quick">{quick.map((o: string) => <button key={o} className="chip" disabled={busy} onClick={() => send(o)}>{o}</button>)}</div>}
          {err && <p className="error">{err}</p>}
          {mode === "closed" ? <p className="muted">This chat is closed. Start a new chat.</p> :
            <div className="composer">
              <button className="secondary" title="Attach photo" onClick={() => fileRef.current?.click()}>📎</button>
              <input ref={fileRef} type="file" accept="image/*,.pdf" capture={undefined} multiple hidden onChange={upload} />
              <input value={text} placeholder={mode === "agent" ? (th?.own ? "Message the helpdesk agent…" : "Reply to customer…") : "Type your message…"} onChange={e => setText(e.target.value)} onKeyDown={e => e.key === "Enter" && send()} />
              <button disabled={busy || !text.trim()} onClick={() => send()}>Send</button>
            </div>}
        </>}
      </section>
      {zoom && <Lightbox src={zoom} onClose={() => setZoom("")} />}
    </div>
  );
}

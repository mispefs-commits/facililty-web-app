import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api, fmt, getUser, openAttachment } from "../api";
import { AuthImg, Lightbox, useInterval } from "../components";
import { Badge } from "./Tickets";

const STAGES: [string, string, string][] = [
  ["before", "📷 Before — reported issue", "Photos of the problem when it was raised"],
  ["during", "🔧 During — work in progress", "Required before the ticket can be resolved"],
  ["after", "✅ After — completed work", "Required before the ticket can be resolved"],
];

export default function TicketDetail() {
  const { id } = useParams(); const u = getUser();
  const [t, setT] = useState<any>(null); const [err, setErr] = useState(""); const [techs, setTechs] = useState<any[]>([]);
  const [comment, setComment] = useState(""); const [internal, setInternal] = useState(false); const [zoom, setZoom] = useState("");
  const [st, setSt] = useState({ status: "", note: "", root_cause: "", corrective_action: "" });
  const [rating, setRating] = useState(5); const [fbText, setFbText] = useState(""); const [assignee, setAssignee] = useState("");
  const [uploading, setUploading] = useState("");
  const load = () => api(`/tickets/${id}`).then(setT).catch(e => setErr(e.message));
  useEffect(() => { load(); if (["facility_manager", "super_admin"].includes(u.role)) api("/users?role=technician").then(setTechs); }, [id]);
  useInterval(load, 10000, [id]);   // live refresh
  async function act(fn: () => Promise<any>) { setErr(""); try { await fn(); await load(); } catch (e: any) { setErr(e.message); } }
  if (!t) return err ? <p className="error">{err}</p> : <p className="muted">Loading…</p>;
  const isStaff = ["facility_manager", "super_admin", "technician"].includes(u.role);
  const mgr = ["facility_manager", "super_admin"].includes(u.role);
  const closed = t.status === "Closed";
  const post = (path: string, body: any) => act(() => api(`/tickets/${id}/${path}`, { method: "POST", body }));
  const upload = (kind: string) => async (e: any) => {
    const files: File[] = Array.from(e.target.files || []); e.target.value = ""; if (!files.length) return;
    setUploading(kind);
    await act(async () => { for (const f of files) { const fd = new FormData(); fd.append("file", f); fd.append("kind", kind); await api(`/tickets/${id}/attachments`, { method: "POST", body: fd }); } });
    setUploading("");
  };
  const photos = (k: string) => t.attachments.filter((a: any) => a.kind === k);
  const canUpload = (k: string) => !closed && (isStaff || (u.role === "client" && k === "before"));
  const waText = encodeURIComponent(`Hello ${t.rep_name}, regarding ticket ${t.number} (${t.subject}) at ${t.site.name}.`);
  const techStatuses = ["Acknowledged", "In Progress", "On Hold", "Pending Vendor", "Pending Client", "Resolved", "Escalated"];
  const statuses = mgr ? [...techStatuses, "Closed"] : techStatuses;
  const needsPhotos = st.status === "Resolved" && (!photos("during").length || !photos("after").length);

  return (
    <div>
      <h2>{t.number} — {t.subject}</h2>
      {err && <p className="error">{err}</p>}
      <div className="card"><div className="grid2">
        <div><b>Status</b><br /><Badge v={t.status} /> <Badge v={t.priority} /></div>
        <div><b>Category</b><br />{t.category.name}</div>
        <div><b>Site / Building</b><br />{t.site.name} / {t.building.name}{t.tower && ` / ${t.tower}`}{t.floor && ` / ${t.floor}`}</div>
        <div><b>Location</b><br />{t.location} {t.asset_id && `(Asset ${t.asset_id})`}</div>
        <div><b>Raised by</b><br />{t.requester.name} via {t.source}</div>
        <div><b>Assigned to</b><br />{t.assignee?.name || "Unassigned"}</div>
        <div><b>Created</b><br />{fmt(t.created_at)}</div>
        <div><b>Resolved</b><br />{fmt(t.resolved_at)}</div>
      </div><p>{t.description}</p>
        {t.root_cause && <p><b>Root cause:</b> {t.root_cause}</p>}{t.corrective_action && <p><b>Corrective action:</b> {t.corrective_action}</p>}</div>

      <div className="card rep"><h3>Client &amp; representative</h3>
        <div className="grid2">
          <div><b>Client</b><br />{t.client_name || "—"}</div>
          <div><b>Representative</b><br />{t.rep_name || "—"}</div>
          <div><b>Phone</b><br />{t.rep_phone ? <a href={`tel:${t.rep_phone}`}>{t.rep_phone}</a> : "—"}</div>
          <div><b>WhatsApp</b><br />{t.rep_whatsapp ? <a className="wa" target="_blank" rel="noreferrer" href={`${t.wa_link}?text=${waText}`}>💬 {t.rep_whatsapp}</a> : "—"}</div>
        </div></div>

      <div className="card"><h3>Photo evidence</h3>
        <div className="stages">{STAGES.map(([k, title, hint]) => (
          <div key={k} className={`stage ${photos(k).length ? "done" : ""}`}>
            <b>{title}</b> <span className="muted small">({photos(k).length})</span>
            <div className="muted small">{hint}</div>
            <div className="thumbs">{photos(k).map((a: any) => <AuthImg key={a.id} path={`/api/attachments/${a.id}`} className="thumb" onOpen={setZoom} />)}
              {photos(k).length === 0 && <span className="muted small">No photos yet</span>}</div>
            {canUpload(k) && <label className="uploadbtn">{uploading === k ? "Uploading…" : "＋ Add photo"}
              <input type="file" accept="image/*" capture="environment" multiple hidden onChange={upload(k)} /></label>}
          </div>))}</div>
        {isStaff && !closed && <p className="muted small">Checklist to resolve: during photo {photos("during").length ? "✔" : "✖"} · after photo {photos("after").length ? "✔" : "✖"}</p>}
        {t.attachments.filter((a: any) => a.kind === "evidence").length > 0 && <><b>Other files</b>{t.attachments.filter((a: any) => a.kind === "evidence").map((a: any) =>
          <div key={a.id}><button className="link" onClick={() => openAttachment(a.id, a.filename)}>{a.filename}</button></div>)}</>}
      </div>

      {mgr && !closed && <div className="card"><h3>Assign</h3>
        <select value={assignee} onChange={e => setAssignee(e.target.value)}><option value="">Select technician…</option>{techs.map(x => <option key={x.id} value={x.id}>{x.name}</option>)}</select>
        <button disabled={!assignee} onClick={() => post("assign", { assignee_id: Number(assignee) })}>Assign</button>
        <select value="" onChange={e => e.target.value && post("priority", { priority: e.target.value })}><option value="">Change priority…</option>{["Critical", "High", "Medium", "Low"].map(p => <option key={p}>{p}</option>)}</select></div>}

      {isStaff && !closed && <div className="card"><h3>Update status</h3>
        <select value={st.status} onChange={e => setSt({ ...st, status: e.target.value })}><option value="">Select status…</option>{statuses.map(s => <option key={s}>{s}</option>)}</select>
        {st.status === "Resolved" && <><input placeholder="Root cause" value={st.root_cause} onChange={e => setSt({ ...st, root_cause: e.target.value })} />
          <input placeholder="Corrective action (required)" value={st.corrective_action} onChange={e => setSt({ ...st, corrective_action: e.target.value })} /></>}
        {needsPhotos && <p className="error small">Add at least one “during” and one “after” photo above before resolving.</p>}
        <input placeholder="Remarks" value={st.note} onChange={e => setSt({ ...st, note: e.target.value })} />
        <button disabled={!st.status || needsPhotos} onClick={() => post("status", st)}>Update</button></div>}

      {u.role === "client" && <div className="card"><h3>Your actions</h3>
        {t.status === "Resolved" && <button onClick={() => post("status", { status: "Closed" })}>Confirm resolved &amp; close</button>}
        {["Resolved", "Closed"].includes(t.status) && <button className="secondary" onClick={() => { const r = prompt("Why are you reopening this ticket?"); if (r) post("reopen", { reason: r }); }}>Reopen</button>}
        {["Resolved", "Closed"].includes(t.status) && !t.feedback && <div><label>Rating <select value={rating} onChange={e => setRating(+e.target.value)}>{[5, 4, 3, 2, 1].map(n => <option key={n}>{n}</option>)}</select></label>
          <input placeholder="Feedback (optional)" value={fbText} onChange={e => setFbText(e.target.value)} /><button onClick={() => post("feedback", { rating, comment: fbText })}>Submit feedback</button></div>}
        {t.feedback && <p>Your rating: {t.feedback.rating}/5 {t.feedback.comment}</p>}</div>}

      <div className="card"><h3>Comments</h3>
        {t.comments.map((c: any) => <p key={c.id} className={c.internal ? "internal" : ""}><b>{c.author}</b> <span className="muted">{fmt(c.created_at)} {c.internal && "· internal"}</span><br />{c.body}</p>)}
        <textarea rows={2} value={comment} onChange={e => setComment(e.target.value)} placeholder="Write a comment…" />
        {isStaff && <label className="inline"><input type="checkbox" checked={internal} onChange={e => setInternal(e.target.checked)} /> Internal note</label>}
        <button disabled={!comment.trim()} onClick={() => post("comments", { body: comment, internal }).then(() => setComment(""))}>Post</button></div>

      <div className="card"><h3>Activity history</h3>
        <ul className="timeline">{t.history.map((h: any) => <li key={h.id}><b>{h.action.replace("_", " ")}</b> {h.from_status && h.to_status && `${h.from_status} → ${h.to_status}`} <span className="muted">by {h.actor} · {fmt(h.created_at)}</span>{h.note && <div>{h.note}</div>}</li>)}</ul></div>
      {zoom && <Lightbox src={zoom} onClose={() => setZoom("")} />}
    </div>
  );
}

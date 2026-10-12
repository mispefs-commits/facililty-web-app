import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, fmt } from "../api";
import { useInterval } from "../components";

export const Badge = ({ v }: any) => <span className={`badge ${String(v).replace(/\s/g, "")}`}>{v}</span>;
const STATUSES = ["New", "Acknowledged", "Assigned", "In Progress", "On Hold", "Pending Vendor", "Pending Client", "Resolved", "Closed", "Reopened", "Escalated"];

export default function Tickets() {
  const [res, setRes] = useState<any>(null); const [err, setErr] = useState("");
  const [f, setF] = useState({ q: "", status: "", priority: "", page: 1 });
  const load = (reset = false) => {
    const p = new URLSearchParams(); Object.entries(f).forEach(([k, v]) => v && p.set(k, String(v)));
    if (reset) setRes(null); api(`/tickets?${p}`).then(setRes).catch(e => setErr(e.message));
  };
  useEffect(() => { load(true); }, [f]);
  useInterval(() => load(), 15000, [f]);
  return (
    <div>
      <h2>Tickets</h2>
      <div className="filters">
        <input placeholder="Search number, location, asset, keyword…" value={f.q} onChange={e => setF({ ...f, q: e.target.value, page: 1 })} />
        <select value={f.status} onChange={e => setF({ ...f, status: e.target.value, page: 1 })}><option value="">All statuses</option>{STATUSES.map(s => <option key={s}>{s}</option>)}</select>
        <select value={f.priority} onChange={e => setF({ ...f, priority: e.target.value, page: 1 })}><option value="">All priorities</option>{["Critical", "High", "Medium", "Low"].map(s => <option key={s}>{s}</option>)}</select>
      </div>
      {err && <p className="error">{err}</p>}
      {!res ? <p className="muted">Loading…</p> : res.items.length === 0 ? <p className="muted">No tickets found.</p> :
        <div className="scroll"><table><thead><tr><th>Ticket</th><th>Subject</th><th>Site / Location</th><th>Priority</th><th>Status</th><th>Assignee</th><th>Created</th></tr></thead>
          <tbody>{res.items.map((t: any) => <tr key={t.id}>
            <td><Link to={`/tickets/${t.id}`}>{t.number}</Link></td><td>{t.subject}</td><td>{t.site.name}<br /><span className="muted">{t.location}</span></td>
            <td><Badge v={t.priority} /></td><td><Badge v={t.status} /></td><td>{t.assignee?.name || "—"}</td><td>{fmt(t.created_at)}</td></tr>)}</tbody></table></div>}
      {res && <div className="pager"><button disabled={f.page <= 1} onClick={() => setF({ ...f, page: f.page - 1 })}>Prev</button>
        <span>Page {res.page} of {Math.max(1, Math.ceil(res.total / res.page_size))} ({res.total} tickets)</span>
        <button disabled={f.page * res.page_size >= res.total} onClick={() => setF({ ...f, page: f.page + 1 })}>Next</button></div>}
    </div>
  );
}

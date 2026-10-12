import { useEffect, useState } from "react";
import { api } from "../api";
import { useInterval } from "../components";

const Card = ({ label, value }: any) => <div className="stat card"><div className="muted">{label}</div><div className="big">{value ?? "—"}</div></div>;

export default function Dashboard() {
  const [d, setD] = useState<any>(null); const [err, setErr] = useState("");
  const load = () => api("/dashboard/summary").then(setD).catch(e => setErr(e.message));
  useEffect(() => { load(); }, []);
  useInterval(load, 15000);
  if (err) return <p className="error">{err}</p>;
  if (!d) return <p className="muted">Loading…</p>;
  const staff = d.role !== "client";
  return (
    <div>
      <h2>{d.role === "technician" ? "My Work" : d.role === "client" ? "My Complaints" : "Dashboard"}</h2>
      <div className="grid">
        <Card label="Total tickets" value={d.total} />
        <Card label="Open" value={d.open} />
        <Card label="Resolved / Closed" value={d.closed} />
        {staff && d.role !== "technician" && <Card label="Awaiting acknowledgement" value={d.needs_acknowledgement} />}
        <Card label="In progress" value={d.in_progress} />
        <Card label="Reopened" value={d.reopened} />
        <Card label="Escalated" value={d.escalated} />
        <Card label="Avg. rating" value={d.avg_rating} />
      </div>
      <h3>Open tickets by priority</h3>
      <div className="grid">{["Critical", "High", "Medium", "Low"].map(p => <Card key={p} label={p} value={d.open_by_priority[p] || 0} />)}</div>
      {d.by_site && <><h3>Site-wise</h3>
        <table><thead><tr><th>Site</th><th>Total</th><th>Open</th></tr></thead>
          <tbody>{d.by_site.map((s: any) => <tr key={s.site}><td>{s.site}</td><td>{s.total}</td><td>{s.open}</td></tr>)}</tbody></table></>}
      <p className="muted">SLA compliance, response times and trends arrive in Phase 2.</p>
    </div>
  );
}

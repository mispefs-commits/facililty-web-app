import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, getUser } from "../api";

export default function NewTicket() {
  const nav = useNavigate(); const u = getUser();
  const [sites, setSites] = useState<any[]>([]); const [cats, setCats] = useState<any[]>([]); const [struct, setStruct] = useState<any[]>([]);
  const [files, setFiles] = useState<File[]>([]);
  const [sameWa, setSameWa] = useState(true);
  const [f, setF] = useState<any>({ site_id: "", building_id: "", tower_id: "", floor_id: "", location: "", asset_id: "", category_id: "", subject: "", description: "",
    client_name: "", rep_name: u?.name || "", rep_phone: "", rep_whatsapp: "" });
  const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  useEffect(() => { api("/sites").then(setSites); api("/categories").then(setCats); }, []);
  useEffect(() => { if (f.site_id) api(`/sites/${f.site_id}/structure`).then(setStruct); else setStruct([]); }, [f.site_id]);
  const previews = useMemo(() => files.map(x => URL.createObjectURL(x)), [files]);
  const b = struct.find(x => String(x.id) === String(f.building_id));
  const set = (k: string, v: any) => setF((p: any) => ({ ...p, [k]: v, ...(k === "site_id" ? { building_id: "", tower_id: "", floor_id: "" } : {}), ...(k === "building_id" ? { tower_id: "", floor_id: "" } : {}) }));

  async function submit(e: any) {
    e.preventDefault(); setBusy(true); setErr("");
    try {
      const body: any = { ...f, rep_whatsapp: sameWa ? f.rep_phone : f.rep_whatsapp };
      ["site_id", "building_id", "tower_id", "floor_id", "category_id"].forEach(k => body[k] = body[k] ? Number(body[k]) : null);
      const t = await api("/tickets", { method: "POST", body });
      for (const file of files) { const fd = new FormData(); fd.append("file", file); fd.append("kind", "before"); await api(`/tickets/${t.id}/attachments`, { method: "POST", body: fd }); }
      nav(`/tickets/${t.id}`);
    } catch (x: any) { setErr(x.message); } finally { setBusy(false); }
  }
  if (sites.length === 0) return <p className="muted">No sites are assigned to your account yet. Please contact your administrator.</p>;
  return (
    <form className="card form" onSubmit={submit}>
      <h2>Raise a complaint</h2>
      <p className="muted">Prefer chatting? Use the 💬 Chat assistant — it asks the same questions step by step.</p>
      <label>Site<select required value={f.site_id} onChange={e => set("site_id", e.target.value)}><option value="">Select…</option>{sites.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
      <label>Building<select required value={f.building_id} onChange={e => set("building_id", e.target.value)}><option value="">Select…</option>{struct.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
      {b && <><label>Tower / Block<select value={f.tower_id} onChange={e => set("tower_id", e.target.value)}><option value="">—</option>{b.towers.map((t: any) => <option key={t.id} value={t.id}>{t.name}</option>)}</select></label>
        <label>Floor<select value={f.floor_id} onChange={e => set("floor_id", e.target.value)}><option value="">—</option>{b.floors.filter((x: any) => !f.tower_id || String(x.tower_id) === String(f.tower_id)).map((t: any) => <option key={t.id} value={t.id}>{t.name}</option>)}</select></label></>}
      <label>Exact location (room / area)<input required minLength={2} value={f.location} onChange={e => set("location", e.target.value)} placeholder="e.g. Meeting room 3B" /></label>
      <label>Asset ID (optional)<input value={f.asset_id} onChange={e => set("asset_id", e.target.value)} /></label>
      <label>Category<select required value={f.category_id} onChange={e => set("category_id", e.target.value)}><option value="">Select…</option>{cats.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
      <label>Subject<input required minLength={3} value={f.subject} onChange={e => set("subject", e.target.value)} /></label>
      <label>Description<textarea required minLength={5} rows={4} value={f.description} onChange={e => set("description", e.target.value)} /></label>
      <h3>Client &amp; representative</h3>
      <label>Client / company name<input required value={f.client_name} onChange={e => set("client_name", e.target.value)} /></label>
      <label>Representative name<input required value={f.rep_name} onChange={e => set("rep_name", e.target.value)} /></label>
      <label>Representative phone<input required inputMode="tel" placeholder="9876543210 or +919876543210" value={f.rep_phone} onChange={e => set("rep_phone", e.target.value)} /></label>
      <label className="inline"><input type="checkbox" checked={sameWa} onChange={e => setSameWa(e.target.checked)} /> WhatsApp number is the same as phone</label>
      {!sameWa && <label>Representative WhatsApp<input required inputMode="tel" value={f.rep_whatsapp} onChange={e => set("rep_whatsapp", e.target.value)} /></label>}
      <h3>Photos of the issue (before)</h3>
      <label><input type="file" multiple accept="image/*" capture="environment" onChange={e => setFiles(Array.from(e.target.files || []))} /></label>
      <div className="thumbs">{previews.map((p, i) => <img key={i} src={p} className="thumb" alt="" />)}</div>
      <p className="muted">For fire, smoke, gas leak or electrical hazard, also call the site security desk immediately.</p>
      {err && <p className="error">{err}</p>}
      <button disabled={busy}>{busy ? "Submitting…" : "Submit complaint"}</button>
    </form>
  );
}

import { useEffect, useState } from "react";
import { api } from "../api";

const ROLES = ["super_admin", "management", "facility_manager", "technician", "client"];

export default function Admin() {
  const [users, setUsers] = useState<any[]>([]); const [sites, setSites] = useState<any[]>([]); const [msg, setMsg] = useState("");
  const [nu, setNu] = useState({ name: "", email: "", password: "", role: "technician", site_ids: [] as number[] });
  const [ns, setNs] = useState({ region: "", name: "", code: "" });
  const load = () => { api("/users").then(setUsers); api("/sites").then(setSites); };
  useEffect(load, []);
  const run = async (fn: () => Promise<any>, ok: string) => { setMsg(""); try { await fn(); setMsg(ok); load(); } catch (e: any) { setMsg("Error: " + e.message); } };
  return (
    <div>
      <h2>Administration</h2>{msg && <p className={msg.startsWith("Error") ? "error" : "ok"}>{msg}</p>}
      <div className="card form"><h3>Add site</h3>
        <input placeholder="City / Region" value={ns.region} onChange={e => setNs({ ...ns, region: e.target.value })} />
        <input placeholder="Site name" value={ns.name} onChange={e => setNs({ ...ns, name: e.target.value })} />
        <input placeholder="Site code (unique)" value={ns.code} onChange={e => setNs({ ...ns, code: e.target.value })} />
        <button onClick={() => run(() => api("/sites", { method: "POST", body: ns }), "Site created. Add buildings/towers/floors via the API docs at /docs.")}>Create site</button></div>
      <div className="card form"><h3>Add user</h3>
        <input placeholder="Name" value={nu.name} onChange={e => setNu({ ...nu, name: e.target.value })} />
        <input placeholder="Email" value={nu.email} onChange={e => setNu({ ...nu, email: e.target.value })} />
        <input type="password" placeholder="Temporary password" value={nu.password} onChange={e => setNu({ ...nu, password: e.target.value })} />
        <select value={nu.role} onChange={e => setNu({ ...nu, role: e.target.value })}>{ROLES.map(r => <option key={r}>{r}</option>)}</select>
        <select multiple value={nu.site_ids.map(String)} onChange={e => setNu({ ...nu, site_ids: Array.from(e.target.selectedOptions).map(o => +o.value) })}>{sites.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select>
        <button onClick={() => run(() => api("/users", { method: "POST", body: nu }), "User created")}>Create user</button></div>
      <h3>Users</h3><div className="scroll"><table><thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Sites</th><th>Active</th><th>Site access</th></tr></thead>
        <tbody>{users.map(u => <tr key={u.id}><td>{u.name}</td><td>{u.email}</td><td>{u.role}</td><td>{u.sites.map((s: any) => s.name).join(", ")}</td>
          <td><input type="checkbox" checked={u.is_active} onChange={e => run(() => api(`/users/${u.id}`, { method: "PATCH", body: { is_active: e.target.checked } }), "Updated")} /></td>
          <td><select value="" onChange={e => e.target.value && run(() => api(`/users/${u.id}`, { method: "PATCH", body: { site_ids: [...u.sites.map((s: any) => s.id), +e.target.value] } }), "Site added")}><option value="">Add site…</option>{sites.filter(s => !u.sites.some((x: any) => x.id === s.id)).map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></td></tr>)}</tbody></table></div>
    </div>
  );
}

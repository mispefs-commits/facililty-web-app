import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, setSession } from "../api";

export function Login() {
  const nav = useNavigate();
  const [f, setF] = useState({ email: "", password: "" });
  const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  async function submit(e: any) {
    e.preventDefault(); setBusy(true); setErr("");
    try { const r = await api("/auth/login", { method: "POST", body: f }); setSession(r.access_token, r.user); nav("/"); }
    catch (x: any) { setErr(x.message); } finally { setBusy(false); }
  }
  return (
    <div className="auth card"><h2>Sign in</h2>
      <form onSubmit={submit}>
        <label>Email<input type="email" required value={f.email} onChange={e => setF({ ...f, email: e.target.value })} /></label>
        <label>Password<input type="password" required value={f.password} onChange={e => setF({ ...f, password: e.target.value })} /></label>
        {err && <p className="error">{err}</p>}
        <button disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
      </form>
      <p className="muted">New occupant? <Link to="/register">Create an account</Link></p>
    </div>
  );
}

export function Register() {
  const nav = useNavigate();
  const [f, setF] = useState({ name: "", email: "", phone: "", password: "" });
  const [err, setErr] = useState(""); const [ok, setOk] = useState(false);
  async function submit(e: any) {
    e.preventDefault(); setErr("");
    try { await api("/auth/register", { method: "POST", body: f }); setOk(true); setTimeout(() => nav("/login"), 2500); }
    catch (x: any) { setErr(x.message); }
  }
  return (
    <div className="auth card"><h2>Create client account</h2>
      {ok ? <p>Account created. An administrator must grant you site access before you can raise complaints. Redirecting…</p> :
        <form onSubmit={submit}>
          <label>Name<input required value={f.name} onChange={e => setF({ ...f, name: e.target.value })} /></label>
          <label>Email<input type="email" required value={f.email} onChange={e => setF({ ...f, email: e.target.value })} /></label>
          <label>Phone<input value={f.phone} onChange={e => setF({ ...f, phone: e.target.value })} /></label>
          <label>Password<input type="password" required value={f.password} onChange={e => setF({ ...f, password: e.target.value })} /></label>
          {err && <p className="error">{err}</p>}
          <button>Register</button>
        </form>}
      <p className="muted"><Link to="/login">Back to sign in</Link></p>
    </div>
  );
}

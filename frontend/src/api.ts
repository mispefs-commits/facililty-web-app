export const getToken = () => localStorage.getItem("token");
export const getUser = () => { try { return JSON.parse(localStorage.getItem("user") || "null"); } catch { return null; } };
export function setSession(token: string, user: any) { localStorage.setItem("token", token); localStorage.setItem("user", JSON.stringify(user)); }
export function logout() { localStorage.removeItem("token"); localStorage.removeItem("user"); location.href = "/login"; }

export async function api(path: string, opts: any = {}) {
  const headers: any = { ...(opts.headers || {}) };
  if (getToken()) headers.Authorization = `Bearer ${getToken()}`;
  let body = opts.body;
  if (body && !(body instanceof FormData)) { headers["Content-Type"] = "application/json"; body = JSON.stringify(body); }
  const res = await fetch(`/api${path}`, { ...opts, headers, body });
  if (res.status === 401 && !path.startsWith("/auth/login")) logout();
  const data = res.headers.get("content-type")?.includes("json") ? await res.json() : null;
  if (!res.ok) {
    const d = data?.detail;
    throw new Error(typeof d === "string" ? d : Array.isArray(d) ? d.map((x: any) => x.msg).join("; ") : "Request failed");
  }
  return data;
}

export async function openAttachment(id: number, name: string) {
  const res = await fetch(`/api/attachments/${id}`, { headers: { Authorization: `Bearer ${getToken()}` } });
  if (!res.ok) return alert("Could not open file");
  const url = URL.createObjectURL(await res.blob());
  window.open(url, "_blank");
}

export const fmt = (d?: string) => (d ? new Date(d).toLocaleString() : "—");
export const STAFF = ["super_admin", "facility_manager", "technician"];

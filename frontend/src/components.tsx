import { useEffect, useState } from "react";
import { getToken } from "./api";

/** <img> that loads a protected file with the login token (plain <img src> cannot send headers). */
export function AuthImg({ path, alt, className, onOpen }: { path: string; alt?: string; className?: string; onOpen?: (src: string) => void }) {
  const [src, setSrc] = useState("");
  useEffect(() => {
    let dead = false, url = "";
    fetch(path, { headers: { Authorization: `Bearer ${getToken()}` } })
      .then(r => (r.ok ? r.blob() : null))
      .then(b => { if (b && !dead) { url = URL.createObjectURL(b); setSrc(url); } })
      .catch(() => {});
    return () => { dead = true; if (url) URL.revokeObjectURL(url); };
  }, [path]);
  if (!src) return <div className={`ph ${className || ""}`} />;
  return <img src={src} alt={alt || ""} className={className} onClick={() => onOpen?.(src)} style={{ cursor: onOpen ? "zoom-in" : undefined }} />;
}

export function Lightbox({ src, onClose }: { src: string; onClose: () => void }) {
  useEffect(() => { const f = (e: KeyboardEvent) => e.key === "Escape" && onClose(); window.addEventListener("keydown", f); return () => window.removeEventListener("keydown", f); }, []);
  return <div className="lightbox" onClick={onClose}><img src={src} alt="" /><span className="muted">Click anywhere or press Esc to close</span></div>;
}

export function useInterval(fn: () => void, ms: number, deps: any[] = []) {
  useEffect(() => { const i = setInterval(fn, ms); return () => clearInterval(i); }, deps);
}

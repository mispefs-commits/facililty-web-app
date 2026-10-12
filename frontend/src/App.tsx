import { useEffect, useState } from "react";
import { Link, Navigate, Route, Routes } from "react-router-dom";
import { api, getToken, getUser, logout } from "./api";
import { Login, Register } from "./pages/Auth";
import Dashboard from "./pages/Dashboard";
import Tickets from "./pages/Tickets";
import NewTicket from "./pages/NewTicket";
import TicketDetail from "./pages/TicketDetail";
import Admin from "./pages/Admin";
import Chat from "./pages/Chat";

function Protected({ children }: any) { return getToken() ? children : <Navigate to="/login" replace />; }

function Layout({ children }: any) {
  const u = getUser();
  const canChat = ["client", "facility_manager", "super_admin"].includes(u?.role);
  const [unread, setUnread] = useState(0);
  useEffect(() => {
    if (!canChat) return;
    const f = () => api("/chat/unread").then(r => setUnread(r.unread)).catch(() => {});
    f(); const i = setInterval(f, 5000); return () => clearInterval(i);
  }, []);
  return (
    <div>
      <header className="nav">
        <strong>FM Helpdesk</strong>
        <nav>
          <Link to="/">Dashboard</Link>
          <Link to="/tickets">Tickets</Link>
          {canChat && <Link to="/tickets/new">Raise Complaint</Link>}
          {canChat && <Link to="/chat">Chat{unread > 0 && <span className="dot">{unread}</span>}</Link>}
          {u?.role === "super_admin" && <Link to="/admin">Admin</Link>}
        </nav>
        <span className="muted">{u?.name} ({u?.role?.replace("_", " ")}) <button className="link" onClick={logout}>Log out</button></span>
      </header>
      <main className="container">{children}</main>
      {canChat && <Link to="/chat" className="fab" title="Chat with the helpdesk">💬{unread > 0 && <span className="dot">{unread}</span>}</Link>}
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/*" element={
        <Protected><Layout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/tickets" element={<Tickets />} />
            <Route path="/tickets/new" element={<NewTicket />} />
            <Route path="/tickets/:id" element={<TicketDetail />} />
            <Route path="/chat" element={<Chat />} />
            <Route path="/admin" element={<Admin />} />
          </Routes>
        </Layout></Protected>} />
    </Routes>
  );
}

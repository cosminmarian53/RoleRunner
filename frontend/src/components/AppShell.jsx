import {
  BriefcaseBusiness,
  FileText,
  LayoutDashboard,
  Menu,
  Search,
  UserRound,
  X,
} from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";

import { eventUrl } from "../lib/api";
import { useSSE } from "../hooks/useSSE";
import ProviderStatus from "./ProviderStatus";

const navigation = [
  ["/", "Dashboard", LayoutDashboard],
  ["/profile", "Profile", UserRound],
  ["/jobs", "Jobs", Search],
  ["/cv", "CV Builder", FileText],
  ["/applications", "Applications", BriefcaseBusiness],
];

export default function AppShell() {
  const [open, setOpen] = useState(false);
  const { data: agent, connected } = useSSE(eventUrl("/agent/status"));

  return (
    <div className="app-shell">
      <aside className={`sidebar ${open ? "open" : ""}`}>
        <div className="brand-row">
          <div className="brand-mark">JB</div>
          <div><strong>Job-Bot</strong><span>Career workspace</span></div>
          <button className="icon-button close-nav" aria-label="Close navigation" onClick={() => setOpen(false)}><X /></button>
        </div>
        <nav>
          {navigation.map(([to, label, Icon]) => (
            <NavLink key={to} to={to} end={to === "/"} onClick={() => setOpen(false)}>
              <Icon size={18} /><span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          <ProviderStatus compact />
          <div className="agent-line">
            <span className={`status-dot ${connected ? "online" : "offline"}`} />
            <span>{agent?.message || (connected ? "Agent stream live" : "Agent stream offline")}</span>
          </div>
        </div>
      </aside>
      {open && <button className="nav-backdrop" aria-label="Close navigation" onClick={() => setOpen(false)} />}
      <main className="main-content">
        <header className="mobile-header">
          <button className="icon-button" aria-label="Open navigation" onClick={() => setOpen(true)}><Menu /></button>
          <strong>Job-Bot</strong>
        </header>
        <Outlet />
      </main>
    </div>
  );
}

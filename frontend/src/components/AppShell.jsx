import {
  BriefcaseBusiness,
  FileText,
  Home,
  LayoutDashboard,
  Menu,
  MessageSquare,
  Search,
  UserRound,
  X,
  Zap,
} from "lucide-react";
import { useState } from "react";
import { Link, NavLink, Outlet } from "react-router-dom";

import FeedbackModal from "./FeedbackModal";
import ProviderStatus from "./ProviderStatus";
import { useSSE } from "../hooks/useSSE";
import { eventUrl } from "../lib/api";

const navigation = [
  ["/dashboard", "Dashboard", LayoutDashboard],
  ["/profile", "Profile", UserRound],
  ["/jobs", "Jobs", Search],
  ["/cv", "CV Builder", FileText],
  ["/applications", "Applications", BriefcaseBusiness],
];

export default function AppShell() {
  const [open, setOpen] = useState(false);
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const { data: agent } = useSSE(eventUrl("/agent/status"));

  return (
    <div className="app-shell min-h-screen bg-[#0b0f19] text-slate-100 flex flex-col md:flex-row">
      <aside className={`sidebar ${open ? "open" : ""} bg-[#0e1320] border-r border-slate-800/80`}>
        <div className="brand-row flex items-center justify-between p-4 border-b border-slate-800/80">
          <Link to="/" className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center shadow-lg shadow-indigo-600/30 border border-indigo-400/30">
              <Zap size={18} className="text-white" />
            </div>
            <div>
              <strong className="block text-sm font-bold text-white leading-tight">RoleRunner</strong>
              <span className="text-[11px] text-slate-400">Career Autopilot</span>
            </div>
          </Link>
          <button
            className="icon-button close-nav md:hidden text-slate-400 hover:text-white"
            aria-label="Close navigation"
            onClick={() => setOpen(false)}
          >
            <X size={18} />
          </button>
        </div>

        <nav className="p-3 space-y-1">
          <Link
            to="/"
            className="flex items-center gap-3 px-3 py-2 text-xs font-medium text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 rounded-lg transition mb-2"
          >
            <Home size={16} /> <span>Home</span>
          </Link>

          {navigation.map(([to, label, Icon]) => (
            <NavLink
              key={to}
              to={to}
              onClick={() => setOpen(false)}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-semibold transition ${
                  isActive
                    ? "bg-indigo-600/20 text-indigo-300 border border-indigo-500/30 shadow-sm"
                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/60"
                }`
              }
            >
              <Icon size={18} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer mt-auto p-4 border-t border-slate-800/80 space-y-3">
          <button
            onClick={() => setFeedbackOpen(true)}
            className="w-full flex items-center justify-center gap-2 py-2 px-3 text-xs font-semibold text-indigo-300 bg-indigo-500/10 hover:bg-indigo-500/20 border border-indigo-500/20 rounded-xl transition"
          >
            <MessageSquare size={14} /> Give Feedback
          </button>

          <ProviderStatus compact />
          {agent?.message && (
            <div className="agent-line flex items-center gap-2 text-[11px] text-indigo-300 bg-indigo-950/40 border border-indigo-500/20 px-2.5 py-1.5 rounded-lg">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span className="truncate">{agent.message}</span>
            </div>
          )}
        </div>
      </aside>

      {open && <button className="nav-backdrop" aria-label="Close navigation" onClick={() => setOpen(false)} />}

      <main className="main-content flex-1 min-w-0">
        <header className="mobile-header md:hidden flex items-center justify-between p-4 border-b border-slate-800/80 bg-[#0e1320]">
          <button className="icon-button" aria-label="Open navigation" onClick={() => setOpen(true)}>
            <Menu size={20} />
          </button>
          <div className="mobile-brand flex items-center gap-2">
            <Zap size={18} className="text-indigo-400" />
            <strong className="text-sm font-bold text-white">RoleRunner</strong>
          </div>
          <button
            onClick={() => setFeedbackOpen(true)}
            className="p-2 rounded-lg bg-indigo-500/10 text-indigo-300"
            title="Give feedback"
          >
            <MessageSquare size={16} />
          </button>
        </header>

        <Outlet />
      </main>

      {/* Global Feedback Modal */}
      <FeedbackModal isOpen={feedbackOpen} onClose={() => setFeedbackOpen(false)} />
    </div>
  );
}

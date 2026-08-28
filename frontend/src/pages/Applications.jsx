import {
  ArrowRight,
  BriefcaseBusiness,
  Building2,
  CheckCircle2,
  ExternalLink,
  Kanban,
  LoaderCircle,
  Plus,
  Trash2,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";

import { api } from "../lib/api";

const COLUMNS = [
  { id: "applied", label: "Applied", color: "border-blue-500/40 text-blue-400 bg-blue-500/10" },
  { id: "interviewing", label: "Interviewing", color: "border-amber-500/40 text-amber-400 bg-amber-500/10" },
  { id: "offer", label: "Offer Received", color: "border-emerald-500/40 text-emerald-400 bg-emerald-500/10" },
  { id: "rejected", label: "Archived / Rejected", color: "border-slate-700 text-slate-400 bg-slate-800/40" },
];

export default function Applications() {
  const [items, setItems] = useState([]);
  const [adding, setAdding] = useState(false);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ title: "", company: "", link: "", status: "applied" });
  const [notice, setNotice] = useState("");

  const loadApplications = async () => {
    try {
      const result = await api("/applications");
      setItems(Array.isArray(result) ? result : result?.applications || []);
    } catch {
      setItems(JSON.parse(localStorage.getItem("rolerunner-applications") || "[]"));
    }
  };

  useEffect(() => {
    loadApplications();
  }, []);

  const persistLocal = (next) => {
    setItems(next);
    localStorage.setItem("rolerunner-applications", JSON.stringify(next));
  };

  const handleAdd = async (e) => {
    e.preventDefault();
    if (!form.title.trim() || !form.company.trim()) return;
    setBusy(true);

    try {
      const created = await api("/applications", {
        method: "POST",
        body: JSON.stringify(form),
      });
      setItems((current) => [...current, created]);
    } catch {
      persistLocal([...items, { ...form, id: crypto.randomUUID(), created_at: new Date().toISOString() }]);
      setNotice("Saved locally.");
    } finally {
      setBusy(false);
      setForm({ title: "", company: "", link: "", status: "applied" });
      setAdding(false);
    }
  };

  const handleAdvance = async (item) => {
    const stageIds = COLUMNS.map((c) => c.id);
    const currentIndex = stageIds.indexOf(item.status);
    if (currentIndex >= stageIds.length - 1) return;

    const nextStatus = stageIds[currentIndex + 1];
    const next = items.map((entry) => (entry.id === item.id ? { ...entry, status: nextStatus } : entry));

    try {
      await api(`/applications/${item.id}`, {
        method: "PATCH",
        body: JSON.stringify({ status: nextStatus }),
      });
      setItems(next);
    } catch {
      persistLocal(next);
    }
  };

  const handleDelete = async (itemId) => {
    const next = items.filter((entry) => entry.id !== itemId);
    try {
      await api(`/applications/${itemId}`, { method: "DELETE" });
      setItems(next);
    } catch {
      persistLocal(next);
    }
  };

  return (
    <div className="page max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-xs font-semibold">
            <Kanban size={14} /> Pipeline Management
          </div>
          <h1 className="text-3xl font-extrabold text-white tracking-tight mt-1">Application Tracker</h1>
          <p className="text-slate-400 text-sm">
            Organize every opportunity across screening, interviews, offers, and follow-ups.
          </p>
        </div>

        <button
          type="button"
          onClick={() => setAdding(true)}
          className="inline-flex items-center gap-2 px-4 py-2.5 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-500 rounded-xl shadow-lg shadow-indigo-600/25 transition"
        >
          <Plus size={16} /> Add Application
        </button>
      </div>

      {notice && (
        <div className="p-3 rounded-xl bg-slate-900 border border-slate-700 text-xs text-slate-300">
          {notice}
        </div>
      )}

      {/* Add Modal */}
      {adding && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
          <div className="relative w-full max-w-md p-6 bg-[#111622] border border-slate-700 rounded-2xl shadow-2xl space-y-4">
            <button
              onClick={() => setAdding(false)}
              className="absolute top-4 right-4 p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800"
            >
              <X size={18} />
            </button>

            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <Plus size={18} className="text-indigo-400" /> New Application
            </h3>

            <form onSubmit={handleAdd} className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Job Title / Role</label>
                <input
                  required
                  type="text"
                  value={form.title}
                  onChange={(e) => setForm({ ...form, title: e.target.value })}
                  placeholder="e.g. Lead Product Designer"
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-100 focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Company</label>
                <input
                  required
                  type="text"
                  value={form.company}
                  onChange={(e) => setForm({ ...form, company: e.target.value })}
                  placeholder="e.g. Vercel"
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-100 focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Job URL (Optional)</label>
                <input
                  type="url"
                  value={form.link}
                  onChange={(e) => setForm({ ...form, link: e.target.value })}
                  placeholder="https://..."
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-100 focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Starting Stage</label>
                <select
                  value={form.status}
                  onChange={(e) => setForm({ ...form, status: e.target.value })}
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
                >
                  <option value="applied">Applied</option>
                  <option value="interviewing">Interviewing</option>
                  <option value="offer">Offer Received</option>
                  <option value="rejected">Archived</option>
                </select>
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setAdding(false)}
                  className="px-4 py-2 text-xs font-semibold text-slate-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={busy}
                  className="px-5 py-2 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-500 rounded-xl shadow-md transition"
                >
                  {busy ? <LoaderCircle size={14} className="animate-spin" /> : "Save"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Kanban Board Columns */}
      <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
        {COLUMNS.map((col) => {
          const colItems = items.filter((it) => it.status === col.id);
          return (
            <div
              key={col.id}
              className="p-4 rounded-2xl bg-[#111622] border border-slate-800 shadow-md flex flex-col space-y-3 min-h-[400px]"
            >
              {/* Column Header */}
              <div className="flex items-center justify-between pb-2 border-b border-slate-800">
                <span className={`px-2.5 py-1 text-xs font-bold rounded-lg border ${col.color}`}>
                  {col.label}
                </span>
                <span className="text-xs font-bold text-slate-400">{colItems.length}</span>
              </div>

              {/* Items List */}
              <div className="flex-1 space-y-3 overflow-y-auto">
                {colItems.map((item) => (
                  <article
                    key={item.id}
                    className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 hover:border-slate-700 transition shadow-sm space-y-2.5"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <h4 className="text-sm font-bold text-white truncate">{item.title}</h4>
                        <p className="text-xs text-slate-300 font-medium truncate">{item.company}</p>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleDelete(item.id)}
                        className="text-slate-500 hover:text-rose-400 transition p-1"
                        title="Delete application"
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>

                    <div className="flex items-center justify-between pt-1 border-t border-slate-800/60 text-xs">
                      {item.link ? (
                        <a
                          href={item.link}
                          target="_blank"
                          rel="noreferrer"
                          className="text-indigo-400 hover:text-indigo-300 flex items-center gap-1"
                        >
                          <ExternalLink size={12} /> View Role
                        </a>
                      ) : (
                        <span className="text-slate-600 text-[11px]">No link</span>
                      )}

                      {col.id !== "offer" && col.id !== "rejected" && (
                        <button
                          type="button"
                          onClick={() => handleAdvance(item)}
                          className="px-2 py-1 text-[11px] font-bold text-indigo-300 bg-indigo-500/10 hover:bg-indigo-500/20 border border-indigo-500/20 rounded-md flex items-center gap-1 transition"
                          title="Advance to next stage"
                        >
                          Advance <ArrowRight size={11} />
                        </button>
                      )}
                    </div>
                  </article>
                ))}

                {colItems.length === 0 && (
                  <div className="py-12 text-center text-xs text-slate-600 font-medium">
                    No applications here
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </section>
    </div>
  );
}

import { ArrowRight, BriefcaseBusiness, Plus, X } from "lucide-react";
import { useEffect, useState } from "react";

import { api } from "../lib/api";

const columns = ["applied", "interviewing", "offer", "rejected"];

export default function Applications() {
  const [items, setItems] = useState([]);
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ title: "", company: "", link: "", status: "applied" });
  const [notice, setNotice] = useState("");

  useEffect(() => {
    api("/applications").then((result) => setItems(Array.isArray(result) ? result : result?.applications || [])).catch(() => {
      setItems(JSON.parse(localStorage.getItem("job-bot-applications") || "[]"));
      setNotice("Using local storage until application sync is available.");
    });
  }, []);

  const persistLocal = (next) => { setItems(next); localStorage.setItem("job-bot-applications", JSON.stringify(next)); };
  const add = async (event) => {
    event.preventDefault();
    try { const created = await api("/applications", { method: "POST", body: JSON.stringify(form) }); setItems((current) => [...current, created]); }
    catch { persistLocal([...items, { ...form, id: crypto.randomUUID(), created_at: new Date().toISOString() }]); setNotice("Saved locally."); }
    setForm({ title: "", company: "", link: "", status: "applied" }); setAdding(false);
  };
  const advance = async (item) => {
    const index = columns.indexOf(item.status); const status = columns[Math.min(index + 1, columns.length - 1)];
    const next = items.map((entry) => entry.id === item.id ? { ...entry, status } : entry);
    try { await api(`/applications/${item.id}`, { method: "PATCH", body: JSON.stringify({ status }) }); setItems(next); } catch { persistLocal(next); }
  };

  return (
    <div className="page"><div className="page-header"><div><p className="eyebrow">Pipeline</p><h1>Applications</h1><p>Track every role from submission through final outcome.</p></div><button className="button primary" onClick={() => setAdding(true)}><Plus size={17} /> Add application</button></div>
      {notice && <div className="notice">{notice}</div>}
      {adding && <form className="panel inline-form" onSubmit={add}><button type="button" className="icon-button close-form" onClick={() => setAdding(false)}><X /></button><label>Role<input required value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} /></label><label>Company<input required value={form.company} onChange={(event) => setForm({ ...form, company: event.target.value })} /></label><label>Job URL<input type="url" value={form.link} onChange={(event) => setForm({ ...form, link: event.target.value })} /></label><button className="button primary">Save</button></form>}
      <section className="kanban">{columns.map((status) => <div className="kanban-column" key={status}><div className="column-heading"><h2>{status}</h2><span>{items.filter((item) => item.status === status).length}</span></div>{items.filter((item) => item.status === status).map((item) => <article className="application-card" key={item.id}><BriefcaseBusiness size={18} /><h3>{item.title}</h3><p>{item.company}</p>{status !== "rejected" && status !== "offer" && <button className="icon-button advance" title="Move to next stage" onClick={() => advance(item)}><ArrowRight size={16} /></button>}</article>)}{!items.some((item) => item.status === status) && <p className="empty compact">No applications</p>}</div>)}</section>
    </div>
  );
}

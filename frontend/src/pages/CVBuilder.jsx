import { Download, FileText, LoaderCircle, Sparkles } from "lucide-react";
import { useState } from "react";
import ReactMarkdown from "react-markdown";

import { api, download } from "../lib/api";

export default function CVBuilder() {
  const [form, setForm] = useState({ job_title: "", company: "", job_url: "", job_description: "", export_format: "pdf" });
  const [generated, setGenerated] = useState(null);
  const [score, setScore] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const update = (key, value) => setForm((current) => ({ ...current, [key]: value }));

  const generate = async (event) => {
    event.preventDefault(); setBusy(true); setError("");
    try { const result = await api("/cv/generate", { method: "POST", body: JSON.stringify(form) }); setGenerated(result); setScore(result.ats_score || null); }
    catch (requestError) { setError(requestError.message); } finally { setBusy(false); }
  };
  const scoreCV = async () => {
    setBusy(true); setError("");
    try { setScore(await api("/cv/score", { method: "POST", body: JSON.stringify({ markdown: generated.markdown_content, job_description: form.job_description }) })); }
    catch (requestError) { setError(requestError.message); } finally { setBusy(false); }
  };

  return (
    <div className="page"><div className="page-header"><div><p className="eyebrow">Tailored documents</p><h1>CV Builder</h1><p>Generate a focused, ATS-friendly CV from your master profile.</p></div></div>
      <div className="builder-grid">
        <form className="panel generator-form" onSubmit={generate}><h2>Target role</h2><div className="field-grid"><label>Job title<input value={form.job_title} onChange={(event) => update("job_title", event.target.value)} /></label><label>Company<input value={form.company} onChange={(event) => update("company", event.target.value)} /></label></div><label>Job URL<input type="url" value={form.job_url} onChange={(event) => update("job_url", event.target.value)} placeholder="https://..." /></label><label>Job description<textarea required rows="14" value={form.job_description} onChange={(event) => update("job_description", event.target.value)} /></label><button className="button primary full" disabled={busy}>{busy ? <LoaderCircle className="spin" size={17} /> : <Sparkles size={17} />} Generate CV</button>{error && <p className="form-error">{error}</p>}</form>
        <section className="panel preview-panel">
          <div className="panel-heading"><div><p className="eyebrow">Preview</p><h2>{generated?.job_title || "Tailored CV"}</h2></div>{generated?.id && <div className="export-actions">{["pdf","docx","markdown"].map((format) => <button key={format} className="icon-button" title={`Download ${format.toUpperCase()}`} onClick={() => download(`/cv/export/${generated.id}?format=${format}`)}><Download size={17} /></button>)}</div>}</div>
          {generated?.markdown_content ? <div className="markdown-preview"><ReactMarkdown>{generated.markdown_content}</ReactMarkdown></div> : <div className="empty-state"><FileText size={28} /><h2>Your preview will appear here</h2><p>Paste a job description and generate a tailored CV.</p></div>}
        </section>
      </div>
      {generated && <section className="panel score-panel"><div className="score-gauge"><strong>{score?.overall_score ?? "--"}</strong><span>ATS score</span></div><div className="score-content"><div className="panel-heading"><div><p className="eyebrow">Keyword coverage</p><h2>{score ? `${Math.round((score.keyword_match_pct || 0) * 100)}% match` : "Not scored"}</h2></div><button className="button secondary" onClick={scoreCV} disabled={busy}><Sparkles size={16} /> Score CV</button></div><div className="chip-row">{score?.missing_keywords?.slice(0, 10).map((keyword) => <span className="chip warning" key={keyword}>{keyword}</span>)}</div>{score?.improvement_suggestions?.map((suggestion) => <p className="suggestion" key={suggestion}>{suggestion}</p>)}</div></section>}
    </div>
  );
}

import { ExternalLink, Lightbulb, LoaderCircle, Search, Sparkles } from "lucide-react";
import { useState } from "react";

import JobIntelModal from "../components/JobIntelModal";
import { api } from "../lib/api";

export default function JobSearch() {
  const [form, setForm] = useState({
    query: "",
    target_companies: "",
    location_filter: "",
    date_posted_filter: "",
    remote_only: false,
    limit: 30,
  });
  const [results, setResults] = useState(null);
  const [selectedJobIntel, setSelectedJobIntel] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const update = (key, value) => setForm((current) => ({ ...current, [key]: value }));
  const search = async (event) => {
    event.preventDefault(); setBusy(true); setError("");
    try { setResults(await api("/jobs/search", { method: "POST", body: JSON.stringify({ ...form, target_companies: form.target_companies.split("\n").map((value) => value.trim()).filter(Boolean) }) })); }
    catch (requestError) { setError(requestError.message); }
    finally { setBusy(false); }
  };
  const scoreAll = async () => {
    setBusy(true); setError("");
    try {
      const payload = results?.jobs?.length ? { jobs: results.jobs } : {};
      const res = await api("/jobs/score-all", { method: "POST", body: JSON.stringify(payload) });
      setResults(res);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page"><div className="page-header"><div><p className="eyebrow">Opportunity discovery</p><h1>Job search</h1><p>Search career pages and job boards, then rank results against your profile.</p></div></div>
      <form className="panel search-form" onSubmit={search}>
        <label className="grow">Type your job name or role<input required value={form.query} onChange={(event) => update("query", event.target.value)} placeholder="e.g. Marketing Manager, Nurse, Software Engineer, Project Lead" /></label>
        <label>Location<input value={form.location_filter} onChange={(event) => update("location_filter", event.target.value)} placeholder="Europe" /></label>
        <label>Date posted
          <select value={form.date_posted_filter} onChange={(event) => update("date_posted_filter", event.target.value)}>
            <option value="">Anytime</option>
            <option value="24h">Past 24 hours</option>
            <option value="7d">Past week</option>
            <option value="30d">Past month</option>
          </select>
        </label>
        <label className="number-field">Limit<input type="number" min="1" max="150" value={form.limit} onChange={(event) => update("limit", Number(event.target.value))} /></label>
        <label className="checkbox"><input type="checkbox" checked={form.remote_only} onChange={(event) => update("remote_only", event.target.checked)} /> Remote only</label>
        <label className="full-field">Target career pages, one URL per line<textarea rows="2" value={form.target_companies} onChange={(event) => update("target_companies", event.target.value)} placeholder="https://boards.greenhouse.io/company" /></label>
        <button className="button primary" disabled={busy}>{busy ? <LoaderCircle className="spin" size={17} /> : <Search size={17} />} Search</button>
      </form>
      {error && <div className="notice error">{error}</div>}
      <div className="results-heading"><div><h2>{results ? `${results.total_found ?? results.jobs?.length ?? 0} opportunities` : "Results"}</h2>{results?.query && <span className="muted">for {results.query}</span>}</div>{results?.jobs?.length > 0 && <button className="button secondary" onClick={scoreAll} disabled={busy}><Sparkles size={16} /> Score all</button>}</div>
      <section className="job-grid">
        {(results?.jobs || []).map((job) => <article className="job-card" key={job.id || job.link}>
          <div className="job-top">
            <div className="source-badges">
              <span className="source-label">{job.source?.replaceAll("_", " ") || "job"}</span>
              {job.source_platform && <span className="platform-badge">{job.source_platform}</span>}
            </div>
            {job.relevance_score != null && <span className={`score ${job.relevance_score >= 7.5 ? "high" : job.relevance_score >= 5.0 ? "medium" : "low"}`}>{job.relevance_score.toFixed(1)}</span>}
          </div>
          <div className="job-header-row">
            {job.logo_url && <img className="company-logo" src={job.logo_url} alt="" loading="lazy" />}
            <div>
              <h3>{job.title}</h3>
              <p className="company">{job.company || "Company not listed"}</p>
            </div>
          </div>
          <p className="muted">{job.location || "Location not listed"}{job.date_posted ? ` · ${job.date_posted}` : ""}{job.salary ? ` · ${job.salary}` : ""}{job.employment_type ? ` · ${job.employment_type}` : ""}</p>
          <p className="job-summary">{job.summary || "Open the listing to review the full description."}</p>
          {!!job.match_reasons?.length && <div className="reason-list">{job.match_reasons.slice(0, 3).map((reason) => <span key={reason}>{reason}</span>)}</div>}
          <div className="job-footer">
            {job.recommendation && <span className="recommendation">{job.recommendation.replaceAll("_", " ")}</span>}
            <div className="card-actions">
              <button className="button secondary small intel-btn" title="AI Strategic Framing & Intel" onClick={() => setSelectedJobIntel(job)}>
                <Lightbulb size={14} /> AI Intel
              </button>
              <a className="icon-button" title="Open job listing" href={job.link} target="_blank" rel="noreferrer"><ExternalLink size={17} /></a>
            </div>
          </div>
        </article>)}
        {!busy && !results?.jobs?.length && <div className="empty-state"><Search size={26} /><h2>No results yet</h2><p>Run a search to collect matching roles.</p></div>}
      </section>
      {selectedJobIntel && <JobIntelModal job={selectedJobIntel} onClose={() => setSelectedJobIntel(null)} />}
    </div>
  );
}

import { ArrowRight, BriefcaseBusiness, FileText, Search, UserRound } from "lucide-react";
import { Link } from "react-router-dom";

import ProviderStatus from "../components/ProviderStatus";
import { useApi } from "../hooks/useApi";

export default function Dashboard() {
  const profile = useApi("/profile");
  const jobs = useApi("/jobs/results");
  const applications = useApi("/applications");
  const appList = Array.isArray(applications.data) ? applications.data : applications.data?.applications || [];

  return (
    <div className="page">
      <div className="page-header">
        <div><p className="eyebrow">Overview</p><h1>Dashboard</h1><p>Manage your search from one focused workspace.</p></div>
      </div>
      <section className="metric-grid">
        <article className="metric"><Search /><span>Jobs found</span><strong>{jobs.data?.total_found || 0}</strong></article>
        <article className="metric"><BriefcaseBusiness /><span>Applications</span><strong>{appList.length}</strong></article>
        <article className="metric"><FileText /><span>Strong matches</span><strong>{jobs.data?.jobs?.filter((job) => (job.relevance_score || 0) >= 8).length || 0}</strong></article>
      </section>
      <div className="dashboard-grid">
        <section className="panel">
          <div className="panel-heading"><div><p className="eyebrow">Candidate profile</p><h2>{profile.data?.personal_info?.name || "No profile yet"}</h2></div><UserRound /></div>
          <p className="muted clamp">{profile.data?.summary || "Add your experience and skills before starting a tailored search."}</p>
          <div className="chip-row">{Object.values(profile.data?.skills || {}).flat().slice(0, 7).map((skill) => <span className="chip" key={skill}>{skill}</span>)}</div>
          <Link className="text-link" to="/profile">Open profile <ArrowRight size={15} /></Link>
        </section>
        <ProviderStatus />
      </div>
      <section className="panel">
        <div className="panel-heading"><div><p className="eyebrow">Latest search</p><h2>{jobs.data?.query || "No search run"}</h2></div><Link className="button secondary" to="/jobs">Search jobs</Link></div>
        <div className="list-rows">
          {(jobs.data?.jobs || []).slice(0, 4).map((job) => <div className="list-row" key={job.id || job.link}><div><strong>{job.title}</strong><span>{job.company} · {job.location || "Location not listed"}</span></div>{job.relevance_score != null && <span className="score">{job.relevance_score.toFixed(1)}</span>}</div>)}
          {!jobs.loading && !jobs.data?.jobs?.length && <p className="empty">Search results will appear here.</p>}
        </div>
      </section>
    </div>
  );
}

import {
  ArrowRight,
  BriefcaseBusiness,
  Lightbulb,
  Search,
  Star,
  Wand2,
} from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import JobIntelModal from "../components/JobIntelModal";
import ProviderStatus from "../components/ProviderStatus";
import { useApi } from "../hooks/useApi";

export default function Dashboard() {
  const navigate = useNavigate();
  const profile = useApi("/profile");
  const jobs = useApi("/jobs");
  const applications = useApi("/applications");
  const [selectedJobIntel, setSelectedJobIntel] = useState(null);

  const jobList = Array.isArray(jobs.data)
    ? jobs.data
    : jobs.data?.jobs || [];
  const appList = Array.isArray(applications.data)
    ? applications.data
    : applications.data?.applications || [];

  const strongMatches = jobList.filter((j) => (j.relevance_score || 0) >= 7.5);

  const candidateName = profile.data?.personal_info?.name || "Welcome Candidate";
  const candidateTitle = profile.data?.personal_info?.title || "Master Career Profile";
  const allSkills = Object.values(profile.data?.skills || {}).flat().filter(Boolean);

  return (
    <div className="page max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <p className="text-xs uppercase font-bold tracking-wider text-indigo-400">Mission Control</p>
          <h1 className="text-3xl font-extrabold text-white tracking-tight">Overview & Pipeline</h1>
          <p className="text-slate-400 text-sm">
            Monitor matched opportunities, track applications, and optimize your career materials.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Link
            to="/jobs"
            className="inline-flex items-center gap-2 px-4 py-2.5 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-500 rounded-xl shadow-lg shadow-indigo-600/25 transition"
          >
            <Search size={14} /> Search New Jobs
          </Link>
          <Link
            to="/cv"
            className="inline-flex items-center gap-2 px-4 py-2.5 text-xs font-semibold text-slate-200 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-xl transition"
          >
            <Wand2 size={14} /> Tailor CV
          </Link>
        </div>
      </div>

      {/* Metrics Row */}
      <section className="grid grid-cols-1 sm:grid-cols-3 gap-5">
        <article className="p-6 rounded-2xl bg-[#111622] border border-slate-800 flex items-center justify-between shadow-lg">
          <div className="space-y-1">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Saved Opportunities</span>
            <div className="text-3xl font-extrabold text-white">{jobList.length}</div>
          </div>
          <div className="w-12 h-12 rounded-xl bg-blue-500/10 border border-blue-500/20 text-blue-400 flex items-center justify-center">
            <Search size={22} />
          </div>
        </article>

        <article className="p-6 rounded-2xl bg-[#111622] border border-slate-800 flex items-center justify-between shadow-lg">
          <div className="space-y-1">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Strong Matches (&ge; 7.5)</span>
            <div className="text-3xl font-extrabold text-emerald-400">{strongMatches.length}</div>
          </div>
          <div className="w-12 h-12 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center justify-center">
            <Star size={22} className="fill-emerald-400" />
          </div>
        </article>

        <article className="p-6 rounded-2xl bg-[#111622] border border-slate-800 flex items-center justify-between shadow-lg">
          <div className="space-y-1">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Active Pipeline</span>
            <div className="text-3xl font-extrabold text-indigo-400">{appList.length}</div>
          </div>
          <div className="w-12 h-12 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 flex items-center justify-center">
            <BriefcaseBusiness size={22} />
          </div>
        </article>
      </section>

      {/* Profile & Provider Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Candidate Profile Summary */}
        <section className="lg:col-span-7 p-6 rounded-2xl bg-[#111622] border border-slate-800 shadow-lg space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-indigo-600/20 border border-indigo-500/30 text-indigo-300 flex items-center justify-center font-bold">
                {candidateName.charAt(0).toUpperCase()}
              </div>
              <div>
                <h2 className="text-lg font-bold text-white leading-tight">{candidateName}</h2>
                <span className="text-xs text-slate-400">{candidateTitle}</span>
              </div>
            </div>
            <Link
              to="/profile"
              className="text-xs font-semibold text-indigo-400 hover:text-indigo-300 flex items-center gap-1"
            >
              Edit Profile <ArrowRight size={14} />
            </Link>
          </div>

          <p className="text-xs text-slate-300 line-clamp-3 leading-relaxed">
            {profile.data?.summary ||
              "Upload your resume or paste experience in the Profile section to enable dynamic scoring."}
          </p>

          <div>
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              Profile Keywords & Skills
            </span>
            <div className="flex flex-wrap gap-1.5 mt-2">
              {allSkills.length > 0 ? (
                allSkills.slice(0, 8).map((skill) => (
                  <span
                    key={skill}
                    className="px-2.5 py-1 text-xs font-medium rounded-lg bg-slate-900 border border-slate-700/80 text-indigo-200"
                  >
                    {skill}
                  </span>
                ))
              ) : (
                <span className="text-xs text-slate-500">No skills added yet</span>
              )}
            </div>
          </div>
        </section>

        {/* AI & Provider Status Panel */}
        <div className="lg:col-span-5">
          <ProviderStatus />
        </div>
      </div>

      {/* Saved Opportunities Table / List */}
      <section className="p-6 rounded-2xl bg-[#111622] border border-slate-800 shadow-lg space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <div>
            <h2 className="text-lg font-bold text-white">Recent Opportunities</h2>
            <p className="text-xs text-slate-400">Latest discovered and scored roles</p>
          </div>
          <Link
            to="/jobs"
            className="text-xs font-semibold text-indigo-400 hover:text-indigo-300 flex items-center gap-1"
          >
            View All Jobs ({jobList.length}) <ArrowRight size={14} />
          </Link>
        </div>

        <div className="divide-y divide-slate-800/80">
          {jobList.slice(0, 5).map((job) => (
            <div
              key={job.id || job.link}
              className="py-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3"
            >
              <div className="min-w-0 space-y-1">
                <div className="flex items-center gap-2">
                  <strong className="text-sm font-bold text-white hover:text-indigo-300 transition truncate">
                    {job.title}
                  </strong>
                  {job.relevance_score != null && (
                    <span
                      className={`px-2 py-0.5 text-[11px] font-bold rounded-md border ${
                        job.relevance_score >= 7.5
                          ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                          : "bg-slate-800 border-slate-700 text-slate-300"
                      }`}
                    >
                      {job.relevance_score.toFixed(1)} / 10
                    </span>
                  )}
                </div>
                <p className="text-xs text-slate-400 truncate">
                  {job.company} &bull; {job.location || "Location not listed"}
                </p>
              </div>

              <div className="flex items-center gap-2 flex-none">
                <button
                  type="button"
                  onClick={() =>
                    navigate("/cv", {
                      state: {
                        job_title: job.title,
                        company: job.company,
                        job_url: job.link,
                        job_description: job.description || job.summary,
                      },
                    })
                  }
                  className="px-3 py-1.5 text-xs font-bold text-indigo-300 bg-indigo-500/10 hover:bg-indigo-500/20 border border-indigo-500/20 rounded-lg transition"
                >
                  <Wand2 size={13} className="inline mr-1" /> Tailor
                </button>
                <button
                  type="button"
                  onClick={() => setSelectedJobIntel(job)}
                  className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition"
                  title="AI Intel"
                >
                  <Lightbulb size={16} />
                </button>
              </div>
            </div>
          ))}

          {!jobs.loading && !jobList.length && (
            <div className="text-center py-8 text-slate-500 text-xs">
              No saved jobs yet. Search for your role in the Jobs tab!
            </div>
          )}
        </div>
      </section>

      {/* Job Intel Modal */}
      {selectedJobIntel && (
        <JobIntelModal job={selectedJobIntel} onClose={() => setSelectedJobIntel(null)} />
      )}
    </div>
  );
}

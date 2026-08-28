import {
  Briefcase,
  Building2,
  Calendar,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Filter,
  Globe,
  Lightbulb,
  LoaderCircle,
  MapPin,
  Search,
  Sparkles,
  Star,
  Target,
  Wand2,
} from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import JobIntelModal from "../components/JobIntelModal";
import { api } from "../lib/api";

const LIMIT_OPTIONS = [15, 30, 50, 100];

export default function JobSearch() {
  const navigate = useNavigate();
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
  const [scoringBusy, setScoringBusy] = useState(false);
  const [error, setError] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [activeFilterTab, setActiveFilterTab] = useState("all");
  const [sortBy, setSortBy] = useState("score_desc");

  const update = (key, value) => setForm((current) => ({ ...current, [key]: value }));

  const handleSearch = async (event) => {
    if (event) event.preventDefault();
    if (!form.query.trim()) return;

    setBusy(true);
    setError("");

    try {
      const payload = {
        ...form,
        query: form.query.trim(),
        target_companies: form.target_companies
          .split("\n")
          .map((v) => v.trim())
          .filter(Boolean),
      };
      const res = await api("/jobs/search", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setResults(res);
    } catch (err) {
      setError(err.message || "Failed to search jobs. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  const handleScoreAll = async () => {
    if (!results?.jobs?.length) return;
    setScoringBusy(true);
    setError("");

    try {
      const res = await api("/jobs/score-all", {
        method: "POST",
        body: JSON.stringify({ jobs: results.jobs }),
      });
      setResults((prev) => ({
        ...prev,
        jobs: res.jobs,
      }));
    } catch (err) {
      setError(err.message || "Failed to score jobs. Please check your profile.");
    } finally {
      setScoringBusy(false);
    }
  };

  const handleTailorCV = (job) => {
    navigate("/cv", {
      state: {
        job_title: job.title,
        company: job.company || "",
        job_url: job.link || "",
        job_description: job.description || job.summary || "",
      },
    });
  };

  // Filter and sort listings
  const filteredJobs = (results?.jobs || []).filter((job) => {
    if (activeFilterTab === "strong") return (job.relevance_score || 0) >= 7.5;
    if (activeFilterTab === "good") return (job.relevance_score || 0) >= 5.0 && (job.relevance_score || 0) < 7.5;
    if (activeFilterTab === "remote") {
      const loc = (job.location || "").toLowerCase();
      return loc.includes("remote") || job.is_remote;
    }
    return true;
  });

  const sortedJobs = [...filteredJobs].sort((a, b) => {
    if (sortBy === "score_desc") return (b.relevance_score || 0) - (a.relevance_score || 0);
    if (sortBy === "title_asc") return (a.title || "").localeCompare(b.title || "");
    if (sortBy === "company_asc") return (a.company || "").localeCompare(b.company || "");
    return 0;
  });

  return (
    <div className="page max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Header */}
      <div className="space-y-1">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-xs font-semibold">
          <Target size={14} /> Multi-Feed Opportunity Discovery
        </div>
        <h1 className="text-3xl font-extrabold text-white tracking-tight">Job Search & Intelligence</h1>
        <p className="text-slate-400 text-sm max-w-3xl">
          Search live opportunities across Google, Remotive, Jobicy, and company portals. Compare listings against your master profile on a 0.0 to 10.0 ATS relevance scale.
        </p>
      </div>

      {/* Main Search Box Panel */}
      <div className="bg-[#111622] border border-slate-700/60 rounded-2xl p-5 sm:p-7 shadow-xl space-y-5">
        <form onSubmit={handleSearch} className="space-y-4">
          {/* Primary Input Row */}
          <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-center">
            {/* Job Title / Role */}
            <div className="md:col-span-6">
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                Type your job name or role
              </label>
              <div className="flex items-center px-3.5 bg-slate-900/90 border border-slate-700 rounded-xl focus-within:border-indigo-500 transition">
                <Search size={18} className="text-slate-400 flex-none mr-2.5" />
                <input
                  required
                  type="text"
                  value={form.query}
                  onChange={(e) => update("query", e.target.value)}
                  placeholder="e.g. Marketing Manager, Nurse, Software Engineer, Data Lead"
                  className="w-full bg-transparent border-0 outline-none text-sm text-slate-100 placeholder:text-slate-500 py-3 px-0 focus:ring-0 focus:border-0"
                  style={{ border: "none", boxShadow: "none", background: "transparent", padding: "10px 0" }}
                />
              </div>
            </div>

            {/* Location */}
            <div className="md:col-span-4">
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                Location (Optional)
              </label>
              <div className="flex items-center px-3.5 bg-slate-900/90 border border-slate-700 rounded-xl focus-within:border-indigo-500 transition">
                <MapPin size={18} className="text-slate-400 flex-none mr-2.5" />
                <input
                  type="text"
                  value={form.location_filter}
                  onChange={(e) => update("location_filter", e.target.value)}
                  placeholder="e.g. Europe, United States, Remote, London"
                  className="w-full bg-transparent border-0 outline-none text-sm text-slate-100 placeholder:text-slate-500 py-3 px-0 focus:ring-0 focus:border-0"
                  style={{ border: "none", boxShadow: "none", background: "transparent", padding: "10px 0" }}
                />
              </div>
            </div>

            {/* Search Submit Button */}
            <div className="md:col-span-2 pt-6">
              <button
                type="submit"
                disabled={busy || !form.query.trim()}
                className="w-full inline-flex items-center justify-center gap-2 py-3 px-5 text-sm font-bold text-white bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl shadow-lg shadow-indigo-600/30 transition active:scale-[0.98]"
              >
                {busy ? <LoaderCircle size={18} className="animate-spin" /> : <Search size={18} />}
                Search Jobs
              </button>
            </div>
          </div>

          {/* Quick Filters Ribbon */}
          <div className="flex flex-wrap items-center justify-between gap-4 pt-3 border-t border-slate-800/80">
            <div className="flex flex-wrap items-center gap-4 text-xs font-medium text-slate-300">
              {/* Date Filter */}
              <div className="flex items-center gap-2">
                <Calendar size={14} className="text-slate-400" />
                <select
                  value={form.date_posted_filter}
                  onChange={(e) => update("date_posted_filter", e.target.value)}
                  className="px-2.5 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
                >
                  <option value="">Anytime</option>
                  <option value="24h">Past 24 hours</option>
                  <option value="7d">Past week</option>
                  <option value="30d">Past month</option>
                </select>
              </div>

              {/* Limit Pills */}
              <div className="flex items-center gap-1.5">
                <span className="text-slate-400">Limit:</span>
                <div className="inline-flex rounded-lg bg-slate-900 p-0.5 border border-slate-700">
                  {LIMIT_OPTIONS.map((val) => (
                    <button
                      key={val}
                      type="button"
                      onClick={() => update("limit", val)}
                      className={`px-2.5 py-1 rounded-md text-xs font-bold transition ${
                        form.limit === val
                          ? "bg-indigo-600 text-white shadow-sm"
                          : "text-slate-400 hover:text-slate-200"
                      }`}
                    >
                      {val}
                    </button>
                  ))}
                </div>
              </div>

              {/* Remote Only Toggle */}
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={form.remote_only}
                  onChange={(e) => update("remote_only", e.target.checked)}
                  className="w-4 h-4 rounded bg-slate-900 border-slate-700 text-indigo-600 focus:ring-0 cursor-pointer"
                />
                <span className="flex items-center gap-1 text-slate-200">
                  <Globe size={14} className="text-emerald-400" /> Remote only
                </span>
              </label>
            </div>

            {/* Advanced Toggle */}
            <button
              type="button"
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="text-xs text-indigo-300 hover:text-indigo-200 flex items-center gap-1 font-semibold"
            >
              {showAdvanced ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              {showAdvanced ? "Hide direct career URLs" : "+ Add direct career URLs (Greenhouse, Lever)"}
            </button>
          </div>

          {/* Advanced Target URLs Textarea */}
          {showAdvanced && (
            <div className="pt-2 animate-in fade-in duration-150">
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                Target company career boards (one URL per line)
              </label>
              <textarea
                rows={2}
                value={form.target_companies}
                onChange={(e) => update("target_companies", e.target.value)}
                placeholder="https://boards.greenhouse.io/stripe&#10;https://jobs.lever.co/netflix"
                className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-indigo-500 font-mono"
              />
            </div>
          )}
        </form>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-sm flex items-center gap-2">
          <span>⚠️ {error}</span>
        </div>
      )}

      {/* Results Header Toolbar */}
      {results && (
        <div className="space-y-4 pt-2">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 rounded-xl bg-[#0e1422] border border-slate-800">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-lg font-bold text-white">
                  Showing {results.jobs?.length || 0} opportunities
                </span>
                {results.total_found > (results.jobs?.length || 0) && (
                  <span className="text-xs font-medium text-slate-400">
                    ({results.total_found} matching discovered across feeds)
                  </span>
                )}
              </div>
              {results.query && (
                <p className="text-xs text-indigo-300 font-medium">Search: &ldquo;{results.query}&rdquo;</p>
              )}
            </div>

            <div className="flex flex-wrap items-center gap-3">
              {results.jobs?.length > 0 && (
                <button
                  type="button"
                  onClick={handleScoreAll}
                  disabled={scoringBusy || busy}
                  className="inline-flex items-center gap-2 px-4 py-2 text-xs font-bold text-emerald-300 bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/30 rounded-xl shadow-sm transition"
                >
                  {scoringBusy ? <LoaderCircle size={14} className="animate-spin" /> : <Sparkles size={14} />}
                  Match & Score with Profile
                </button>
              )}

              {/* Sort selector */}
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-300 focus:outline-none"
              >
                <option value="score_desc">Highest Match Score</option>
                <option value="title_asc">Job Title (A-Z)</option>
                <option value="company_asc">Company (A-Z)</option>
              </select>
            </div>
          </div>

          {/* Filter Tabs */}
          <div className="flex flex-wrap items-center gap-2 text-xs font-semibold">
            {[
              { id: "all", label: `All (${results.jobs?.length || 0})` },
              { id: "strong", label: `Strong Match ≥ 7.5 (${results.jobs?.filter((j) => (j.relevance_score || 0) >= 7.5).length || 0})` },
              { id: "good", label: `Good Match 5.0–7.4 (${results.jobs?.filter((j) => (j.relevance_score || 0) >= 5.0 && (j.relevance_score || 0) < 7.5).length || 0})` },
              { id: "remote", label: `Remote (${results.jobs?.filter((j) => (j.location || "").toLowerCase().includes("remote") || j.is_remote).length || 0})` },
            ].map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveFilterTab(tab.id)}
                className={`px-3 py-1.5 rounded-lg border transition ${
                  activeFilterTab === tab.id
                    ? "bg-indigo-600/20 border-indigo-500/40 text-indigo-300"
                    : "bg-slate-900/60 border-slate-800 text-slate-400 hover:text-slate-200"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Loading Skeleton */}
      {busy && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {[1, 2, 3, 4, 5, 6].map((idx) => (
            <div key={idx} className="h-56 rounded-2xl bg-slate-900/40 border border-slate-800/80 animate-pulse p-6 space-y-4">
              <div className="h-5 bg-slate-800 rounded w-2/3" />
              <div className="h-4 bg-slate-800/60 rounded w-1/2" />
              <div className="h-16 bg-slate-800/40 rounded w-full" />
              <div className="h-8 bg-slate-800/50 rounded w-full" />
            </div>
          ))}
        </div>
      )}

      {/* Job Cards Grid */}
      {!busy && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {sortedJobs.map((job) => {
            const score = job.relevance_score;
            const hasScore = score != null;
            const isHigh = hasScore && score >= 7.5;
            const isMedium = hasScore && score >= 5.0 && score < 7.5;

            return (
              <article
                key={job.id || job.link}
                className="flex flex-col justify-between p-5 rounded-2xl bg-[#111622] border border-slate-800/90 hover:border-slate-700 transition shadow-lg space-y-4"
              >
                <div className="space-y-3">
                  {/* Top Bar: Source & Score Meter */}
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-1.5">
                      <span className="px-2 py-0.5 rounded-md bg-slate-800 text-[11px] font-semibold text-slate-400 border border-slate-700 capitalize">
                        {job.source?.replaceAll("_", " ") || "job"}
                      </span>
                      {job.source_platform && (
                        <span className="px-2 py-0.5 rounded-md bg-indigo-950 text-[11px] font-semibold text-indigo-300 border border-indigo-800/40 capitalize">
                          {job.source_platform}
                        </span>
                      )}
                    </div>

                    {/* Match Score Badge */}
                    {hasScore ? (
                      <div
                        className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold border ${
                          isHigh
                            ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                            : isMedium
                            ? "bg-amber-500/10 border-amber-500/30 text-amber-400"
                            : "bg-slate-800 border-slate-700 text-slate-400"
                        }`}
                      >
                        <Star size={12} className={isHigh ? "fill-emerald-400" : isMedium ? "fill-amber-400" : ""} />
                        <span>{score.toFixed(1)} / 10 Match</span>
                      </div>
                    ) : (
                      <span className="text-[11px] font-medium text-slate-500">Unscored</span>
                    )}
                  </div>

                  {/* Header: Company Avatar & Job Title */}
                  <div className="flex items-start gap-3">
                    {job.logo_url ? (
                      <img
                        src={job.logo_url}
                        alt=""
                        className="w-10 h-10 rounded-xl object-contain bg-slate-900 border border-slate-800 p-1 flex-none"
                      />
                    ) : (
                      <div className="w-10 h-10 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-center text-slate-400 font-bold text-sm flex-none">
                        {(job.company || "J").charAt(0).toUpperCase()}
                      </div>
                    )}

                    <div className="min-w-0">
                      <h3 className="text-base font-bold text-white hover:text-indigo-300 transition leading-snug line-clamp-2">
                        {job.title}
                      </h3>
                      <p className="text-xs font-medium text-slate-300 mt-0.5 truncate">
                        {job.company || "Company not specified"}
                      </p>
                    </div>
                  </div>

                  {/* Metadata line */}
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-400 pt-1">
                    <span className="flex items-center gap-1">
                      <MapPin size={12} className="text-slate-500" />
                      {job.location || "Location not listed"}
                    </span>
                    {job.date_posted && (
                      <span className="flex items-center gap-1">
                        <Calendar size={12} className="text-slate-500" />
                        {job.date_posted}
                      </span>
                    )}
                    {job.salary && (
                      <span className="px-1.5 py-0.5 rounded bg-emerald-950/60 border border-emerald-800/40 text-emerald-300 text-[11px] font-semibold">
                        {job.salary}
                      </span>
                    )}
                  </div>

                  {/* Summary Clamp */}
                  <p className="text-xs text-slate-300 line-clamp-3 leading-relaxed">
                    {job.summary || job.description || "Review full posting for details and responsibilities."}
                  </p>

                  {/* Matched Keywords Chips */}
                  {!!job.match_reasons?.length && (
                    <div className="flex flex-wrap gap-1.5 pt-1">
                      {job.match_reasons.slice(0, 4).map((kw) => (
                        <span
                          key={kw}
                          className="px-2 py-0.5 text-[11px] font-medium rounded-md bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 flex items-center gap-1"
                        >
                          <CheckCircle2 size={10} /> {kw}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                {/* Card Actions Footer */}
                <div className="pt-4 border-t border-slate-800/80 flex items-center justify-between gap-2">
                  <button
                    type="button"
                    onClick={() => handleTailorCV(job)}
                    className="flex-1 inline-flex items-center justify-center gap-1.5 py-2 px-3 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-500 rounded-xl shadow-md transition"
                  >
                    <Wand2 size={13} /> Tailor CV
                  </button>

                  <button
                    type="button"
                    onClick={() => setSelectedJobIntel(job)}
                    className="p-2 rounded-xl bg-slate-900 border border-slate-700 text-slate-300 hover:text-white hover:border-slate-600 transition"
                    title="AI Strategic Intel"
                  >
                    <Lightbulb size={15} />
                  </button>

                  {job.link && (
                    <a
                      href={job.link}
                      target="_blank"
                      rel="noreferrer"
                      className="p-2 rounded-xl bg-slate-900 border border-slate-700 text-slate-300 hover:text-white hover:border-slate-600 transition"
                      title="Open full job posting"
                    >
                      <ExternalLink size={15} />
                    </a>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      )}

      {/* Empty State */}
      {!busy && !results && (
        <div className="text-center py-16 px-4 rounded-3xl bg-[#111622]/60 border border-slate-800 space-y-4 max-w-2xl mx-auto">
          <div className="w-14 h-14 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 flex items-center justify-center mx-auto">
            <Search size={26} />
          </div>
          <h3 className="text-xl font-bold text-white">Find Opportunities Across Any Industry</h3>
          <p className="text-sm text-slate-400 max-w-md mx-auto">
            Try searching for your job role or click any of the popular careers below to get started:
          </p>
          <div className="flex flex-wrap items-center justify-center gap-2 pt-2">
            {[
              "Marketing Manager",
              "Software Engineer",
              "Registered Nurse",
              "Product Designer",
              "Financial Analyst",
              "Operations Lead",
            ].map((query) => (
              <button
                key={query}
                type="button"
                onClick={() => {
                  update("query", query);
                  setTimeout(() => handleSearch(), 50);
                }}
                className="px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-700 text-xs font-semibold text-slate-300 hover:text-white hover:border-indigo-500 transition"
              >
                + {query}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Job Intel Modal */}
      {selectedJobIntel && (
        <JobIntelModal job={selectedJobIntel} onClose={() => setSelectedJobIntel(null)} />
      )}
    </div>
  );
}

import {
  Briefcase,
  Building2,
  Check,
  Compass,
  Copy,
  HelpCircle,
  Layers,
  Lightbulb,
  LoaderCircle,
  MapPin,
  MessageSquare,
  Sparkles,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";

import { api } from "../lib/api";

export default function JobIntelModal({ job, onClose }) {
  const [intel, setIntel] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [copiedKey, setCopiedKey] = useState("");

  useEffect(() => {
    if (!job) return;

    let active = true;
    const fetchIntel = async () => {
      setLoading(true);
      setError("");
      try {
        const response = await api("/jobs/intelligence", {
          method: "POST",
          body: JSON.stringify({
            job_title: job.title,
            company: job.company || "",
            description: job.description || job.summary || "",
            summary: job.summary || "",
            link: job.link || "",
          }),
        });
        if (active) setIntel(response);
      } catch (err) {
        if (active) setError(err.message || "Failed to generate job intelligence.");
      } finally {
        if (active) setLoading(false);
      }
    };

    fetchIntel();
    return () => {
      active = false;
    };
  }, [job]);

  const copyToClipboard = (text, key) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(""), 2000);
  };

  if (!job) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-150"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-3xl max-h-[90vh] flex flex-col bg-[#111622] border border-slate-700/80 rounded-2xl shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <header className="p-6 border-b border-slate-800 flex items-start justify-between gap-4 bg-[#0e1422]">
          <div className="space-y-1">
            <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-xs font-semibold">
              <Sparkles size={13} /> AI Role Intelligence & Strategic Prep
            </div>
            <h2 className="text-xl font-bold text-white leading-snug">{job.title}</h2>
            <p className="text-xs text-slate-400 flex items-center gap-2">
              <Building2 size={13} className="text-slate-500" />
              <strong className="text-slate-300">{job.company || "Target Company"}</strong>
              {job.location && (
                <span className="flex items-center gap-1">
                  &bull; <MapPin size={11} /> {job.location}
                </span>
              )}
            </p>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition"
            aria-label="Close modal"
          >
            <X size={20} />
          </button>
        </header>

        {/* Modal Body */}
        <div className="flex-1 p-6 overflow-y-auto space-y-5">
          {loading && (
            <div className="py-16 text-center space-y-3">
              <LoaderCircle className="animate-spin text-indigo-400 mx-auto" size={36} />
              <h3 className="text-base font-bold text-white">Synthesizing Strategic Intelligence...</h3>
              <p className="text-xs text-slate-400 max-w-md mx-auto">
                Analyzing role requirements, likely interview stages, talking points, and candidate positioning plan.
              </p>
            </div>
          )}

          {error && (
            <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs font-semibold">
              {error}
            </div>
          )}

          {!loading && intel && (
            <div className="space-y-4">
              {/* 1. Strategic Framing */}
              <section className="p-4 rounded-xl bg-gradient-to-br from-indigo-950/40 to-slate-900 border border-indigo-500/30 space-y-2">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-bold text-indigo-300 flex items-center gap-1.5 uppercase tracking-wider">
                    <Compass size={15} /> How to Frame Your Profile
                  </h3>
                  <button
                    className="text-xs text-slate-400 hover:text-white flex items-center gap-1 font-semibold"
                    title="Copy Framing Strategy"
                    onClick={() => copyToClipboard(intel.framing_strategy, "framing")}
                  >
                    {copiedKey === "framing" ? <Check size={13} className="text-emerald-400" /> : <Copy size={13} />}
                    <span>{copiedKey === "framing" ? "Copied" : "Copy"}</span>
                  </button>
                </div>
                <p className="text-xs text-slate-200 leading-relaxed font-sans">{intel.framing_strategy}</p>
              </section>

              {/* 2. Company & Culture Insights */}
              <section className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2">
                <h3 className="text-xs font-bold text-slate-200 flex items-center gap-1.5 uppercase tracking-wider">
                  <Building2 size={15} className="text-indigo-400" /> Company & Team Insights
                </h3>
                <p className="text-xs text-slate-300 leading-relaxed">{intel.company_insights}</p>
                {intel.culture_notes && (
                  <div className="pt-2 border-t border-slate-800 text-[11px] text-slate-400">
                    <span className="font-semibold text-indigo-300">Culture Markers:</span> {intel.culture_notes}
                  </div>
                )}
              </section>

              {/* 3. Likely Interview Process Stages */}
              {!!intel.interview_stages?.length && (
                <section className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2.5">
                  <h3 className="text-xs font-bold text-slate-200 flex items-center gap-1.5 uppercase tracking-wider">
                    <Layers size={15} className="text-indigo-400" /> Likely Interview Process Stages
                  </h3>
                  <div className="space-y-2">
                    {intel.interview_stages.map((stage, idx) => (
                      <div
                        key={idx}
                        className="flex items-start gap-2.5 p-2 rounded-lg bg-slate-950/60 border border-slate-800/80 text-xs text-slate-200"
                      >
                        <span className="w-5 h-5 rounded-full bg-indigo-600/30 border border-indigo-500/40 text-indigo-300 flex items-center justify-center text-[10px] font-bold flex-none">
                          {idx + 1}
                        </span>
                        <p className="leading-tight pt-0.5">{stage}</p>
                      </div>
                    ))}
                  </div>
                </section>
              )}

              {/* 4. High-Impact Pitch Talking Points */}
              {!!intel.talking_points?.length && (
                <section className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2.5">
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs font-bold text-slate-200 flex items-center gap-1.5 uppercase tracking-wider">
                      <MessageSquare size={15} className="text-emerald-400" /> Key Pitch Talking Points
                    </h3>
                    <button
                      className="text-xs text-slate-400 hover:text-white flex items-center gap-1 font-semibold"
                      title="Copy Talking Points"
                      onClick={() =>
                        copyToClipboard(intel.talking_points.map((tp) => `• ${tp}`).join("\n"), "talking_points")
                      }
                    >
                      {copiedKey === "talking_points" ? (
                        <Check size={13} className="text-emerald-400" />
                      ) : (
                        <Copy size={13} />
                      )}
                      <span>{copiedKey === "talking_points" ? "Copied" : "Copy"}</span>
                    </button>
                  </div>
                  <ul className="space-y-1.5">
                    {intel.talking_points.map((tp, idx) => (
                      <li key={idx} className="text-xs text-slate-300 flex items-start gap-2">
                        <span className="text-emerald-400 font-bold">&bull;</span>
                        <span>{tp}</span>
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {/* 5. High-Leverage Questions to Ask */}
              {!!intel.questions_to_ask?.length && (
                <section className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2.5">
                  <h3 className="text-xs font-bold text-slate-200 flex items-center gap-1.5 uppercase tracking-wider">
                    <HelpCircle size={15} className="text-amber-400" /> High-Leverage Questions to Ask
                  </h3>
                  <ul className="space-y-1.5">
                    {intel.questions_to_ask.map((q, idx) => (
                      <li key={idx} className="text-xs text-slate-300 italic flex items-start gap-2">
                        <span className="text-amber-400 font-bold">&ldquo;</span>
                        <span>{q}&rdquo;</span>
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {/* 6. Key Domain Skills / Technologies */}
              {!!intel.key_technologies?.length && (
                <section className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2">
                  <h3 className="text-xs font-bold text-slate-200 flex items-center gap-1.5 uppercase tracking-wider">
                    <Lightbulb size={15} className="text-indigo-400" /> Core Domain Skills & Keywords
                  </h3>
                  <div className="flex flex-wrap gap-1.5">
                    {intel.key_technologies.map((tech) => (
                      <span
                        key={tech}
                        className="px-2.5 py-1 text-xs font-medium rounded-lg bg-slate-950 border border-slate-700 text-indigo-300"
                      >
                        {tech}
                      </span>
                    ))}
                  </div>
                </section>
              )}
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <footer className="p-4 border-t border-slate-800 flex items-center justify-between gap-3 bg-[#0e1422]">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-xs font-bold text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 rounded-xl transition"
          >
            Close
          </button>
          {job.link && (
            <a
              href={job.link}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-500 rounded-xl shadow-md transition"
            >
              <Briefcase size={14} /> Open Full Job Posting
            </a>
          )}
        </footer>
      </div>
    </div>
  );
}

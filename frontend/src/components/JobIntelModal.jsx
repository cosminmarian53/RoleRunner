import {
  BookOpen,
  Briefcase,
  Building2,
  Check,
  CheckCircle2,
  Compass,
  Copy,
  Download,
  Globe,
  HelpCircle,
  Layers,
  Lightbulb,
  LoaderCircle,
  MapPin,
  MessageSquare,
  Sparkles,
  Target,
  Trophy,
  X,
  Zap,
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

  const exportStudyGuideMarkdown = () => {
    if (!intel) return;
    const content = `# Interview Preparation & Strategic Landing Guide
## ${job.title} — ${job.company || "Target Company"}
${intel.scraped_source ? `*Scraped Source:* ${intel.scraped_source}\n` : ""}
---

### 1. Role Summary
${intel.role_summary || "N/A"}

### 2. Strategic Framing Plan
${intel.framing_strategy || "N/A"}

### 3. Company & Culture Insights
${intel.company_insights || "N/A"}
${intel.culture_notes ? `\n*Culture Notes:* ${intel.culture_notes}\n` : ""}

### 4. 5-Stage Interview Process
${(intel.interview_stages || []).map((st) => `- ${st}`).join("\n")}

### 5. Technical Study Guide
${(intel.study_guide || [])
  .map(
    (sg) => `#### ${sg.topic}
- **Key Concepts:** ${sg.key_concepts}
- **Practice Focus:** ${sg.practice_focus}
`
  )
  .join("\n")}

### 6. Gap-Bridging Improvement Suggestions
${(intel.improvement_suggestions || []).map((s) => `- ${s}`).join("\n")}

### 7. How to Land This Role (Playbook)
${(intel.how_to_land_role || []).map((step) => `- ${step}`).join("\n")}

### 8. Likely Interview Questions & Recommended Answers
${(intel.likely_interview_questions || [])
  .map(
    (q) => `#### Question: "${q.question}"
- **Why They Ask:** ${q.why_they_ask}
- **Recommended Framing:** ${q.recommended_angle}
`
  )
  .join("\n")}

### 9. High-Impact Talking Points
${(intel.talking_points || []).map((tp) => `- ${tp}`).join("\n")}

### 10. Senior Reverse-Interview Questions to Ask
${(intel.questions_to_ask || []).map((q) => `- ${q}`).join("\n")}
`;

    const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `Interview_Prep_${(job.company || "Role").replace(/[^a-zA-Z0-9]/g, "_")}_${(job.title || "Guide").replace(/[^a-zA-Z0-9]/g, "_")}.md`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  if (!job) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-150"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-4xl max-h-[92vh] flex flex-col bg-[#111622] border border-slate-700/80 rounded-2xl shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <header className="p-6 border-b border-slate-800 flex items-start justify-between gap-4 bg-[#0e1422]">
          <div className="space-y-1">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-xs font-semibold">
                <Sparkles size={13} /> AI Role Intelligence & Interview Prep Guide
              </span>
              {intel?.scraped_source && (
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-[11px] font-semibold">
                  <Globe size={11} /> Live Web Scraped
                </span>
              )}
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

          <div className="flex items-center gap-2 flex-none">
            {intel && (
              <button
                type="button"
                onClick={exportStudyGuideMarkdown}
                className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold flex items-center gap-1.5 transition shadow-sm"
                title="Export Interview Preparation Guide as Markdown"
              >
                <Download size={13} /> Export Guide (.md)
              </button>
            )}
            <button
              onClick={onClose}
              className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition"
              aria-label="Close modal"
            >
              <X size={20} />
            </button>
          </div>
        </header>

        {/* Modal Body */}
        <div className="flex-1 p-6 overflow-y-auto space-y-6">
          {loading && (
            <div className="py-16 text-center space-y-3">
              <LoaderCircle className="animate-spin text-indigo-400 mx-auto" size={36} />
              <h3 className="text-base font-bold text-white">Scraping & Processing Role Intelligence...</h3>
              <p className="text-xs text-slate-400 max-w-md mx-auto">
                Gathering live company signals, building your interview study guide, improvement roadmap, and role landing playbook.
              </p>
            </div>
          )}

          {error && (
            <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs font-semibold">
              {error}
            </div>
          )}

          {!loading && intel && (
            <div className="space-y-5">
              {/* 1. Strategic Framing Plan */}
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

              {/* 2. Technical Study & Prep Guide (What to Study) */}
              {!!intel.study_guide?.length && (
                <section className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs font-bold text-sky-300 flex items-center gap-1.5 uppercase tracking-wider">
                      <BookOpen size={15} className="text-sky-400" /> What to Study & Technical Prep Guide
                    </h3>
                    <span className="text-[11px] font-semibold text-slate-400">
                      {intel.study_guide.length} Key Focus Areas
                    </span>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {intel.study_guide.map((item, idx) => (
                      <div
                        key={idx}
                        className="p-3 rounded-xl bg-slate-950/70 border border-slate-800/80 space-y-1.5"
                      >
                        <h4 className="text-xs font-bold text-white flex items-center gap-1.5">
                          <span className="w-4 h-4 rounded-full bg-sky-500/20 text-sky-400 flex items-center justify-center text-[10px]">
                            {idx + 1}
                          </span>
                          {item.topic}
                        </h4>
                        {item.key_concepts && (
                          <p className="text-[11px] text-slate-300 leading-normal">
                            <span className="font-semibold text-slate-400">Concepts:</span> {item.key_concepts}
                          </p>
                        )}
                        {item.practice_focus && (
                          <p className="text-[11px] text-sky-300/90 leading-normal pt-1 border-t border-slate-800/60">
                            <span className="font-semibold text-sky-400">Practice Focus:</span> {item.practice_focus}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                </section>
              )}

              {/* 3. Suggestions on Improvements & Gap Bridging */}
              {!!intel.improvement_suggestions?.length && (
                <section className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs font-bold text-amber-300 flex items-center gap-1.5 uppercase tracking-wider">
                      <Zap size={15} className="text-amber-400" /> Profile Improvement & Alignment Suggestions
                    </h3>
                    <button
                      className="text-xs text-slate-400 hover:text-white flex items-center gap-1 font-semibold"
                      title="Copy Improvements"
                      onClick={() =>
                        copyToClipboard(
                          intel.improvement_suggestions.map((s) => `• ${s}`).join("\n"),
                          "improvements"
                        )
                      }
                    >
                      {copiedKey === "improvements" ? (
                        <Check size={13} className="text-emerald-400" />
                      ) : (
                        <Copy size={13} />
                      )}
                      <span>{copiedKey === "improvements" ? "Copied" : "Copy"}</span>
                    </button>
                  </div>
                  <ul className="space-y-2">
                    {intel.improvement_suggestions.map((sug, idx) => (
                      <li
                        key={idx}
                        className="flex items-start gap-2.5 p-2.5 rounded-lg bg-slate-950/60 border border-slate-800/80 text-xs text-slate-200"
                      >
                        <CheckCircle2 size={14} className="text-amber-400 mt-0.5 flex-none" />
                        <span className="leading-relaxed">{sug}</span>
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {/* 4. How to Land the Role / Interview Playbook */}
              {!!intel.how_to_land_role?.length && (
                <section className="p-4 rounded-xl bg-gradient-to-br from-emerald-950/20 to-slate-900 border border-emerald-500/30 space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs font-bold text-emerald-300 flex items-center gap-1.5 uppercase tracking-wider">
                      <Trophy size={15} className="text-emerald-400" /> How to Land the Role Playbook
                    </h3>
                    <button
                      className="text-xs text-slate-400 hover:text-white flex items-center gap-1 font-semibold"
                      title="Copy Playbook"
                      onClick={() =>
                        copyToClipboard(intel.how_to_land_role.map((step) => step).join("\n\n"), "playbook")
                      }
                    >
                      {copiedKey === "playbook" ? (
                        <Check size={13} className="text-emerald-400" />
                      ) : (
                        <Copy size={13} />
                      )}
                      <span>{copiedKey === "playbook" ? "Copied" : "Copy"}</span>
                    </button>
                  </div>
                  <div className="space-y-2">
                    {intel.how_to_land_role.map((step, idx) => (
                      <div
                        key={idx}
                        className="flex items-start gap-2.5 p-2.5 rounded-lg bg-slate-950/70 border border-emerald-500/20 text-xs text-slate-200"
                      >
                        <Target size={14} className="text-emerald-400 mt-0.5 flex-none" />
                        <span className="leading-relaxed">{step}</span>
                      </div>
                    ))}
                  </div>
                </section>
              )}

              {/* 5. Likely Interview Questions & Recommended Answers */}
              {!!intel.likely_interview_questions?.length && (
                <section className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 space-y-3">
                  <h3 className="text-xs font-bold text-slate-200 flex items-center gap-1.5 uppercase tracking-wider">
                    <HelpCircle size={15} className="text-indigo-400" /> Likely Interview Questions & Model Angles
                  </h3>
                  <div className="space-y-3">
                    {intel.likely_interview_questions.map((qObj, idx) => (
                      <div
                        key={idx}
                        className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80 space-y-2 text-xs"
                      >
                        <div className="font-semibold text-white flex items-start gap-2">
                          <span className="text-indigo-400 font-bold">Q{idx + 1}:</span>
                          <span>{qObj.question}</span>
                        </div>
                        {qObj.why_they_ask && (
                          <p className="text-[11px] text-slate-400 leading-normal pl-5">
                            <span className="text-slate-500 font-medium">Why they ask:</span> {qObj.why_they_ask}
                          </p>
                        )}
                        {qObj.recommended_angle && (
                          <div className="p-2 rounded-lg bg-indigo-950/30 border border-indigo-500/20 text-[11px] text-indigo-200 leading-relaxed ml-5">
                            <span className="font-semibold text-indigo-300">Recommended Angle:</span>{" "}
                            {qObj.recommended_angle}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </section>
              )}

              {/* 6. Company & Culture Insights */}
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

              {/* 7. Likely Interview Process Stages */}
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

              {/* 8. High-Impact Pitch Talking Points */}
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

              {/* 9. High-Leverage Questions to Ask */}
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

              {/* 10. Key Domain Skills / Technologies */}
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

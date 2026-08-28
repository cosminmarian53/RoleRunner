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
            company: job.company,
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
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-content intel-modal" onClick={(e) => e.stopPropagation()}>
        <header className="intel-modal-header">
          <div className="intel-header-title">
            <div className="intel-badge">
              <Sparkles size={16} /> AI Job Intelligence
            </div>
            <h2>{job.title}</h2>
            <p className="company-meta">
              <Building2 size={15} /> <strong>{job.company || "Target Company"}</strong>
              {job.location && <span> · {job.location}</span>}
            </p>
          </div>
          <button className="icon-button" onClick={onClose} aria-label="Close modal">
            <X size={18} />
          </button>
        </header>

        <div className="intel-modal-body">
          {loading && (
            <div className="intel-loading-state">
              <LoaderCircle className="spin" size={32} />
              <h3>Synthesizing Role Intelligence...</h3>
              <p className="muted">
                Analyzing company engineering culture, typical interview stages, and strategic framing for your profile.
              </p>
            </div>
          )}

          {error && (
            <div className="notice error">
              <p>{error}</p>
            </div>
          )}

          {!loading && intel && (
            <div className="intel-sections">
              {/* 1. Strategic Framing */}
              <section className="intel-card highlight-card">
                <div className="intel-card-header">
                  <Compass size={18} />
                  <h3>How to Frame Your Profile</h3>
                  <button
                    className="icon-button small-btn"
                    title="Copy Framing Strategy"
                    onClick={() => copyToClipboard(intel.framing_strategy, "framing")}
                  >
                    {copiedKey === "framing" ? <Check size={14} /> : <Copy size={14} />}
                  </button>
                </div>
                <p className="intel-text">{intel.framing_strategy}</p>
              </section>

              {/* 2. Company & Culture Insights */}
              <section className="intel-card">
                <div className="intel-card-header">
                  <Building2 size={18} />
                  <h3>Company Insights & Culture</h3>
                </div>
                <p className="intel-text">{intel.company_insights}</p>
                {intel.culture_notes && (
                  <div className="culture-chip-box">
                    <span className="culture-label">Culture Markers:</span> {intel.culture_notes}
                  </div>
                )}
              </section>

              {/* 3. Interview Process Stages */}
              {!!intel.interview_stages?.length && (
                <section className="intel-card">
                  <div className="intel-card-header">
                    <Layers size={18} />
                    <h3>Likely Interview Stages & Flow</h3>
                  </div>
                  <div className="stages-timeline">
                    {intel.interview_stages.map((stage, idx) => (
                      <div className="stage-item" key={idx}>
                        <span className="stage-index">{idx + 1}</span>
                        <div className="stage-content">
                          <p>{stage}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </section>
              )}

              {/* 4. High Impact Talking Points */}
              {!!intel.talking_points?.length && (
                <section className="intel-card">
                  <div className="intel-card-header">
                    <MessageSquare size={18} />
                    <h3>Key Pitch Talking Points</h3>
                    <button
                      className="icon-button small-btn"
                      title="Copy Talking Points"
                      onClick={() =>
                        copyToClipboard(intel.talking_points.map((tp) => `• ${tp}`).join("\n"), "talking_points")
                      }
                    >
                      {copiedKey === "talking_points" ? <Check size={14} /> : <Copy size={14} />}
                    </button>
                  </div>
                  <ul className="intel-list">
                    {intel.talking_points.map((tp, idx) => (
                      <li key={idx}>{tp}</li>
                    ))}
                  </ul>
                </section>
              )}

              {/* 5. Strategic Questions to Ask */}
              {!!intel.questions_to_ask?.length && (
                <section className="intel-card">
                  <div className="intel-card-header">
                    <HelpCircle size={18} />
                    <h3>High-Leverage Questions to Ask</h3>
                  </div>
                  <ul className="intel-list questions">
                    {intel.questions_to_ask.map((q, idx) => (
                      <li key={idx}>"{q}"</li>
                    ))}
                  </ul>
                </section>
              )}

              {/* 6. Key Technologies */}
              {!!intel.key_technologies?.length && (
                <section className="intel-card">
                  <div className="intel-card-header">
                    <Lightbulb size={18} />
                    <h3>Key Stacks & Domains</h3>
                  </div>
                  <div className="chip-row">
                    {intel.key_technologies.map((tech) => (
                      <span className="chip" key={tech}>
                        {tech}
                      </span>
                    ))}
                  </div>
                </section>
              )}
            </div>
          )}
        </div>

        <footer className="intel-modal-footer">
          <button className="button secondary" onClick={onClose}>
            Close
          </button>
          {job.link && (
            <a className="button primary" href={job.link} target="_blank" rel="noreferrer">
              <Briefcase size={16} /> Open Job Posting
            </a>
          )}
        </footer>
      </div>
    </div>
  );
}

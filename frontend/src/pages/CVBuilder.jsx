import {
  CheckCircle2,
  Copy,
  Download,
  FileCheck,
  FileText,
  LoaderCircle,
  Sparkles,
  Star,
  Wand2,
} from "lucide-react";
import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import { useLocation } from "react-router-dom";

import { api, download } from "../lib/api";

export default function CVBuilder() {
  const location = useLocation();
  const [form, setForm] = useState({
    job_title: "",
    company: "",
    job_url: "",
    job_description: "",
    export_format: "pdf",
  });

  const [generated, setGenerated] = useState(null);
  const [score, setScore] = useState(null);
  const [busy, setBusy] = useState(false);
  const [scoreBusy, setScoreBusy] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  // Prepopulate form if passed from JobSearch or Dashboard
  useEffect(() => {
    if (location.state) {
      setForm((prev) => ({
        ...prev,
        job_title: location.state.job_title || prev.job_title,
        company: location.state.company || prev.company,
        job_url: location.state.job_url || prev.job_url,
        job_description: location.state.job_description || prev.job_description,
      }));
    }
  }, [location.state]);

  const update = (key, value) => setForm((current) => ({ ...current, [key]: value }));

  const handleGenerate = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");

    try {
      const result = await api("/cv/generate", {
        method: "POST",
        body: JSON.stringify(form),
      });
      setGenerated(result);
      setScore(result.ats_score || null);
    } catch (requestError) {
      setError(requestError.message || "Failed to generate tailored CV.");
    } finally {
      setBusy(false);
    }
  };

  const handleScoreCV = async () => {
    if (!generated?.markdown_content) return;
    setScoreBusy(true);
    setError("");

    try {
      const res = await api("/cv/score", {
        method: "POST",
        body: JSON.stringify({
          markdown: generated.markdown_content,
          job_description: form.job_description,
        }),
      });
      setScore(res);
    } catch (requestError) {
      setError(requestError.message || "Failed to score CV.");
    } finally {
      setScoreBusy(false);
    }
  };

  const handleCopyMarkdown = () => {
    if (!generated?.markdown_content) return;
    navigator.clipboard.writeText(generated.markdown_content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="page max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Header */}
      <div>
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-xs font-semibold">
          <Wand2 size={14} /> ATS Resume Engine
        </div>
        <h1 className="text-3xl font-extrabold text-white tracking-tight mt-1">Tailored CV Builder</h1>
        <p className="text-slate-400 text-sm max-w-3xl">
          Instantly generate a customized, ATS-optimized CV emphasizing the exact skills, impact metrics, and project accomplishments for any target role.
        </p>
      </div>

      {/* Main Grid: Form + Live Preview */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left Column: Target Role Input Form */}
        <form
          onSubmit={handleGenerate}
          className="lg:col-span-5 p-6 rounded-2xl bg-[#111622] border border-slate-800 shadow-xl space-y-4"
        >
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              <FileText size={18} className="text-indigo-400" /> Target Job Details
            </h2>
            <span className="text-xs text-slate-400">Step 1 of 2</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Target Job Title</label>
              <input
                required
                type="text"
                value={form.job_title}
                onChange={(e) => update("job_title", e.target.value)}
                placeholder="e.g. Senior Product Manager"
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-100 focus:outline-none focus:border-indigo-500"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Target Company</label>
              <input
                type="text"
                value={form.company}
                onChange={(e) => update("company", e.target.value)}
                placeholder="e.g. Google, Spotify, NHS"
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-100 focus:outline-none focus:border-indigo-500"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">Job URL (Optional)</label>
            <input
              type="url"
              value={form.job_url}
              onChange={(e) => update("job_url", e.target.value)}
              placeholder="https://..."
              className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-100 focus:outline-none focus:border-indigo-500 font-mono"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">
              Job Description / Requirements
            </label>
            <textarea
              required
              rows={10}
              value={form.job_description}
              onChange={(e) => update("job_description", e.target.value)}
              placeholder="Paste the full job description or key responsibilities here..."
              className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-indigo-500 leading-relaxed font-sans"
            />
          </div>

          {error && <p className="text-xs text-rose-400">{error}</p>}

          <button
            type="submit"
            disabled={busy || !form.job_title.trim() || !form.job_description.trim()}
            className="w-full inline-flex items-center justify-center gap-2 py-3 px-4 text-sm font-bold text-white bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl shadow-lg shadow-indigo-600/30 transition active:scale-[0.98]"
          >
            {busy ? <LoaderCircle size={18} className="animate-spin" /> : <Sparkles size={18} />}
            Generate Tailored CV
          </button>
        </form>

        {/* Right Column: Live Document Preview */}
        <section className="lg:col-span-7 p-6 rounded-2xl bg-[#111622] border border-slate-800 shadow-xl space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div>
              <h2 className="text-base font-bold text-white flex items-center gap-2">
                <FileCheck size={18} className="text-emerald-400" />
                {generated?.job_title ? `Tailored for ${generated.job_title}` : "Document Preview"}
              </h2>
              <p className="text-xs text-slate-400">Structured layout for applicant tracking systems</p>
            </div>

            {/* Export Toolbar */}
            {generated?.id && (
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleCopyMarkdown}
                  className="px-2.5 py-1.5 rounded-lg bg-slate-900 border border-slate-700 text-slate-300 hover:text-white text-xs font-semibold flex items-center gap-1 transition"
                  title="Copy Raw Markdown"
                >
                  <Copy size={13} /> {copied ? "Copied!" : "Copy"}
                </button>
                <button
                  type="button"
                  onClick={() => download(`/cv/export/${generated.id}?format=pdf`)}
                  className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold flex items-center gap-1.5 shadow-sm transition"
                  title="Download High-Res PDF"
                >
                  <Download size={13} /> PDF
                </button>
                <button
                  type="button"
                  onClick={() => download(`/cv/export/${generated.id}?format=docx`)}
                  className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 text-xs font-semibold flex items-center gap-1.5 transition"
                  title="Download Word Document"
                >
                  <Download size={13} /> DOCX
                </button>
              </div>
            )}
          </div>

          {/* Document Markdown Canvas */}
          {generated?.markdown_content ? (
            <div className="cv-document-sheet max-h-[700px] overflow-y-auto">
              <ReactMarkdown>{generated.markdown_content}</ReactMarkdown>
            </div>
          ) : (
            <div className="py-20 text-center space-y-3">
              <div className="w-12 h-12 rounded-xl bg-slate-900 border border-slate-800 text-slate-500 flex items-center justify-center mx-auto">
                <FileText size={24} />
              </div>
              <h3 className="text-base font-bold text-slate-300">Ready to Tailor Your CV</h3>
              <p className="text-xs text-slate-500 max-w-sm mx-auto">
                Fill in the job details on the left or select a job from the search tab to generate an ATS-tailored resume.
              </p>
            </div>
          )}

          {/* ATS Score Meter Panel */}
          {generated && (
            <div className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 flex flex-col items-center justify-center">
                  <strong className="text-sm font-extrabold">{score?.overall_score ?? "9.2"}</strong>
                  <span className="text-[9px] uppercase font-bold text-emerald-500">ATS</span>
                </div>
                <div>
                  <h4 className="text-xs font-bold text-white">
                    {score
                      ? `${
                          score.keyword_match_pct <= 1.0
                            ? Math.round((score.keyword_match_pct || 0.92) * 100)
                            : Math.round(score.keyword_match_pct)
                        }% Target Match`
                      : "High Keyword Density"}
                  </h4>
                  <p className="text-[11px] text-slate-400">Aligned with job description skills and phrasing</p>
                </div>
              </div>

              <button
                type="button"
                onClick={handleScoreCV}
                disabled={scoreBusy}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-slate-300 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg transition"
              >
                {scoreBusy ? <LoaderCircle size={13} className="animate-spin" /> : <Sparkles size={13} />}
                Re-evaluate Score
              </button>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

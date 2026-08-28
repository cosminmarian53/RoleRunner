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
  const [activeStep, setActiveStep] = useState("cv"); // "cv" | "pack"
  const [form, setForm] = useState({
    job_title: "",
    company: "",
    job_url: "",
    job_description: "",
    export_format: "pdf",
    use_ai: true,
  });

  const [generated, setGenerated] = useState(null);
  const [score, setScore] = useState(null);
  const [busy, setBusy] = useState(false);
  const [scoreBusy, setScoreBusy] = useState(false);
  const [fetchBusy, setFetchBusy] = useState(false);
  const [packBusy, setPackBusy] = useState(false);
  const [appPack, setAppPack] = useState(null);
  const [copiedField, setCopiedField] = useState("");
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  const cleanCompany = (name) =>
    (name || "")
      .replace(/\s*(\||-)\s*(Jobs?|Careers?|Wellfound|Lever|Ashby|Greenhouse|Workable|Indeed|SmartRecruiters).*$/i, "")
      .replace(/\s*•\s*.*$/, "")
      .trim();

  const handleFetchUrlDescription = async (targetUrl) => {
    const u = targetUrl || form.job_url;
    if (!u || !u.startsWith("http")) return;
    setFetchBusy(true);
    setError("");

    try {
      const res = await api("/jobs/fetch-description", {
        method: "POST",
        body: JSON.stringify({ url: u }),
      });
      if (res?.description && res.description.length > 50) {
        setForm((prev) => ({
          ...prev,
          job_description: res.description,
        }));
      }
    } catch {
      // Non-blocking fallback
    } finally {
      setFetchBusy(false);
    }
  };

  const handleScanApplicationPack = async () => {
    setPackBusy(true);
    setError("");

    try {
      const res = await api("/applications/scan-form", {
        method: "POST",
        body: JSON.stringify({
          job_url: form.job_url,
          job_title: form.job_title,
          company: form.company,
          notes: form.job_description,
        }),
      });
      setAppPack(res);
      setActiveStep("pack");
    } catch (requestError) {
      setError(requestError.message || "Failed to scan application form.");
    } finally {
      setPackBusy(false);
    }
  };

  const copyToClipboard = (text, fieldName) => {
    navigator.clipboard.writeText(text);
    setCopiedField(fieldName);
    setTimeout(() => setCopiedField(""), 2000);
  };

  // Prepopulate form if passed from JobSearch or Dashboard
  useEffect(() => {
    if (location.state) {
      const initialComp = cleanCompany(location.state.company);
      const initialUrl = location.state.job_url || "";
      const initialDesc = location.state.job_description || "";

      setForm((prev) => ({
        ...prev,
        job_title: location.state.job_title || prev.job_title,
        company: initialComp || prev.company,
        job_url: initialUrl || prev.job_url,
        job_description: initialDesc || prev.job_description,
      }));

      // If description is short (e.g. snippet) and URL exists, auto-fetch full posting
      if (initialUrl && initialDesc.length < 300) {
        handleFetchUrlDescription(initialUrl);
      }
    }
  }, [location.state]);

  const update = (key, value) =>
    setForm((current) => ({
      ...current,
      [key]: key === "company" ? cleanCompany(value) : value,
    }));

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
          markdown_content: generated.markdown_content,
          job_description: form.job_description,
          job_url: form.job_url,
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
      {/* Header with Step Switcher */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-xs font-semibold">
            <Wand2 size={14} /> ATS Application Engine
          </div>
          <h1 className="text-3xl font-extrabold text-white tracking-tight mt-1">Application Studio</h1>
          <p className="text-slate-400 text-sm max-w-3xl">
            Tailor your CV with verified project deliverables and automatically draft answers for every question on the employer's application form.
          </p>
        </div>

        {/* Step Tabs */}
        <div className="inline-flex rounded-xl bg-slate-900/90 p-1 border border-slate-800 flex-none">
          <button
            type="button"
            onClick={() => setActiveStep("cv")}
            className={`px-4 py-2 rounded-lg text-xs font-bold transition flex items-center gap-2 ${
              activeStep === "cv"
                ? "bg-indigo-600 text-white shadow-sm"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <FileText size={14} /> Step 1: Tailored CV
          </button>
          <button
            type="button"
            onClick={() => {
              if (!appPack && (form.job_url || form.job_description)) {
                handleScanApplicationPack();
              } else {
                setActiveStep("pack");
              }
            }}
            className={`px-4 py-2 rounded-lg text-xs font-bold transition flex items-center gap-2 ${
              activeStep === "pack"
                ? "bg-indigo-600 text-white shadow-sm"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <Sparkles size={14} /> Step 2: Form Answers
            <span className="px-1.5 py-0.2 rounded text-[10px] bg-emerald-500/20 text-emerald-400 font-extrabold">Fast Apply</span>
          </button>
        </div>
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
            <div className="flex items-center justify-between mb-1">
              <label className="block text-xs font-semibold text-slate-300">Job URL (Optional)</label>
              {form.job_url && (
                <button
                  type="button"
                  onClick={() => handleFetchUrlDescription(form.job_url)}
                  disabled={fetchBusy}
                  className="text-[11px] font-semibold text-indigo-400 hover:text-indigo-300 flex items-center gap-1 disabled:opacity-50"
                >
                  {fetchBusy ? (
                    <>
                      <LoaderCircle size={12} className="animate-spin" /> Fetching...
                    </>
                  ) : (
                    <>
                      <Sparkles size={12} /> Auto-Fetch Full Posting
                    </>
                  )}
                </button>
              )}
            </div>
            <input
              type="url"
              value={form.job_url}
              onChange={(e) => update("job_url", e.target.value)}
              onBlur={() => {
                if (form.job_url && form.job_description.length < 300) {
                  handleFetchUrlDescription(form.job_url);
                }
              }}
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

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
            <button
              type="submit"
              disabled={busy || !form.job_title.trim() || !form.job_description.trim()}
              className="inline-flex items-center justify-center gap-2 py-3 px-4 text-sm font-bold text-white bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl shadow-lg shadow-indigo-600/30 transition active:scale-[0.98]"
            >
              {busy ? <LoaderCircle size={18} className="animate-spin" /> : <Sparkles size={18} />}
              Generate CV
            </button>

            <button
              type="button"
              onClick={handleScanApplicationPack}
              disabled={packBusy || !form.job_title.trim()}
              className="inline-flex items-center justify-center gap-2 py-3 px-4 text-sm font-bold text-slate-200 bg-slate-800 hover:bg-slate-700 border border-slate-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl transition active:scale-[0.98]"
            >
              {packBusy ? <LoaderCircle size={18} className="animate-spin" /> : <CheckCircle2 size={18} className="text-emerald-400" />}
              Draft Form Answers
            </button>
          </div>
        </form>

        {/* Right Column: Live Document Preview OR Application Pack */}
        {activeStep === "cv" ? (
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

            {/* Next Step Banner */}
            {generated && (
              <div className="p-4 rounded-xl bg-gradient-to-r from-indigo-950/40 to-slate-900 border border-indigo-500/20 flex items-center justify-between gap-4">
                <div>
                  <h4 className="text-xs font-bold text-white">Ready for Application Form?</h4>
                  <p className="text-[11px] text-slate-400">Auto-draft answers for employer custom questions.</p>
                </div>
                <button
                  type="button"
                  onClick={handleScanApplicationPack}
                  disabled={packBusy}
                  className="px-3 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-bold flex items-center gap-1.5 transition"
                >
                  {packBusy ? <LoaderCircle size={13} className="animate-spin" /> : <Sparkles size={13} />}
                  Proceed to Step 2 ➔
                </button>
              </div>
            )}

            {/* ATS Score Meter Panel */}
            {generated && (
              <div className="p-5 rounded-2xl bg-slate-900/90 border border-slate-800 space-y-3">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div className="flex items-center gap-3">
                    <div className="w-14 h-14 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 flex flex-col items-center justify-center flex-none">
                      <strong className="text-base font-extrabold">
                        {score?.overall_score != null ? (score.overall_score / 10).toFixed(1) : "8.5"}
                      </strong>
                      <span className="text-[9px] uppercase font-bold text-emerald-500">/ 10 ATS</span>
                    </div>
                    <div>
                      <h4 className="text-sm font-bold text-white">
                        {score?.overall_score != null
                          ? `${score.overall_score}% Keyword Coverage`
                          : "Strong Profile Match"}
                      </h4>
                      <p className="text-xs text-slate-400">
                        {score?.overall_score != null && score.overall_score >= 70
                          ? "High keyword alignment with target job requirements"
                          : "Consider adding the missing target keywords below"}
                      </p>
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={handleScoreCV}
                    disabled={scoreBusy}
                    className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-bold text-slate-200 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-xl transition flex-none"
                  >
                    {scoreBusy ? <LoaderCircle size={13} className="animate-spin" /> : <Sparkles size={13} />}
                    Re-evaluate Score
                  </button>
                </div>

                {/* Matched / Missing Keyword Chips */}
                {(score?.matched_keywords?.length > 0 || score?.missing_keywords?.length > 0) && (
                  <div className="pt-2 border-t border-slate-800/80 space-y-2">
                    {score.matched_keywords?.length > 0 && (
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className="text-[11px] font-semibold text-emerald-400 mr-1">Matched:</span>
                        {score.matched_keywords.slice(0, 8).map((kw) => (
                          <span
                            key={kw}
                            className="px-2 py-0.5 text-[11px] font-medium rounded-md bg-emerald-500/10 border border-emerald-500/20 text-emerald-300"
                          >
                            ✓ {kw}
                          </span>
                        ))}
                      </div>
                    )}

                    {score.missing_keywords?.length > 0 && (
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className="text-[11px] font-semibold text-amber-400 mr-1">Suggested:</span>
                        {score.missing_keywords.slice(0, 6).map((kw) => (
                          <span
                            key={kw}
                            className="px-2 py-0.5 text-[11px] font-medium rounded-md bg-amber-500/10 border border-amber-500/20 text-amber-300"
                          >
                            + {kw}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </section>
        ) : (
          /* Step 2: Application Answers & Form Pack */
          <section className="lg:col-span-7 p-6 rounded-2xl bg-[#111622] border border-slate-800 shadow-xl space-y-6">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <h2 className="text-base font-bold text-white flex items-center gap-2">
                  <Sparkles size={18} className="text-emerald-400" />
                  Reviewable Application Pack
                </h2>
                <p className="text-xs text-slate-400">Tailored answers ready to copy-paste or submit to the employer</p>
              </div>

              {form.job_url && (
                <a
                  href={form.job_url}
                  target="_blank"
                  rel="noreferrer"
                  className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold flex items-center gap-1 transition"
                >
                  Open Apply Page ↗
                </a>
              )}
            </div>

            {/* Cover Note Card */}
            {appPack?.cover_note && (
              <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-bold text-indigo-400 uppercase tracking-wider">
                    Introductory Cover Note
                  </label>
                  <button
                    type="button"
                    onClick={() => copyToClipboard(appPack.cover_note, "cover_note")}
                    className="text-[11px] font-semibold text-slate-300 hover:text-white flex items-center gap-1"
                  >
                    <Copy size={12} /> {copiedField === "cover_note" ? "Copied!" : "Copy Note"}
                  </button>
                </div>
                <textarea
                  rows={4}
                  value={appPack.cover_note}
                  onChange={(e) => setAppPack((prev) => ({ ...prev, cover_note: e.target.value }))}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 leading-relaxed font-sans focus:outline-none focus:border-indigo-500"
                />
              </div>
            )}

            {/* Custom Employer Questions */}
            <div className="space-y-4">
              <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                Application Form Questions ({appPack?.custom_questions?.length || 0})
              </h3>

              {appPack?.custom_questions?.map((q, idx) => (
                <div key={q.field_id || idx} className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-2">
                  <div className="flex items-start justify-between gap-2">
                    <span className="text-xs font-bold text-slate-200">
                      {q.label} {q.required && <span className="text-rose-400">*</span>}
                    </span>
                    <button
                      type="button"
                      onClick={() => copyToClipboard(q.suggested_answer, q.field_id)}
                      className="text-[11px] font-semibold text-emerald-400 hover:text-emerald-300 flex items-center gap-1 flex-none"
                    >
                      <Copy size={12} /> {copiedField === q.field_id ? "Copied!" : "Copy"}
                    </button>
                  </div>

                  {q.field_type === "textarea" ? (
                    <textarea
                      rows={3}
                      value={q.suggested_answer}
                      onChange={(e) => {
                        const val = e.target.value;
                        setAppPack((prev) => {
                          const updated = [...prev.custom_questions];
                          updated[idx].suggested_answer = val;
                          return { ...prev, custom_questions: updated };
                        });
                      }}
                      className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 leading-relaxed font-sans focus:outline-none focus:border-indigo-500"
                    />
                  ) : (
                    <input
                      type="text"
                      value={q.suggested_answer}
                      onChange={(e) => {
                        const val = e.target.value;
                        setAppPack((prev) => {
                          const updated = [...prev.custom_questions];
                          updated[idx].suggested_answer = val;
                          return { ...prev, custom_questions: updated };
                        });
                      }}
                      className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
                    />
                  )}
                </div>
              ))}
            </div>

            {/* Standard Contact Copy Ribbon */}
            <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-3">
              <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider">Quick Copy Contact Info</h4>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {Object.entries(appPack?.standard_fields || {}).map(([key, val]) => (
                  val ? (
                    <button
                      key={key}
                      type="button"
                      onClick={() => copyToClipboard(val, key)}
                      className="p-2 rounded-lg bg-slate-950 hover:bg-slate-800 border border-slate-800 text-left transition flex items-center justify-between"
                    >
                      <div className="truncate pr-1">
                        <div className="text-[10px] text-slate-400 font-semibold">{key}</div>
                        <div className="text-xs text-slate-200 truncate font-mono">{val}</div>
                      </div>
                      <Copy size={11} className="text-slate-500 flex-none" />
                    </button>
                  ) : null
                ))}
              </div>
            </div>
          </section>
        )}
      </div>
    </div>
  );
}

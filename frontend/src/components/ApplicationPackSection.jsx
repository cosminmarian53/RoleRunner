import { Copy, ExternalLink, Sparkles } from "lucide-react";

export default function ApplicationPackSection({
  appPack,
  setAppPack,
  jobUrl,
  copiedField,
  copyToClipboard,
}) {
  if (!appPack) return null;

  const handleAnswerChange = (idx, val) => {
    setAppPack((prev) => {
      if (!prev || !prev.custom_questions) return prev;
      return {
        ...prev,
        custom_questions: prev.custom_questions.map((q, i) =>
          i === idx ? { ...q, suggested_answer: val } : q
        ),
      };
    });
  };

  return (
    <div className="space-y-6">
      {/* Top Banner & Apply Link */}
      <div className="p-4 rounded-xl bg-indigo-950/30 border border-indigo-500/20 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div>
          <div className="text-xs font-bold text-indigo-400 flex items-center gap-1.5 uppercase tracking-wider">
            <Sparkles size={13} />
            Universal Master Application Pack ({appPack.custom_questions?.length || 0} Questions Ready)
          </div>
          <div className="text-xs text-slate-300 mt-0.5">
            Employer-specific questions and universal application fields drafted directly from your verified profile.
          </div>
        </div>
        {jobUrl && (
          <a
            href={jobUrl}
            target="_blank"
            rel="noreferrer"
            className="px-3.5 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold flex items-center gap-1.5 transition flex-none shadow-md shadow-indigo-500/20"
          >
            Open Apply Page <ExternalLink size={13} />
          </a>
        )}
      </div>

      {/* Cover Note Card */}
      {appPack.cover_note && (
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

      {/* Custom Employer & Master Questions */}
      <div className="space-y-4">
        <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
          Application Form Questions ({appPack.custom_questions?.length || 0})
        </h3>

        {appPack.custom_questions?.map((q, idx) => (
          <div key={q.field_id || idx} className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-2">
            <div className="flex items-start justify-between gap-2">
              <span className="text-xs font-bold text-slate-200">
                {q.label} {q.required && <span className="text-rose-400">*</span>}
              </span>
              <button
                type="button"
                onClick={() => copyToClipboard(q.suggested_answer, q.field_id || `q_${idx}`)}
                className="text-[11px] font-semibold text-emerald-400 hover:text-emerald-300 flex items-center gap-1 flex-none"
              >
                <Copy size={12} /> {copiedField === (q.field_id || `q_${idx}`) ? "Copied!" : "Copy"}
              </button>
            </div>

            {q.field_type === "textarea" ? (
              <textarea
                rows={3}
                value={q.suggested_answer || ""}
                onChange={(e) => handleAnswerChange(idx, e.target.value)}
                className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 leading-relaxed font-sans focus:outline-none focus:border-indigo-500"
              />
            ) : (
              <input
                type="text"
                value={q.suggested_answer || ""}
                onChange={(e) => handleAnswerChange(idx, e.target.value)}
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
          {Object.entries(appPack.standard_fields || {}).map(([key, val]) => (
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
    </div>
  );
}

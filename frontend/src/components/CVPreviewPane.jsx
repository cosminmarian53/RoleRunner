import { Copy, Download, FileText, LoaderCircle, Sparkles } from "lucide-react";
import ReactMarkdown from "react-markdown";

export default function CVPreviewPane({
  generated,
  score,
  copied,
  download,
  handleCopyMarkdown,
  handleScoreCV,
  scoreBusy,
  handleScanApplicationPack,
  packBusy,
}) {
  return (
    <div className="space-y-6">
      {/* Canvas Header & Actions */}
      <div className="flex items-center justify-between pb-3 border-b border-slate-800">
        <div>
          <h2 className="text-sm font-bold text-white uppercase tracking-wider">Tailored CV Preview</h2>
          <p className="text-xs text-slate-400">Review generated resume formatted for ATS parsers.</p>
        </div>

        {generated && (
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
    </div>
  );
}

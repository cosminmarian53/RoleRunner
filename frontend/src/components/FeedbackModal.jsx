import { MessageSquare, Send, Sparkles, Star, ThumbsUp, X } from "lucide-react";
import { useState } from "react";
import { api } from "../lib/api";

export default function FeedbackModal({ isOpen, onClose }) {
  const [rating, setRating] = useState(5);
  const [category, setCategory] = useState("general");
  const [message, setMessage] = useState("");
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!message.trim()) return;
    setBusy(true);
    setError("");

    try {
      await api("/feedback", {
        method: "POST",
        body: JSON.stringify({
          rating,
          category,
          message: message.trim(),
          email: email.trim() || undefined,
          page_url: window.location.href,
        }),
      });
      setSubmitted(true);
      setTimeout(() => {
        setSubmitted(false);
        setMessage("");
        onClose();
      }, 2000);
    } catch (err) {
      setError(err.message || "Failed to send feedback. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-lg p-6 bg-[#111622] border border-slate-700/60 rounded-2xl shadow-2xl shadow-indigo-950/40 text-slate-100">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-1.5 text-slate-400 hover:text-slate-200 rounded-lg hover:bg-slate-800 transition"
          title="Close feedback modal"
        >
          <X size={18} />
        </button>

        {submitted ? (
          <div className="py-8 text-center space-y-3">
            <div className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
              <ThumbsUp size={28} />
            </div>
            <h3 className="text-xl font-bold text-slate-100">Thank You for Your Feedback!</h3>
            <p className="text-sm text-slate-400 max-w-sm mx-auto">
              Your feedback helps us continuously improve RoleRunner for everyone.
            </p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-lg bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                <MessageSquare size={18} />
              </div>
              <div>
                <h3 className="text-lg font-bold text-slate-100">Share Your Feedback</h3>
                <p className="text-xs text-slate-400">Help us make RoleRunner better for all career paths.</p>
              </div>
            </div>

            {/* Star Rating */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">How would you rate your experience?</label>
              <div className="flex items-center gap-2">
                {[1, 2, 3, 4, 5].map((star) => (
                  <button
                    type="button"
                    key={star}
                    onClick={() => setRating(star)}
                    className={`p-2 rounded-xl transition border ${
                      rating >= star
                        ? "bg-amber-500/20 border-amber-500/50 text-amber-400"
                        : "bg-slate-800/60 border-slate-700/50 text-slate-500 hover:text-slate-300"
                    }`}
                  >
                    <Star size={20} className={rating >= star ? "fill-amber-400" : ""} />
                  </button>
                ))}
                <span className="text-xs text-slate-400 ml-2 font-medium">
                  {rating === 5 ? "😍 Fantastic" : rating === 4 ? "🙂 Good" : rating === 3 ? "😐 Neutral" : rating === 2 ? "🙁 Needs Work" : "😡 Poor"}
                </span>
              </div>
            </div>

            {/* Category */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">Topic</label>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700/70 rounded-lg text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
              >
                <option value="general">💬 General Feedback</option>
                <option value="job_search">🔍 Job Search & Results Quality</option>
                <option value="cv_generator">📄 Tailored CV & ATS Optimization</option>
                <option value="bug_report">🐛 Bug Report</option>
                <option value="feature_request">💡 Feature Request / Idea</option>
              </select>
            </div>

            {/* Message */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">Your Thoughts or Suggestions</label>
              <textarea
                required
                rows={4}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="What did you like? What was confusing? What would make this 10x more useful for you?"
                className="w-full px-3 py-2.5 bg-slate-900 border border-slate-700/70 rounded-lg text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-indigo-500"
              />
            </div>

            {/* Email (Optional) */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">Your Email (Optional, for follow up)</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700/70 rounded-lg text-sm text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-indigo-500"
              />
            </div>

            {error && <p className="text-xs text-rose-400">{error}</p>}

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 text-sm text-slate-300 hover:text-white rounded-lg hover:bg-slate-800 transition font-medium"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={busy || !message.trim()}
                className="inline-flex items-center gap-2 px-5 py-2 text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg shadow-lg shadow-indigo-600/30 transition"
              >
                {busy ? <Sparkles size={16} className="animate-spin" /> : <Send size={16} />}
                Send Feedback
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

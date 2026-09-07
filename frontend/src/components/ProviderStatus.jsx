import {
  Bot,
  Check,
  CheckCircle2,
  Copy,
  ExternalLink,
  LoaderCircle,
  LogIn,
  LogOut,
  Zap,
} from "lucide-react";
import { useEffect, useState } from "react";

import { api } from "../lib/api";

export default function ProviderStatus({ compact = false }) {
  const [status, setStatus] = useState(null);
  const [auth, setAuth] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  const checkStatus = async () => {
    try {
      setStatus(await api("/agent/provider/status"));
    } catch (requestError) {
      setError(requestError.message);
    }
  };

  useEffect(() => {
    checkStatus();
  }, []);

  // Poll for login status when device code is displayed
  useEffect(() => {
    if (!auth || status?.authenticated) return undefined;
    const timer = window.setInterval(async () => {
      try {
        const result = await api("/agent/login/status");
        if (result?.authenticated) {
          setStatus((current) => ({ ...current, authenticated: true }));
          setAuth(null);
        }
      } catch {
        // Keep polling while waiting for user authorization
      }
    }, 3000);
    return () => window.clearInterval(timer);
  }, [auth, status?.authenticated]);

  const startLogin = async () => {
    setBusy(true);
    setError("");
    try {
      const res = await api("/agent/login/start", { method: "POST" });
      setAuth(res);
    } catch (requestError) {
      setError(requestError.message || "Failed to initiate ChatGPT login.");
    } finally {
      setBusy(false);
    }
  };

  const disconnectProvider = async () => {
    setBusy(true);
    setError("");
    try {
      await api("/agent/disconnect", { method: "POST" });
      setStatus({ authenticated: false, provider: "codex" });
      setAuth(null);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  };

  const copyCode = () => {
    if (!auth?.device_code) return;
    navigator.clipboard.writeText(auth.device_code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  };

  if (compact) {
    return (
      <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-slate-900 border border-slate-800 text-xs">
        <span
          className={`w-2 h-2 rounded-full ${
            status?.authenticated ? "bg-emerald-400 animate-pulse shadow-sm shadow-emerald-400" : "bg-slate-500"
          }`}
        />
        <span className="font-semibold text-slate-300">
          Codex {status?.authenticated ? "Connected" : "Offline"}
        </span>
      </div>
    );
  }

  return (
    <section className="p-6 rounded-2xl bg-[#111622] border border-slate-800 shadow-lg space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-slate-800">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 flex items-center justify-center">
            <Bot size={18} />
          </div>
          <div>
            <span className="text-[11px] font-bold uppercase tracking-wider text-indigo-400">AI Reasoning Engine</span>
            <h2 className="text-sm font-bold text-white leading-tight">ChatGPT / Codex</h2>
          </div>
        </div>

        {/* Status indicator pill */}
        <div
          className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold border ${
            status?.authenticated
              ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
              : "bg-slate-900 border-slate-700 text-slate-400"
          }`}
        >
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              status?.authenticated ? "bg-emerald-400 animate-pulse" : "bg-slate-500"
            }`}
          />
          <span>{status?.authenticated ? "Connected & Synced" : "Standby"}</span>
        </div>
      </div>

      {/* Connected State */}
      {status?.authenticated ? (
        <div className="space-y-3">
          <div className="p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-xs text-emerald-300 flex items-start gap-2.5">
            <CheckCircle2 size={16} className="text-emerald-400 flex-none mt-0.5" />
            <div className="space-y-0.5">
              <p className="font-semibold text-white">Codex Session Active & Cloud Synced</p>
              <p className="text-slate-400 text-[11px]">
                Your AI session is persisted to PostgreSQL and survives container redeployments automatically.
              </p>
            </div>
          </div>

          <div className="flex items-center justify-between pt-1">
            <span className="text-[11px] text-slate-500">Autonomous reasoning enabled</span>
            <button
              type="button"
              onClick={disconnectProvider}
              disabled={busy}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-slate-400 hover:text-rose-400 bg-slate-900 hover:bg-slate-800 border border-slate-700 rounded-lg transition"
            >
              {busy ? <LoaderCircle size={13} className="animate-spin" /> : <LogOut size={13} />}
              Disconnect Session
            </button>
          </div>
        </div>
      ) : (
        /* Disconnected State */
        <div className="space-y-3">
          {!auth && (
            <>
              <p className="text-xs text-slate-300 leading-relaxed">
                Connect your ChatGPT subscription via standard device authorization. Zero API keys, and session persists across redeploys.
              </p>

              <button
                type="button"
                onClick={startLogin}
                disabled={busy}
                className="w-full inline-flex items-center justify-center gap-2 py-2.5 px-4 text-xs font-bold text-white bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 disabled:opacity-50 rounded-xl shadow-md shadow-indigo-600/20 transition active:scale-[0.98]"
              >
                {busy ? <LoaderCircle size={15} className="animate-spin" /> : <LogIn size={15} />}
                Connect ChatGPT / Codex
              </button>
            </>
          )}

          {/* Active Device Auth Flow Card */}
          {auth && (
            <div className="p-4 rounded-xl bg-gradient-to-br from-indigo-950/40 to-slate-900 border border-indigo-500/30 space-y-3.5 animate-in fade-in duration-200">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-indigo-300 flex items-center gap-1.5">
                  <Zap size={14} className="text-indigo-400" /> One-Time Device Code
                </span>
                <button
                  type="button"
                  onClick={() => setAuth(null)}
                  className="text-[11px] text-slate-400 hover:text-white"
                >
                  Cancel
                </button>
              </div>

              {/* Code Display & 1-Click Copy */}
              <div className="flex items-center justify-between gap-2 p-2.5 rounded-lg bg-slate-950 border border-slate-700/80">
                <span className="font-mono text-base font-extrabold tracking-widest text-emerald-400 pl-1">
                  {auth.device_code || "Waiting..."}
                </span>
                <button
                  type="button"
                  onClick={copyCode}
                  className="inline-flex items-center gap-1 px-3 py-1 text-xs font-bold text-slate-200 bg-slate-800 hover:bg-slate-700 border border-slate-600 rounded-md transition"
                >
                  {copied ? <Check size={13} className="text-emerald-400" /> : <Copy size={13} />}
                  <span>{copied ? "Copied!" : "Copy Code"}</span>
                </button>
              </div>

              {/* Authorize on OpenAI CTA */}
              {(auth.authorization_url || auth.url) && (
                <a
                  href={auth.authorization_url || auth.url}
                  target="_blank"
                  rel="noreferrer"
                  className="w-full inline-flex items-center justify-center gap-2 py-2.5 px-4 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-500 rounded-xl shadow-lg shadow-indigo-600/30 transition"
                >
                  Open OpenAI Sign-In <ExternalLink size={14} />
                </a>
              )}

              {/* Live Polling Status */}
              <div className="flex items-center justify-center gap-2 text-[11px] text-slate-400 pt-1">
                <LoaderCircle size={12} className="animate-spin text-indigo-400" />
                <span>Waiting for your authorization on OpenAI...</span>
              </div>
            </div>
          )}
        </div>
      )}

      {error && <p className="text-xs text-rose-400 pt-1">⚠️ {error}</p>}
    </section>
  );
}

import { Bot, CheckCircle2, Copy, ExternalLink, LoaderCircle, LogIn } from "lucide-react";
import { useEffect, useState } from "react";

import { api } from "../lib/api";

export default function ProviderStatus({ compact = false }) {
  const [status, setStatus] = useState(null);
  const [auth, setAuth] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const checkStatus = async () => {
    try {
      setStatus(await api("/agent/provider-status"));
    } catch (requestError) {
      setError(requestError.message);
    }
  };

  useEffect(() => {
    checkStatus();
  }, []);

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
        // Keep polling while the login flow remains visible.
      }
    }, 3000);
    return () => window.clearInterval(timer);
  }, [auth, status?.authenticated]);

  const startLogin = async () => {
    setBusy(true);
    setError("");
    try {
      setAuth(await api("/agent/login", { method: "POST" }));
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  };

  if (compact) {
    return (
      <div className="provider-compact">
        <span className={`status-dot ${status?.authenticated ? "online" : "offline"}`} />
        <span>Codex {status?.authenticated ? "connected" : "offline"}</span>
      </div>
    );
  }

  return (
    <section className="panel provider-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">AI provider</p>
          <h2>Codex connection</h2>
        </div>
        <Bot size={20} />
      </div>
      {status?.authenticated ? (
        <div className="inline-status success"><CheckCircle2 size={17} /> Ready for searches and CV generation</div>
      ) : (
        <>
          <p className="muted">Connect your Codex session to enable AI-assisted workflows.</p>
          <button className="button primary" onClick={startLogin} disabled={busy}>
            {busy ? <LoaderCircle className="spin" size={17} /> : <LogIn size={17} />}
            Connect Codex
          </button>
        </>
      )}
      {auth && (
        <div className="auth-code">
          <span>Device code</span>
          <strong>{auth.device_code || "Waiting..."}</strong>
          <button className="icon-button" title="Copy code" onClick={() => navigator.clipboard.writeText(auth.device_code || "")}>
            <Copy size={16} />
          </button>
          {(auth.authorization_url || auth.url) && (
            <a className="button secondary" href={auth.authorization_url || auth.url} target="_blank" rel="noreferrer">
              Open sign in <ExternalLink size={15} />
            </a>
          )}
        </div>
      )}
      {error && <p className="form-error">{error}</p>}
    </section>
  );
}

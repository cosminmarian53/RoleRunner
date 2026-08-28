import { ArrowRight, Mail } from "lucide-react";
import { useState } from "react";

export default function Auth({ onContinue }) {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);

  const submit = (event) => {
    event.preventDefault();
    setSent(true);
  };

  return (
    <main className="auth-page">
      <section className="auth-panel">
        <div className="brand-mark large">JB</div>
        <p className="eyebrow">Job-Bot workspace</p>
        <h1>Sign in to continue</h1>
        <p className="muted">Use a magic link to access your private career workspace.</p>
        <form onSubmit={submit}>
          <label>Email address<input required type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@example.com" /></label>
          <button className="button primary full" type="submit"><Mail size={17} /> Send magic link</button>
        </form>
        {sent && <div className="notice">Magic-link delivery will activate when Supabase is configured.</div>}
        <button className="button ghost full" onClick={onContinue}>Continue in local mode <ArrowRight size={17} /></button>
      </section>
    </main>
  );
}

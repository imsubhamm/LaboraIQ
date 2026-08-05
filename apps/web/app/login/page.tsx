"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  Activity, ArrowRight, CheckCircle2, FlaskConical, LockKeyhole,
  Mail, ShieldCheck, Sparkles
} from "lucide-react";
import { storeBrowserAccessToken } from "@/lib/session";

type OidcMetadata = {
  enabled: boolean;
  authorization_endpoint?: string | null;
};

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [oidcEnabled, setOidcEnabled] = useState(false);
  const [reason, setReason] = useState("");

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const nextReason = params.get("reason");
    if (nextReason === "expired") setReason("Your session expired. Please sign in again.");
    else if (nextReason?.startsWith("oidc_")) setReason("Single sign-on failed. Try again or use administrator credentials.");

    const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "/api/v1";
    fetch(`${apiBase}/auth/oidc/metadata`)
      .then(async (response) => {
        if (!response.ok) return;
        const body = (await response.json()) as OidcMetadata;
        setOidcEnabled(Boolean(body.enabled && body.authorization_endpoint));
      })
      .catch(() => undefined);
  }, []);

  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      const response = await fetch("/auth/session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password })
      });
      const body = await response.json().catch(() => ({ detail: "Unable to sign in" }));
      if (!response.ok) throw new Error(body.detail ?? "Unable to sign in");
      if (typeof body.access_token === "string") {
        storeBrowserAccessToken(body.access_token);
      }
      const returnTo = new URLSearchParams(window.location.search).get("returnTo");
      window.location.assign(returnTo?.startsWith("/") ? returnTo : "/dashboard");
    } catch (loginError) {
      setError(loginError instanceof Error ? loginError.message : "Unable to sign in");
    } finally {
      setSubmitting(false);
    }
  }

  function startOidc() {
    const returnTo = new URLSearchParams(window.location.search).get("returnTo");
    const start = new URL("/auth/oidc/start", window.location.origin);
    if (returnTo?.startsWith("/")) start.searchParams.set("returnTo", returnTo);
    window.location.assign(start.toString());
  }

  return (
    <main className="login-page">
      <div className="login-glow login-glow-one"/>
      <div className="login-glow login-glow-two"/>
      <section className="login-shell">
        <div className="login-story">
          <header className="login-brand">
            <div className="brand-mark">LQ</div>
            <div><strong>LaboraIQ</strong><span>Laboratory intelligence platform</span></div>
          </header>

          <div className="login-story-copy">
            <div className="login-badge"><Sparkles size={14}/>Precision at every handoff</div>
            <h1>From patient intake to a traceable result.</h1>
            <p>One controlled workspace for registration, billing, specimen identification, and laboratory operations.</p>
          </div>

          <div className="login-flow" aria-label="Lab workflow">
            <div><span><Activity size={16}/></span><p><b>Register</b><small>Patient & prescription</small></p></div>
            <i><ArrowRight size={14}/></i>
            <div><span><FlaskConical size={16}/></span><p><b>Collect</b><small>Barcode & specimen</small></p></div>
            <i><ArrowRight size={14}/></i>
            <div><span><CheckCircle2 size={16}/></span><p><b>Complete</b><small>Auditable workflow</small></p></div>
          </div>

          <div className="login-trust"><ShieldCheck size={17}/><span><strong>Controlled clinical access</strong>Every administrative action is attributable and traceable.</span></div>
        </div>

        <div className="login-form-side">
          <section className="login-card">
            <div className="login-card-icon"><LockKeyhole size={21}/></div>
            <p className="eyebrow">SECURE WORKSPACE</p>
            <h2>Welcome back</h2>
            <p>{oidcEnabled ? "Sign in with your organization identity provider, or use administrator credentials when enabled." : "Enter your administrator credentials to continue."}</p>
            {reason && <div className="error-state" role="status">{reason}</div>}
            {oidcEnabled && (
              <>
                <button type="button" className="login-sso" onClick={startOidc}>
                  Continue with single sign-on<ArrowRight size={17}/>
                </button>
                <div className="login-or" role="separator">or</div>
              </>
            )}
            <form className="login-form" onSubmit={login}>
              <label>Email address<div className="input-with-icon"><Mail size={17}/><input required type="email" autoComplete="username" value={email} onChange={event => setEmail(event.target.value)} placeholder="name@laboraiq.com"/></div></label>
              <label>Password<div className="input-with-icon"><LockKeyhole size={17}/><input required type="password" autoComplete="current-password" value={password} onChange={event => setPassword(event.target.value)} placeholder="Enter your password"/></div></label>
              {error && <div className="error-state" role="alert">{error}</div>}
              <button type="submit" disabled={submitting}>{submitting ? "Signing in…" : <>Sign in to LaboraIQ<ArrowRight size={17}/></>}</button>
            </form>
            <div className="login-security"><ShieldCheck size={14}/>Encrypted session · Authorized staff only</div>
          </section>
          <p className="login-footer">LaboraIQ Control Centre <span>•</span> Kolkata Laboratory</p>
        </div>
      </section>
    </main>
  );
}

"use client";

export default function LoginPage() {
  function startDevelopmentSession() {
    const expires = Date.now() + 60 * 60 * 1000;
    document.cookie = `labora_session=${expires}; Path=/; SameSite=Lax; Max-Age=3600`;
    window.location.assign("/dashboard");
  }
  return (
    <main className="login-page">
      <section className="login-card">
        <div className="brand-mark">LQ</div>
        <p className="eyebrow">CONTROLLED ACCESS</p>
        <h1>LaboraIQ</h1>
        <p>Laboratory operations, tenant configuration, and traceable access control.</p>
        <button onClick={startDevelopmentSession}>Continue with development identity</button>
        <small>Production identity will use an approved OIDC provider.</small>
      </section>
    </main>
  );
}


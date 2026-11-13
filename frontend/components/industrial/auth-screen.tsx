"use client";

import { useState, FormEvent } from "react";
import { ArrowRight, Activity, Factory, ShieldCheck, Wrench } from "lucide-react";
import { post, Profile } from "../../lib/industrial-api";
import { Field, formValues, text } from "./ui";

export default function AuthScreen({ onSignedIn }: { onSignedIn: (profile: Profile) => void }) {
  const [register, setRegister] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = formValues(event.currentTarget);
    setBusy(true); setError("");
    try {
      onSignedIn(await post<Profile>(`/auth/${register ? "register" : "login"}`, {
        email: text(data, "email"), password: String(data.get("password")),
        ...(register ? { name: text(data, "name"), company_name: text(data, "company_name") } : {}),
      }));
    } catch (err) { setError(err instanceof Error ? err.message : "Sign-in failed"); }
    finally { setBusy(false); }
  }
  return <main className="ix-auth">
    <section className="ix-auth-story"><a className="ix-brand" href="/"><span><Activity size={22} /></span>TelemetryX<small>INDUSTRIAL</small></a>
      <div className="ix-auth-copy"><span className="ix-eyebrow">FROM SIGNAL TO ACTION</span>
        <h1>Know your machines.<br /><em>Own the next move.</em></h1>
        <p>A shared operating picture for the people who keep production moving. Connect equipment, investigate signals, and turn maintenance priorities into accountable work.</p>
        <div className="ix-auth-features"><div><Factory /><span>Every site.<small>A workspace built around your assets.</small></span></div>
          <div><Activity /><span>Every signal.<small>Timestamped telemetry with quality checks.</small></span></div>
          <div><Wrench /><span>Every action.<small>From alert to verified maintenance.</small></span></div></div>
      </div><div className="ix-auth-foot"><ShieldCheck size={16} /> Company workspaces with role-based access</div>
    </section>
    <section className="ix-auth-form"><div className="ix-auth-card"><span className="ix-eyebrow">YOUR OPERATIONS WORKSPACE</span>
      <h2>{register ? "Build your operating picture." : "Welcome back."}</h2>
      <p>{register ? "Create your account and first company workspace. No machinery data is preloaded." : "Sign in to your company's machinery workspace."}</p>
      <div className="ix-segment"><button type="button" className={register ? "active" : ""} onClick={() => { setRegister(true); setError(""); }}>Create workspace</button><button type="button" className={!register ? "active" : ""} onClick={() => { setRegister(false); setError(""); }}>Sign in</button></div>
      <form onSubmit={submit}>
        {register && <><Field label="Your name"><input name="name" autoComplete="name" required maxLength={100} /></Field>
          <Field label="Company name"><input name="company_name" autoComplete="organization" required maxLength={120} /></Field></>}
        <Field label="Work email"><input name="email" type="email" autoComplete="email" required maxLength={254} /></Field>
        <Field label="Password"><input name="password" type="password" autoComplete={register ? "new-password" : "current-password"} minLength={12} maxLength={128} required /></Field>
        <small className="ix-muted">Use at least 12 characters. Sessions use an HttpOnly cookie.</small>
        {error && <p role="alert" className="ix-error">{error}</p>}
        <button className="ix-button ix-button-primary ix-full" disabled={busy}>{busy ? "Please wait..." : register ? "Create my workspace" : "Sign in"}<ArrowRight size={16} /></button>
      </form>
      <div className="ix-auth-demo">Exploring the research prototype? <a href="/demo">Open the synthetic C-MAPSS demo <ArrowRight size={13} /></a></div>
    </div></section>
  </main>;
}

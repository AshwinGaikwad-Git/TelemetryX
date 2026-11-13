"use client";

import { FormEvent, useState } from "react";
import { Audit, IngestionKey, industrialRequest, patch, post, Profile, Role, TeamMember } from "../../lib/industrial-api";
import { Badge, date, Field, formValues, Section, text } from "./ui";

type Run = (operation: () => Promise<unknown>, message?: string) => Promise<void>;
export default function Team({ base, members, keys, events, role, run, busy, onProfile, userId }: {
  base: string; members: TeamMember[]; keys: IngestionKey[]; events: Audit[]; role: Role;
  run: Run; busy: boolean; userId: string; onProfile: (profile: Profile) => void;
}) {
  const [secret, setSecret] = useState<{ label: string; value: string } | null>(null);
  const admin = role === "admin"; const engineering = admin || role === "engineer";
  function invite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const data = formValues(event.currentTarget);
    void run(async () => { const result = await post<{ token: string }>(`${base}/invitations`, { email: text(data, "email"), role: text(data, "role") }); setSecret({ label: "Invitation token (expires in 48 hours). Share privately with the invited person; no email has been sent.", value: result.token }); });
  }
  function join(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const data = formValues(event.currentTarget);
    void run(async () => onProfile(await post<Profile>("/auth/join", { token: text(data, "token") })), "Workspace joined. Select it in the company menu.");
  }
  return <div className="ix-stack">
    {secret && <section className="ix-secret" role="status"><strong>{secret.label}</strong><code>{secret.value}</code><button className="ix-button" onClick={() => setSecret(null)}>I have saved it privately</button></section>}
    <Section eyebrow="PEOPLE & PERMISSIONS" title="Your operating team" detail="Admins manage access; managers plan work; engineers configure monitoring; technicians progress assigned work; viewers inspect.">
      <div className="ix-table-wrap"><table className="ix-table"><thead><tr><th>Name</th><th>Email</th><th>Workspace role</th><th>Access</th></tr></thead><tbody>{members.map(member => <tr key={member.id}><td>{member.name}</td><td>{member.email}</td><td>{admin && member.id !== userId ? <select aria-label={`Role for ${member.name}`} value={member.role} disabled={busy} onChange={event => void run(() => patch(`${base}/members/${member.id}`, { role: event.target.value }), "Member role updated.")}>{["viewer", "technician", "engineer", "manager", "admin"].map(value => <option key={value}>{value}</option>)}</select> : <Badge value={member.role} />}</td><td>{admin && member.id !== userId ? <button className="ix-link" disabled={busy} onClick={() => void run(() => industrialRequest(`${base}/members/${member.id}`, { method: "DELETE" }), "Company access removed. Active work was returned to the planning queue.")}>Remove access</button> : member.id === userId ? "You" : "?"}</td></tr>)}</tbody></table></div>
      {admin && <form onSubmit={invite} className="ix-form-grid ix-inset"><Field label="Invite member email"><input name="email" type="email" required /></Field><Field label="Access role"><select name="role" defaultValue="technician">{["viewer", "technician", "engineer", "manager", "admin"].map(value => <option key={value}>{value}</option>)}</select></Field><div className="ix-form-action"><button className="ix-button ix-button-primary" disabled={busy}>Create private invitation</button></div></form>}
    </Section>
    <Section title="Join another workspace" detail="Sign in with the invited email, then paste the one-time token your administrator shared with you."><form onSubmit={join} className="ix-inline-form"><Field label="Invitation token"><input name="token" required autoComplete="off" minLength={20} maxLength={100} /></Field><button className="ix-button" disabled={busy}>Accept invitation</button></form></Section>
    <Section title="Create another company" detail="A separate company has its own sites, machinery and membership permissions."><form className="ix-inline-form" onSubmit={event => { event.preventDefault(); const data = formValues(event.currentTarget); void run(async () => onProfile(await post<Profile>("/auth/companies", { name: text(data, "name") })), "Company workspace created."); }}><Field label="New company name"><input name="name" required maxLength={120} /></Field><button className="ix-button" disabled={busy}>Create company</button></form></Section>
    {engineering && <Section eyebrow="MACHINE-TO-MACHINE ACCESS" title="Telemetry integrations" detail="Keys can only submit readings to this company. They cannot read dashboards or manage machinery. Tokens are shown once.">
      <form className="ix-inline-form" onSubmit={event => { event.preventDefault(); const data = formValues(event.currentTarget); void run(async () => { const result = await post<{ token: string }>(`${base}/ingestion-keys?name=${encodeURIComponent(text(data, "name"))}`); setSecret({ label: "New ingestion key. Save it in your gateway's secret store; it will not be shown again.", value: result.token }); }); }}><Field label="Integration name"><input name="name" required placeholder="Plant gateway" maxLength={100} /></Field><button className="ix-button" disabled={busy}>Generate ingestion key</button></form>
      <div className="ix-table-wrap"><table className="ix-table"><thead><tr><th>Integration</th><th>Status</th><th>Created</th><th>Action</th></tr></thead><tbody>{keys.map(key => <tr key={key.id}><td>{key.name}</td><td><Badge value={key.active ? "active" : "revoked"} /></td><td>{date(key.created_at)}</td><td>{key.active && <button className="ix-link" disabled={busy} onClick={() => void run(() => post(`${base}/ingestion-keys/${key.id}/revoke`), "Integration key revoked.")}>Revoke key</button>}</td></tr>)}</tbody></table></div>
    </Section>}
    {["admin", "manager", "engineer"].includes(role) && <Section eyebrow="ACCOUNTABILITY" title="Recent audit history" detail="Workspace changes, imports, alerts and maintenance transitions."><div className="ix-table-wrap"><table className="ix-table"><thead><tr><th>Time</th><th>Action</th><th>Actor</th></tr></thead><tbody>{events.map(event => <tr key={event.id}><td>{date(event.created_at)}</td><td>{event.action}</td><td>{members.find(member => member.id === event.actor)?.name || (event.actor.startsWith("integration:") ? "Telemetry integration" : "Workspace member")}</td></tr>)}</tbody></table></div></Section>}
  </div>;
}

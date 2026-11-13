"use client";

import { FormEvent, useState } from "react";
import { Alert, Machine, patch, post, TeamMember, WorkOrder, Role } from "../../lib/industrial-api";
import { Badge, date, Empty, Field, formValues, Section, text } from "./ui";

type Run = (operation: () => Promise<unknown>, message?: string) => Promise<void>;
export default function Maintenance({ base, machines, orders, members, role, userId, run, busy, draft }: {
  base: string; machines: Machine[]; orders: WorkOrder[]; members: TeamMember[]; role: Role;
  userId: string; run: Run; busy: boolean; draft: Alert | null;
}) {
  const [selectedId, setSelectedId] = useState("");
  const selected = orders.find(order => order.id === selectedId);
  const canPlan = ["admin", "manager", "engineer"].includes(role);
  const assignees = members.filter(member => member.role !== "viewer");
  function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget; const data = formValues(form);
    void run(async () => { await post(`${base}/work-orders`, {
      machine_id: text(data, "machine_id"), title: text(data, "title"), description: text(data, "description"),
      priority: text(data, "priority"), assigned_to: text(data, "assigned_to") || null,
      due_at: text(data, "due_at") ? new Date(text(data, "due_at")).toISOString() : null,
      alert_id: draft?.id || null,
    }); form.reset(); }, "Work order created.");
  }
  function update(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!selected) return;
    const data = formValues(event.currentTarget);
    void run(() => patch(`${base}/work-orders/${selected.id}`, {
      status: text(data, "status"), findings: text(data, "findings"), component: text(data, "component"),
      downtime_minutes: Number(data.get("downtime_minutes") || 0),
      ...(canPlan && ["open", "assigned"].includes(selected.status) ? { assigned_to: text(data, "assigned_to") || null } : {}),
    }), "Work order updated. History recorded in the audit log.");
  }
  const next: Record<string, string[]> = { open: ["assigned", "cancelled"], assigned: ["in_progress", "assigned", "cancelled"], in_progress: ["completed", "cancelled"], completed: ["verified", "in_progress"], verified: [], cancelled: [] };
  const options = selected ? (next[selected.status] || []).filter(status => canPlan || (selected.assigned_to === userId && ["in_progress", "completed"].includes(status))) : [];
  return <div className="ix-stack">
    <Section eyebrow="MAINTENANCE OPERATIONS" title="Work that moves equipment forward" detail="Plan, assign, execute and verify. Completion records become your reliability history.">
      <div className="ix-work-stages">{["open", "assigned", "in_progress", "completed", "verified"].map(status => <div key={status}><span>{status.replaceAll("_", " ")}</span><strong>{orders.filter(order => order.status === status).length}</strong></div>)}</div>
      {!orders.length ? <Empty title="Your maintenance board is ready" detail="Create a work order or turn an equipment alert into an inspection." /> : <div className="ix-table-wrap"><table className="ix-table"><thead><tr><th>Work order</th><th>Machine</th><th>Priority</th><th>Status</th><th>Assigned to</th><th>Due</th></tr></thead><tbody>{orders.map(order => <tr key={order.id} onClick={() => setSelectedId(order.id)} className={order.id === selectedId ? "selected" : ""}>
        <td><button className="ix-link" onClick={() => setSelectedId(order.id)}>{order.title}</button></td><td>{machines.find(machine => machine.id === order.machine_id)?.asset_tag || "Machine"}</td><td><Badge value={order.priority} /></td><td><Badge value={order.status} /></td><td>{members.find(member => member.id === order.assigned_to)?.name || "Unassigned"}</td><td>{order.due_at ? date(order.due_at) : "Not set"}</td>
      </tr>)}</tbody></table></div>}
    </Section>
    {selected && <Section title={selected.title} detail={`${selected.status.replaceAll("_", " ")} / ${selected.description || "No additional instructions"}`}>
      {options.length ? <form key={selected.id + selected.status} onSubmit={update} className="ix-form-grid">
        {canPlan && ["open", "assigned"].includes(selected.status) && <Field label="Assign team member"><select name="assigned_to" defaultValue={selected.assigned_to || ""}><option value="">Choose a member</option>{assignees.map(member => <option key={member.id} value={member.id}>{member.name} ({member.role})</option>)}</select></Field>}
        <Field label="Move to"><select name="status">{options.map(status => <option key={status} value={status}>{status.replaceAll("_", " ")}</option>)}</select></Field>
        <Field label="Inspection / repair findings"><textarea name="findings" defaultValue={selected.findings} maxLength={5000} placeholder="What was inspected, what failed, and what work was performed?" /></Field>
        <Field label="Component involved"><input name="component" defaultValue={selected.component} maxLength={120} /></Field>
        <Field label="Recorded downtime (minutes)"><input name="downtime_minutes" type="number" min={0} max={10000000} defaultValue={selected.downtime_minutes} /></Field>
        <div className="ix-form-action"><button className="ix-button ix-button-primary" disabled={busy}>Save work progress</button></div>
      </form> : <p className="ix-note">{selected.findings || "No findings recorded."} Recorded downtime: {selected.downtime_minutes} minutes. {role === "technician" && selected.assigned_to !== userId ? "This work is assigned to another member." : "No transitions available for your role."}</p>}
    </Section>}
    {canPlan && <Section eyebrow="PLAN AN ACTION" title={draft ? "Create work from this alert" : "Create a work order"} detail={draft?.title}>
      <form key={draft?.id || "new"} onSubmit={create} className="ix-form-grid">
        <Field label="Machine"><select name="machine_id" required defaultValue={draft?.machine_id || ""} disabled={!!draft}><option value="">Select machine</option>{machines.map(machine => <option key={machine.id} value={machine.id}>{machine.asset_tag} / {machine.name}</option>)}</select>{draft && <input type="hidden" name="machine_id" value={draft.machine_id} />}</Field>
        <Field label="Work title"><input name="title" defaultValue={draft ? `Inspect: ${draft.title}` : ""} maxLength={180} required /></Field>
        <Field label="Priority"><select name="priority" defaultValue="medium"><option>low</option><option>medium</option><option>high</option><option>critical</option></select></Field>
        <Field label="Assign to"><select name="assigned_to"><option value="">Assign later</option>{assignees.map(member => <option key={member.id} value={member.id}>{member.name}</option>)}</select></Field>
        <Field label="Due date (your local time)"><input name="due_at" type="datetime-local" /></Field>
        <Field label="Instructions"><textarea name="description" maxLength={5000} /></Field>
        <div className="ix-form-action"><button className="ix-button ix-button-primary" disabled={busy || !machines.length}>Create work order</button></div>
      </form>
    </Section>}
  </div>;
}

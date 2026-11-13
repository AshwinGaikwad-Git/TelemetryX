"use client";

import { FormEvent } from "react";
import { Machine, post, Site } from "../../lib/industrial-api";
import { Field, formValues, optionalNumber, Section, text } from "./ui";

type Run = (operation: () => Promise<unknown>, message?: string) => Promise<void>;

export function SiteForm({ base, run, busy }: { base: string; run: Run; busy: boolean }) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget; const values = formValues(form);
    void run(async () => { await post(`${base}/sites`, { name: text(values, "name"), location: text(values, "location"), timezone: text(values, "timezone") }); form.reset(); }, "Site registered.");
  }
  return <Section eyebrow="01 / ORGANIZE" title="Register a site" detail="Keep machinery grouped by plant, facility or operating location.">
    <form onSubmit={submit} className="ix-form-grid">
      <Field label="Site name"><input name="name" placeholder="e.g. Pune manufacturing plant" required maxLength={120} /></Field>
      <Field label="Location"><input name="location" placeholder="City or facility address" maxLength={200} /></Field>
      <Field label="Site timezone"><input name="timezone" defaultValue="Asia/Kolkata" required placeholder="Asia/Kolkata" /></Field>
      <div className="ix-form-action"><button className="ix-button ix-button-primary" disabled={busy}>Add site</button></div>
    </form>
  </Section>;
}

export function MachineForm({ base, sites, run, busy }: { base: string; sites: Site[]; run: Run; busy: boolean }) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget; const data = formValues(form);
    const keys = ["site_id", "asset_tag", "name", "equipment_type", "manufacturer", "model", "area", "criticality", "operating_state", "notes"];
    void run(async () => { await post(`${base}/machines`, Object.fromEntries(keys.map(key => [key, text(data, key)]))); form.reset(); }, "Machine registered. Add sensors to connect its readings.");
  }
  return <Section eyebrow="02 / REGISTER" title="Add machinery" detail="Give each physical asset a permanent tag and an operating context.">
    <form onSubmit={submit} className="ix-form-grid">
      <Field label="Site"><select name="site_id" required><option value="">Select a site</option>{sites.map(site => <option key={site.id} value={site.id}>{site.name}</option>)}</select></Field>
      <Field label="Asset tag"><input name="asset_tag" placeholder="PUMP-001" pattern="[A-Za-z0-9_-]+" maxLength={60} required /></Field>
      <Field label="Machine name"><input name="name" placeholder="Cooling water pump" maxLength={120} required /></Field>
      <Field label="Equipment category"><input name="equipment_type" list="equipment-types" placeholder="Pump, motor, compressor..." maxLength={80} required /><datalist id="equipment-types"><option>Pump</option><option>Motor</option><option>Compressor</option><option>CNC machine</option><option>Conveyor</option></datalist></Field>
      <Field label="Manufacturer"><input name="manufacturer" maxLength={100} /></Field><Field label="Model"><input name="model" maxLength={100} /></Field>
      <Field label="Area / production line"><input name="area" maxLength={100} /></Field>
      <Field label="Production criticality"><select name="criticality" defaultValue="medium"><option>low</option><option>medium</option><option>high</option><option>critical</option></select></Field>
      <Field label="Operating state"><select name="operating_state" defaultValue="stopped"><option>stopped</option><option>running</option><option>idle</option><option>maintenance</option></select></Field>
      <Field label="Maintenance context / notes"><textarea name="notes" maxLength={5000} placeholder="Inspection requirements, responsible team, operating context..." /></Field>
      <div className="ix-form-action"><button className="ix-button ix-button-primary" disabled={busy || sites.length === 0}>Register machine</button></div>
    </form>
  </Section>;
}

export function SensorForm({ base, machine, run, busy }: { base: string; machine: Machine; run: Run; busy: boolean }) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget; const data = formValues(form);
    void run(async () => { await post(`${base}/machines/${machine.id}/sensors`, {
      key: text(data, "key"), name: text(data, "name"), unit: text(data, "unit"),
      expected_interval_seconds: Number(data.get("interval")), persistence_samples: Number(data.get("persistence")),
      valid_min: optionalNumber(data, "valid_min"), valid_max: optionalNumber(data, "valid_max"),
      warning_low: optionalNumber(data, "warning_low"), warning_high: optionalNumber(data, "warning_high"),
    }); form.reset(); }, "Sensor registered. Import readings to begin monitoring.");
  }
  return <Section eyebrow="03 / CONNECT" title={`Add a sensor to ${machine.asset_tag}`} detail="Set units and engineering-reviewed limits. Stale readings never count as healthy.">
    <form onSubmit={submit} className="ix-form-grid">
      <Field label="Sensor key"><input name="key" placeholder="bearing_temperature" pattern="[a-z][a-z0-9_]*" maxLength={60} required /></Field>
      <Field label="Display name"><input name="name" placeholder="Bearing temperature" maxLength={100} required /></Field>
      <Field label="Measurement unit"><input name="unit" placeholder="degC, mm/s, bar..." maxLength={30} required /></Field>
      <Field label="Expected interval (seconds)"><input name="interval" type="number" min={1} max={86400} defaultValue={60} required /></Field>
      <Field label="Valid minimum"><input name="valid_min" type="number" step="any" placeholder="Optional measurement range" /></Field>
      <Field label="Valid maximum"><input name="valid_max" type="number" step="any" /></Field>
      <Field label="Warning below"><input name="warning_low" type="number" step="any" /></Field>
      <Field label="Warning above"><input name="warning_high" type="number" step="any" /></Field>
      <Field label="Consecutive samples for alert"><input name="persistence" type="number" min={1} max={100} defaultValue={3} required /></Field>
      <div className="ix-form-action"><button className="ix-button ix-button-primary" disabled={busy}>Add sensor</button></div>
    </form>
  </Section>;
}

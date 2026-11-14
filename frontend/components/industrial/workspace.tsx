"use client";

import { ChangeEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Activity, ArrowRight, Bell, Building2, ChevronRight, Database, Factory, LayoutDashboard, LogOut, Plus, RefreshCw, Search, Settings2, ShieldCheck, Users, Wrench } from "lucide-react";
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Alert, ApiError, Audit, ImportReport, industrialRequest, IngestionKey, Machine, patch, post, Profile, Site, Summary, TeamMember, WorkOrder } from "../../lib/industrial-api";
import AuthScreen from "./auth-screen";
import { MachineForm, SensorForm, SiteForm } from "./asset-forms";
import Maintenance from "./maintenance";
import Team from "./team";
import Predictive from "./predictive";
import { Badge, date, Empty, Section } from "./ui";

type Tab = "overview" | "machines" | "alerts" | "maintenance" | "data" | "team";
const navigation = [
  { id: "overview", label: "Operations overview", icon: LayoutDashboard },
  { id: "machines", label: "Machinery", icon: Factory },
  { id: "alerts", label: "Alert inbox", icon: Bell },
  { id: "maintenance", label: "Maintenance", icon: Wrench },
  { id: "data", label: "Data connections", icon: Database },
  { id: "team", label: "Team & access", icon: Users },
] as const;
const headings: Record<Tab, [string, string]> = {
  overview: ["Your operating picture.", "Equipment condition, connectivity and the work that needs your attention."],
  machines: ["Every asset. In context.", "Organize equipment, define its signals and investigate its condition."],
  alerts: ["Signals that need a decision.", "Review sustained threshold breaches and move investigations into maintenance."],
  maintenance: ["Keep the next action moving.", "Clear ownership and a complete record from inspection to verification."],
  data: ["Connect with confidence.", "Bring in timestamped readings, verify their quality and monitor connectivity."],
  team: ["Built around your team.", "Manage workspace membership, integration credentials and accountability."],
};

export default function IndustrialWorkspace() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [booting, setBooting] = useState(true);
  const [companyId, setCompanyId] = useState("");
  const [siteId, setSiteId] = useState("");
  const [tab, setTab] = useState<Tab>("overview");
  const [sites, setSites] = useState<Site[]>([]);
  const [machines, setMachines] = useState<Machine[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [orders, setOrders] = useState<WorkOrder[]>([]);
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [keys, setKeys] = useState<IngestionKey[]>([]);
  const [events, setEvents] = useState<Audit[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [sensorKey, setSensorKey] = useState("");
  const [series, setSeries] = useState<{ timestamp: string; value: number }[]>([]);
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [showSetup, setShowSetup] = useState(false);
  const [draft, setDraft] = useState<Alert | null>(null);
  const [report, setReport] = useState<ImportReport | null>(null);
  const [upload, setUpload] = useState<File | null>(null);
  const sequence = useRef(0);
  const company = profile?.companies.find(entry => entry.id === companyId);
  const role = company?.role || "viewer";
  const canEdit = ["admin", "manager", "engineer"].includes(role);
  const canConfigure = ["admin", "engineer"].includes(role);
  const base = `/companies/${companyId}`;
  const machine = machines.find(item => item.id === selectedId) || null;
  const sensor = machine?.sensors.find(item => item.key === sensorKey) || machine?.sensors[0];
  const scopedIds = useMemo(() => new Set(machines.map(item => item.id)), [machines]);
  const scopedAlerts = alerts.filter(item => scopedIds.has(item.machine_id));
  const scopedOrders = orders.filter(item => scopedIds.has(item.machine_id));

  const signedIn = useCallback((next: Profile) => {
    setProfile(next);
    setCompanyId(current => next.companies.some(item => item.id === current) ? current : next.companies[0]?.id || "");
  }, []);

  useEffect(() => {
    industrialRequest<Profile>("/auth/me").then(signedIn).catch(err => {
      if (!(err instanceof ApiError && err.status === 401)) setError(err.message);
    }).finally(() => setBooting(false));
  }, [signedIn]);

  const refresh = useCallback(async () => {
    if (!companyId) return;
    const request = ++sequence.current;
    setLoading(true);
    const scoped = siteId ? `?site_id=${encodeURIComponent(siteId)}` : "";
    try {
      const [siteList, machineList, overview, alertList, workList, team, audit, integrations] = await Promise.all([
        industrialRequest<Site[]>(`${base}/sites`), industrialRequest<Machine[]>(`${base}/machines${scoped}`),
        industrialRequest<Summary>(`${base}/summary${scoped}`), industrialRequest<Alert[]>(`${base}/alerts`),
        industrialRequest<WorkOrder[]>(`${base}/work-orders`), industrialRequest<TeamMember[]>(`${base}/members`),
        canEdit ? industrialRequest<Audit[]>(`${base}/audit`) : Promise.resolve([]),
        canConfigure ? industrialRequest<IngestionKey[]>(`${base}/ingestion-keys`) : Promise.resolve([]),
      ]);
      if (request !== sequence.current) return;
      setSites(siteList); setMachines(machineList); setSummary(overview); setAlerts(alertList);
      setOrders(workList); setMembers(team); setEvents(audit); setKeys(integrations);
      setSelectedId(current => machineList.some(item => item.id === current) ? current : machineList[0]?.id || "");
      setLastUpdated(new Date().toISOString()); setError("");
    } catch (err) {
      if (request !== sequence.current) return;
      if (err instanceof ApiError && err.status === 401) { setProfile(null); setCompanyId(""); }
      setError(err instanceof Error ? err.message : "Workspace could not be loaded");
    } finally { if (request === sequence.current) setLoading(false); }
  }, [companyId, base, siteId, canEdit, canConfigure]);

  useEffect(() => {
    void refresh();
    const interval = setInterval(() => { if (!document.hidden) void refresh(); }, 15000);
    return () => { clearInterval(interval); sequence.current++; };
  }, [refresh]);

  useEffect(() => {
    setSeries([]);
    if (!selectedId || !sensor?.key) return;
    let cancelled = false;
    industrialRequest<{ timestamp: string; value: number }[]>(`${base}/machines/${selectedId}/readings?sensor_key=${encodeURIComponent(sensor.key)}`).then(rows => {
      if (!cancelled) setSeries(rows);
    }).catch(err => { if (!cancelled) setError(err.message); });
    return () => { cancelled = true; };
  }, [base, selectedId, sensor?.key, lastUpdated]);

  async function run(operation: () => Promise<unknown>, message = "") {
    setBusy(true); setError(""); setNotice("");
    try { await operation(); if (message) setNotice(message); await refresh(); }
    catch (err) {
      if (err instanceof ApiError && err.status === 401) { setProfile(null); setCompanyId(""); }
      setError(err instanceof Error ? err.message : "Action failed");
    } finally { setBusy(false); }
  }
  function changeCompany(event: ChangeEvent<HTMLSelectElement>) {
    sequence.current++; setCompanyId(event.target.value); setSiteId(""); setSelectedId("");
    setMachines([]); setSites([]); setSummary(null); setAlerts([]); setOrders([]); setMembers([]);
    setKeys([]); setEvents([]); setSeries([]); setReport(null); setUpload(null); setDraft(null);
    setNotice(""); setError(""); setLastUpdated(null); setTab("overview");
  }
  function inspectMachine(id: string) { setSelectedId(id); setSensorKey(""); setTab("machines"); setShowSetup(false); }
  function workFromAlert(alert: Alert) { setDraft(alert); setTab("maintenance"); }
  async function importFile() {
    if (!machine || !upload) return;
    const body = new FormData(); body.set("file", upload);
    await run(async () => setReport(await industrialRequest<ImportReport>(`${base}/machines/${machine.id}/imports`, { method: "POST", body })), "Import processed. Review accepted, duplicate and rejected rows below.");
  }
  function downloadTemplate() {
    const selected = machine?.sensors[0];
    const content = "sensor_key,timestamp,value,unit\n" + `${selected?.key || "bearing_temperature"},${new Date().toISOString()},${selected?.latest?.value ?? "REPLACE_WITH_READING"},${selected?.unit || "degC"}\n`;
    const url = URL.createObjectURL(new Blob([content], { type: "text/csv" }));
    const anchor = document.createElement("a"); anchor.href = url; anchor.download = "telemetry-template.csv"; anchor.click(); URL.revokeObjectURL(url);
  }

  if (booting) return <div className="ix-loading"><Activity /><p>Opening your operations workspace...</p></div>;
  if (!profile) return <><AuthScreen onSignedIn={signedIn} />{error && <div className="ix-connection-error" role="alert">{error}. Check the backend connection and try again.</div>}</>;
  const filtered = machines.filter(item => `${item.asset_tag} ${item.name} ${item.equipment_type}`.toLowerCase().includes(search.toLowerCase()));

  const machineTable = <div className="ix-table-wrap"><table className="ix-table"><thead><tr><th>Machine</th><th>Site / area</th><th>Condition</th><th>Connection</th><th>Operating state</th><th>Last reading</th><th>Last RUL estimate</th></tr></thead><tbody>{filtered.map(item => <tr key={item.id} className={item.id === selectedId && tab === "machines" ? "selected" : ""}>
    <td><button className="ix-asset-link" onClick={() => inspectMachine(item.id)}><span className="ix-machine-icon"><Factory size={18} /></span><span><strong>{item.name}</strong><small>{item.asset_tag} / {item.equipment_type}</small></span><ChevronRight size={15} /></button></td>
    <td>{sites.find(site => site.id === item.site_id)?.name}<small className="ix-cell-detail">{item.area || "No area assigned"}</small></td><td><Badge value={item.health} /></td><td><Badge value={item.connectivity} /></td><td>{item.operating_state}</td><td className="ix-cell-time">{date(item.last_seen)}</td><td>{item.last_prediction ? <><span>{item.last_prediction.remaining_hours.toFixed(1)} h / experimental</span><small className="ix-cell-detail">Observed {date(item.last_prediction.observed_at)}</small></> : <span className="ix-cell-detail">Model and readings required</span>}</td>
  </tr>)}</tbody></table></div>;

  return <div className="industrial-shell">
    <aside className="ix-sidebar"><a className="ix-brand" href="/"><span><Activity size={21} /></span>TelemetryX<small>INDUSTRIAL</small></a>
      <div className="ix-workspace-select"><Building2 size={16} /><label><span>COMPANY WORKSPACE</span><select aria-label="Company workspace" value={companyId} onChange={changeCompany}>{profile.companies.map(entry => <option key={entry.id} value={entry.id}>{entry.name}</option>)}</select></label></div>
      <div className="ix-nav-label">OPERATIONS</div><nav aria-label="Industrial navigation">{navigation.map(item => <button key={item.id} aria-label={item.label} title={item.label} className={tab === item.id ? "active" : ""} onClick={() => { setTab(item.id); setNotice(""); if (item.id !== "maintenance") setDraft(null); }}><item.icon size={18} /><span>{item.label}</span>{item.id === "alerts" && !!summary?.active_alerts && <b>{summary.active_alerts}</b>}</button>)}</nav>
      <div className="ix-sidebar-bottom"><div className="ix-pilot-label"><ShieldCheck size={15} /><span>Industrial pilot<small>Threshold monitoring enabled</small></span></div><a className="ix-demo-link" href="/demo">Research demo <ArrowRight size={14} /></a><div className="ix-user"><span>{profile.name.slice(0, 2).toUpperCase()}</span><div><strong>{profile.name}</strong><small>{role}</small></div><button aria-label="Sign out" title="Sign out" onClick={() => void run(async () => { await post("/auth/logout"); setProfile(null); setCompanyId(""); })}><LogOut size={16} /></button></div></div>
    </aside>
    <div className="ix-main"><header className="ix-topbar"><div className="ix-breadcrumb">Workspace <ChevronRight size={13} /><strong>{company?.name}</strong><ChevronRight size={13} /><span>{navigation.find(item => item.id === tab)?.label}</span></div><div className="ix-top-actions"><label className="ix-mobile-company"><select aria-label="Mobile company workspace" value={companyId} onChange={changeCompany}>{profile.companies.map(entry => <option key={entry.id} value={entry.id}>{entry.name}</option>)}</select></label><label><Building2 size={15} /><select aria-label="Site filter" value={siteId} onChange={event => { setSiteId(event.target.value); setReport(null); setDraft(null); }}><option value="">All sites</option>{sites.map(site => <option key={site.id} value={site.id}>{site.name}</option>)}</select></label><button aria-label="Refresh workspace" title="Refresh workspace" onClick={() => void refresh()} disabled={loading}><RefreshCw size={17} className={loading ? "ix-spin" : ""} /></button></div></header>
      <main className="ix-content"><div className="ix-page-head"><div><span className="ix-eyebrow">{company?.name} / INDUSTRIAL OPERATIONS</span><h1>{headings[tab][0]}</h1><p>{headings[tab][1]}</p></div>{canEdit && <button className="ix-button ix-button-primary" onClick={() => { setTab("machines"); setShowSetup(true); }}><Plus size={16} />Register equipment</button>}</div>
        {error && <div role="alert" className="ix-error">{error} <button className="ix-link" onClick={() => void refresh()}>Retry connection</button></div>}
        {notice && <div role="status" className="ix-success">{notice}<button aria-label="Dismiss notification" onClick={() => setNotice("")}>Dismiss</button></div>}
        <div className="ix-freshness"><span className={error ? "ix-dot ix-dot-amber" : "ix-dot"} />{lastUpdated ? `Updated ${new Date(lastUpdated).toLocaleTimeString()} / refreshes every 15 seconds` : loading ? "Loading workspace..." : "Waiting for your first connection"}<span>All displayed times use your browser timezone</span></div>

        {tab === "overview" && <div className="ix-stack"><div className="ix-kpis">{[
          ["Registered machines", summary?.machine_count, "Your selected operating scope", Factory], ["Connected", summary?.online, "All configured signals fresh", Activity],
          ["Needs attention", summary?.attention, "Current limit breaches", Bell], ["Open maintenance", summary?.open_work_orders, "Awaiting verified completion", Wrench],
        ].map(([label, value, detail, Icon]) => { const Glyph = Icon as typeof Factory; return <div className="ix-kpi" key={String(label)}><div><span>{String(label)}</span><Glyph size={18} /></div><strong>{value === undefined ? "—" : String(value)}</strong><small>{String(detail)}</small></div>; })}</div>
          {!machines.length && !loading ? <Section eyebrow="WELCOME TO YOUR WORKSPACE" title="Start with one machine. Build from there." detail="No generated health scores or machinery readings are included in your company."><div className="ix-onboarding">{[["01", "Organize your sites", "Register a plant or facility and its timezone."], ["02", "Register equipment", "Give machinery a category, asset tag and criticality."], ["03", "Connect real signals", "Define sensors and import timestamped readings."]].map(([step, title, detail]) => <div key={step}><b>{step}</b><h3>{title}</h3><p>{detail}</p></div>)}</div>{canEdit && <button className="ix-button ix-button-primary" onClick={() => { setTab("machines"); setShowSetup(true); }}>Set up your first site <ArrowRight size={15} /></button>}</Section> : <Section title="Machinery at a glance" detail={summary?.scope} action={<button className="ix-link" onClick={() => setTab("machines")}>View machinery <ArrowRight size={14} /></button>}>{machineTable}</Section>}
          <div className="ix-two-col"><Section eyebrow="PRIORITY QUEUE" title="Active equipment alerts" detail="Alerts require consecutive fresh readings beyond a configured limit.">{scopedAlerts.filter(item => item.status !== "resolved").length ? scopedAlerts.filter(item => item.status !== "resolved").slice(0, 5).map(item => <div key={item.id} className="ix-list-row"><span className="ix-alert-icon"><Bell size={17} /></span><div><strong>{item.title}</strong><small>{machines.find(asset => asset.id === item.machine_id)?.asset_tag} / {date(item.created_at)}</small></div><button className="ix-link" onClick={() => setTab("alerts")}>Review</button></div>) : <p className="ix-note">No active threshold alerts. Check connectivity before interpreting this as normal operation.</p>}</Section>
            <Section eyebrow="READINESS" title="Can you trust the current picture?"><div className="ix-readiness"><div><span>Unknown / insufficient condition data</span><strong>{summary?.unknown ?? "—"}</strong></div><div><span>Recorded completed-work downtime</span><strong>{summary?.recorded_downtime_minutes ?? 0}<small> min</small></strong></div></div><p className="ix-note">Condition and connectivity are separate. No readings, stale readings or unconfigured limits never produce a healthy status.</p><button className="ix-link" onClick={() => setTab("data")}>Inspect data connections <ArrowRight size={14} /></button></Section></div>
        </div>}

        {tab === "machines" && <div className="ix-stack"><Section title="Machine registry" detail="Up to 500 machines per view. Select an asset to inspect its signals." action={<div className="ix-search"><Search size={16} /><input aria-label="Search machinery" placeholder="Search machines or tags" value={search} onChange={event => setSearch(event.target.value)} /></div>}>
          {machines.length ? machineTable : <Empty title="No machines registered" detail="Create a site, then register the equipment you want to monitor." />}
        </Section>
          {machine && !showSetup && <><Section eyebrow={`${machine.asset_tag} / ${machine.equipment_type}`} title={machine.name} detail={`${machine.manufacturer} ${machine.model} / ${machine.area || "No production area assigned"}`} action={<Badge value={machine.criticality} />}>
            <div className="ix-machine-summary"><div><small>CONDITION</small><Badge value={machine.health} /></div><div><small>CONNECTION</small><Badge value={machine.connectivity} /></div><div><small>OPERATING STATE</small>{canEdit ? <select aria-label="Machine operating state" value={machine.operating_state} disabled={busy} onChange={event => void run(() => patch(`${base}/machines/${machine.id}`, { operating_state: event.target.value }), "Operating state updated.")}>{["running", "idle", "stopped", "maintenance"].map(value => <option key={value}>{value}</option>)}</select> : machine.operating_state}</div><div><small>LAST OBSERVED</small><span>{date(machine.last_seen)}</span></div></div>
            {machine.notes && <p className="ix-note">{machine.notes}</p>}<p className="ix-model-note"><ShieldCheck size={16} />Threshold monitoring reflects observed sensor limits. Equipment-specific RUL models are configured below.</p>
          </Section><Predictive key={`${companyId}/${machine.id}`} base={base} machine={machine} canConfigure={canConfigure} canEdit={canEdit} /><Section title="Sensor signals" detail="Latest observed readings retain their timestamp and quality status.">
            {!machine.sensors.length ? <Empty title="Define this machine's signals" detail="Add sensors with units, reporting intervals and engineering-reviewed limits." /> : <div className="ix-sensor-grid">{machine.sensors.map(point => <button key={point.id} className={`ix-sensor-card ${sensor?.id === point.id ? "active" : ""}`} onClick={() => setSensorKey(point.key)}><div><span>{point.name}</span><Badge value={point.freshness} /></div><strong>{point.latest ? point.latest.value.toLocaleString(undefined, { maximumFractionDigits: 3 }) : "—"}<small>{point.unit}</small></strong><p>{point.key} / expected every {point.expected_interval_seconds}s</p><small>{date(point.latest?.timestamp || null)}</small></button>)}</div>}
            {sensor && <><div className="ix-chart-title"><strong>{sensor.name} history</strong><span>Latest 500 readings / {sensor.unit}</span></div>{series.length ? <div className="ix-chart"><ResponsiveContainer width="100%" height="100%"><LineChart data={series} margin={{ top: 15, right: 25, left: 0, bottom: 10 }}><CartesianGrid strokeDasharray="3 3" stroke="#e8edf2" /><XAxis dataKey="timestamp" tickFormatter={value => new Date(value).toLocaleTimeString()} minTickGap={70} tick={{ fontSize: 11 }} /><YAxis domain={["auto", "auto"]} tick={{ fontSize: 11 }} /><Tooltip labelFormatter={value => new Date(String(value)).toLocaleString()} /><Line dataKey="value" name={sensor.unit} stroke="#0c756b" strokeWidth={2} dot={false} isAnimationActive={false} />{sensor.warning_high !== null && <ReferenceLine y={sensor.warning_high} stroke="#d97706" strokeDasharray="5 5" label="Upper warning" />}{sensor.warning_low !== null && <ReferenceLine y={sensor.warning_low} stroke="#d97706" strokeDasharray="5 5" label="Lower warning" />}</LineChart></ResponsiveContainer></div> : <p className="ix-note">No readings for this signal. Upload a CSV or connect your gateway.</p>}</>}
          </Section>{canConfigure && <SensorForm base={base} machine={machine} run={run} busy={busy} />}</>}
          {(showSetup || !machines.length) && canEdit && <><SiteForm base={base} run={run} busy={busy} /><MachineForm base={base} sites={sites} run={run} busy={busy} /></>}
        </div>}

        {tab === "alerts" && <Section eyebrow="REVIEW BEFORE ACTING" title="Equipment alert inbox" detail="Acknowledgement records ownership of the review. Alerts recover automatically after consecutive fresh readings return within limits.">
          {!scopedAlerts.length ? <Empty title="No threshold alerts yet" detail="Configure sensor limits and connect fresh readings. Data connection issues are shown separately." /> : scopedAlerts.map(item => <article className="ix-alert-card" key={item.id}><div className="ix-alert-card-head"><div><span className="ix-eyebrow">{machines.find(asset => asset.id === item.machine_id)?.asset_tag}</span><h3>{item.title}</h3></div><Badge value={item.status} /></div><p>Observed {item.evidence.value} {item.evidence.unit} across {item.evidence.consecutive_samples} consecutive samples. Recorded {date(item.evidence.timestamp)}.</p><div className="ix-alert-actions">{item.status === "open" && role !== "viewer" && <button className="ix-button" disabled={busy} onClick={() => void run(() => post(`${base}/alerts/${item.id}/acknowledge`), "Alert acknowledged.")}>Acknowledge</button>}{canEdit && <button className="ix-button ix-button-primary" onClick={() => workFromAlert(item)}>Create inspection work</button>}<button className="ix-link" onClick={() => inspectMachine(item.machine_id)}>Inspect machine <ArrowRight size={14} /></button></div></article>)}
        </Section>}

        {tab === "maintenance" && <Maintenance key={companyId} base={base} machines={machines} orders={scopedOrders} members={members} role={role} userId={profile.id} run={run} busy={busy} draft={draft} />}

        {tab === "data" && <div className="ix-stack"><Section eyebrow="CONNECTION HEALTH" title="Signals before scores" detail="Readings become stale after three expected reporting intervals. Partial connectivity and missing sensors remain visible."><div className="ix-table-wrap"><table className="ix-table"><thead><tr><th>Machine / sensor</th><th>Unit</th><th>Latest reading</th><th>Freshness</th><th>Expected interval</th><th>Warning limits</th></tr></thead><tbody>{machines.flatMap(item => item.sensors.map(point => <tr key={point.id}><td><strong>{item.asset_tag}</strong><small className="ix-cell-detail">{point.name}</small></td><td>{point.unit}</td><td>{point.latest?.value ?? "—"}<small className="ix-cell-detail">{date(point.latest?.timestamp || null)}</small></td><td><Badge value={point.freshness} /></td><td>{point.expected_interval_seconds}s</td><td>{point.warning_low ?? "not set"} / {point.warning_high ?? "not set"}</td></tr>))}</tbody></table></div>{!machines.some(item => item.sensors.length) && <Empty title="No sensor connections" detail="Register a machine and its sensors before sending telemetry." />}</Section>
          {canEdit && <Section eyebrow="CSV INGESTION" title="Import machine telemetry" detail="Use UTF-8 CSV with sensor_key,timestamp,value,unit. Timestamps need an explicit timezone, such as 2026-11-13T09:30:00Z. Up to 10,000 readings per import."><div className="ix-import-controls"><label className="ix-field"><span>Target machine</span><select aria-label="Import target machine" value={selectedId} onChange={event => { setSelectedId(event.target.value); setReport(null); }}>{machines.map(item => <option key={item.id} value={item.id}>{item.asset_tag} / {item.name}</option>)}</select></label><label className="ix-field"><span>Telemetry CSV</span><input type="file" aria-label="Telemetry CSV" accept=".csv,text/csv" onChange={event => { setUpload(event.target.files?.[0] || null); setReport(null); }} /></label><button className="ix-button ix-button-primary" disabled={busy || !machine?.sensors.length || !upload} onClick={() => void importFile()}>Validate & import</button><button className="ix-link" onClick={downloadTemplate}>Download CSV template</button></div>
            {report && <div className="ix-import-report" role="status"><strong>{report.accepted} accepted / {report.duplicates} duplicates / {report.rejected} rejected</strong><small>Source SHA-256: {report.checksum_sha256}</small>{report.errors.slice(0, 50).map(item => <p className="ix-text-amber" key={item.row}>Data row {item.row}: {item.error}</p>)}{report.errors.length > 50 && <p>Showing the first 50 rejected rows.</p>}</div>}
          </Section>}
          <Section eyebrow="AUTHENTICATED API" title="Connect a plant gateway" detail="Create an ingestion key in Team & access. It is scoped to this company and grants ingestion only."><pre className="ix-code">{JSON.stringify({ endpoint: `/api/v1/industrial${base}/telemetry`, method: "POST", headers: { "X-Ingestion-Key": "<YOUR_INGESTION_KEY>" }, body: { readings: [{ machine_id: machine?.id || "<MACHINE_ID>", sensor_key: sensor?.key || "<SENSOR_KEY>", timestamp: "<ISO_8601_WITH_TIMEZONE>", value: "<NUMBER>", unit: sensor?.unit || "<REGISTERED_UNIT>" }] } }, null, 2)}</pre><p className="ix-note">MQTT, OPC UA and Modbus adapters are planned. This release accepts CSV and authenticated HTTP batches. No gateway connection is implied until readings arrive.</p></Section>
        </div>}

        {tab === "team" && <Team key={companyId} base={base} members={members} keys={keys} events={events} role={role} userId={profile.id} run={run} busy={busy} onProfile={signedIn} />}
        <footer className="ix-footer"><span>TelemetryX / Industrial foundation</span><span>Observed condition, explicit uncertainty, accountable action.</span></footer>
      </main>
    </div>
  </div>;
}

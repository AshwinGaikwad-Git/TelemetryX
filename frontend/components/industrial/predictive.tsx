"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Activity, Download, Play, RefreshCw } from "lucide-react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { industrialRequest, Machine, post } from "../../lib/industrial-api";
import { date, Section } from "./ui";

type Metrics = { mae_hours: number; rmse_hours: number; interval_coverage: number; baseline_mae_hours: number; training_runs: number; validation_runs: number; training_rows: number; validation_rows: number };
type Prediction = { id: string; model_id: string; remaining_hours: number; lower_hours: number; upper_hours: number; observed_at: string; created_at: string; evidence: { contributors: { sensor: string; delta_hours: number }[]; inputs: Record<string, { value: number; timestamp: string; unit: string }> } };
type Status = { model: { id: string; checksum: string; created_at: string; feature_schema: Record<string, { unit: string }>; metrics: Metrics } | null; ready: boolean; reason: string | null; history: Prediction[] };
const hours = (value: number) => `${value.toFixed(1)} h`;

export default function Predictive({ base, machine, canConfigure, canEdit }: { base: string; machine: Machine; canConfigure: boolean; canEdit: boolean }) {
  const [status, setStatus] = useState<Status | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const sequence = useRef(0);
  const path = `${base}/machines/${machine.id}/predictive`;
  const refresh = useCallback(async () => {
    const request = ++sequence.current;
    try { const result = await industrialRequest<Status>(path); if (request === sequence.current) { setStatus(result); setError(""); } }
    catch (err) { if (request === sequence.current) setError(err instanceof Error ? err.message : "Prediction status unavailable"); }
  }, [path]);
  useEffect(() => { void refresh(); const timer = setInterval(() => { if (!document.hidden) void refresh(); }, 15000); return () => { sequence.current++; clearInterval(timer); }; }, [refresh]);
  async function action(kind: "train" | "predict") {
    setBusy(true); setNotice(""); setError("");
    try {
      if (kind === "train") {
        if (!file) return;
        const body = new FormData(); body.set("file", file);
        await industrialRequest(`${path}/train`, { method: "POST", body });
      } else await post(`${path}/predict`);
      await refresh(); setNotice(kind === "train" ? "Model trained. Review its held-out validation results before interpreting estimates." : "Estimate saved with its sensor evidence and model version.");
    } catch (err) { setError(err instanceof Error ? err.message : "Prediction operation failed"); }
    finally { setBusy(false); }
  }
  function template() {
    const keys = machine.sensors.slice(0, 30).map(sensor => sensor.key);
    const url = URL.createObjectURL(new Blob([["run_id", "remaining_hours", ...keys].join(",") + "\n"], { type: "text/csv" }));
    const anchor = document.createElement("a"); anchor.href = url; anchor.download = `${machine.asset_tag}-training-template.csv`; anchor.click(); URL.revokeObjectURL(url);
  }
  const model = status?.model;
  const latest = status?.history.find(item => item.model_id === model?.id);
  const fresh = latest && status?.ready && Object.entries(latest.evidence.inputs).every(([key, input]) => {
    const sensor = machine.sensors.find(item => item.key === key);
    return sensor?.freshness === "fresh" && new Date(sensor.latest?.timestamp || "").getTime() === new Date(input.timestamp).getTime() && sensor.latest?.value === input.value;
  });
  return <Section eyebrow="EQUIPMENT-SPECIFIC PREDICTIONS" title="Remaining life. With evidence." detail="Experimental estimates in hours from your labeled failure history. Sensor limits and connectivity remain independently monitored." action={<button aria-label="Refresh predictive status" className="ix-link" disabled={busy} onClick={() => void refresh()}><RefreshCw size={14} />Refresh</button>}>
    {error && <div role="alert" className="ix-error">{error}</div>}
    {notice && <div role="status" className="ix-success">{notice}</div>}
    {!status && !error && <p className="ix-note">Loading model readiness...</p>}
    <div className="ix-model-note"><Activity size={16} /><span>{status?.reason || (model ? "Required sensor readings are compatible and fresh. Ready to estimate." : "Train a model to enable remaining-life estimates.")}</span></div>
    {model && <>
      <div className="ix-machine-summary ix-inset"><div><small>MODEL VERSION</small><span title={model.id}>{model.id.slice(0, 8)} / experimental</span></div><div><small>VALIDATION MAE</small><span>{hours(model.metrics.mae_hours)}</span></div><div><small>MEDIAN BASELINE MAE</small><span>{hours(model.metrics.baseline_mae_hours)}</span></div><div><small>OBSERVED INTERVAL COVERAGE</small><span>{(model.metrics.interval_coverage * 100).toFixed(1)}%</span></div></div>
      <p className="ix-note">Trained on {model.metrics.training_rows} snapshots from {model.metrics.training_runs} runs; evaluated on {model.metrics.validation_rows} snapshots from {model.metrics.validation_runs} separate runs. Interval targets 90% coverage; observed coverage above measures this validation split. Validation RMSE: {hours(model.metrics.rmse_hours)}.</p>
      {model.metrics.mae_hours >= model.metrics.baseline_mae_hours && <p className="ix-error">This model does not improve on the median baseline in held-out validation. Review training data before using its estimates.</p>}
      <p className="ix-note">Required signals: {Object.entries(model.feature_schema).map(([key, value]) => `${key} (${value.unit})`).join(", ")}. Training source SHA-256: <span className="ix-checksum">{model.checksum}</span></p>
      {canEdit && <button className="ix-button ix-button-primary" disabled={busy || !status?.ready} onClick={() => void action("predict")}><Play size={14} />{busy ? "Processing..." : "Estimate remaining life"}</button>}
    </>}
    {latest && <div className="ix-inset"><div className="ix-section-head"><div><span className="ix-eyebrow">{fresh ? "CURRENT SENSOR SNAPSHOT" : "HISTORICAL ESTIMATE / REFRESH REQUIRED"}</span><h2>{hours(latest.remaining_hours)} estimated remaining life</h2><p>Nominal 90% interval: {hours(latest.lower_hours)}–{hours(latest.upper_hours)}. Observed {date(latest.observed_at)}. This is remaining time under the training conditions, not a failure probability.</p></div></div>
      <div className="ix-table-wrap"><table className="ix-table"><thead><tr><th>Sensor evidence</th><th>Input</th><th>Sensitivity in hours</th></tr></thead><tbody>{latest.evidence.contributors.slice(0, 5).map(item => <tr key={item.sensor}><td>{item.sensor}</td><td>{latest.evidence.inputs[item.sensor].value} {latest.evidence.inputs[item.sensor].unit}</td><td>{item.delta_hours > 0 ? "+" : ""}{item.delta_hours.toFixed(2)} h</td></tr>)}</tbody></table></div><p className="ix-note">Sensitivity compares this estimate with replacing one sensor by its training median. It is not a causal explanation or an additive contribution.</p>
    </div>}
    {!!status?.history.length && <div className="ix-inset"><div className="ix-section-head"><h2>Prediction history</h2><p>Latest 50 estimates / model versions retained</p></div><div className="ix-chart"><ResponsiveContainer width="100%" height="100%"><LineChart data={[...status.history].reverse().map(item => ({ time: date(item.created_at), hours: item.remaining_hours, lower: item.lower_hours, upper: item.upper_hours }))}><CartesianGrid stroke="#edf1f2" /><XAxis dataKey="time" fontSize={9} /><YAxis fontSize={10} unit=" h" /><Tooltip /><Line dataKey="hours" name="Remaining hours" stroke="#0c756b" dot /><Line dataKey="lower" name="Lower bound" stroke="#91b6aa" strokeDasharray="4 4" dot={false} /><Line dataKey="upper" name="Upper bound" stroke="#91b6aa" strokeDasharray="4 4" dot={false} /></LineChart></ResponsiveContainer></div><div className="ix-table-wrap"><table className="ix-table"><thead><tr><th>Observed</th><th>Model</th><th>Remaining life</th><th>Interval</th></tr></thead><tbody>{status.history.slice(0, 10).map(item => <tr key={item.id}><td>{date(item.observed_at)}</td><td>{item.model_id.slice(0, 8)}</td><td>{hours(item.remaining_hours)}</td><td>{hours(item.lower_hours)}–{hours(item.upper_hours)}</td></tr>)}</tbody></table></div></div>}
    {canConfigure && <div className="ix-inset"><div className="ix-section-head"><div><h2>{model ? "Train a new model version" : "Start with labeled operating history"}</h2><p>Upload 100–10,000 snapshots from at least 5 independent failure runs (2 MB maximum). Use run_id, remaining_hours and 1–30 registered sensor keys as columns. Each run_id identifies one asset life between repairs. Labels must represent known time to failure; sensor values must use their registered units. No synthetic data is generated.</p></div></div><div className="ix-import-controls"><button className="ix-button" disabled={!machine.sensors.length || busy} onClick={template}><Download size={14} />Training CSV template</button><label className="ix-field">Labeled training history<input aria-label="Labeled training history" type="file" accept=".csv" disabled={busy} onChange={event => setFile(event.target.files?.[0] || null)} /></label><button className="ix-button ix-button-primary" disabled={!file || busy || !machine.sensors.length} onClick={() => void action("train")}>{busy ? "Processing..." : "Train equipment model"}</button></div></div>}
    <p className="ix-note">Model output needs validation for this equipment and operating regime before maintenance decisions. Estimates do not automatically create alerts, change condition or schedule work.</p>
  </Section>;
}


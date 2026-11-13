"use client";

import { ReactNode } from "react";

export function Badge({ value }: { value: string }) {
  const tone = ["attention", "critical", "high", "open"].includes(value) ? "amber" :
    ["within_limits", "online", "verified", "resolved", "fresh"].includes(value) ? "green" : "neutral";
  return <span className={`ix-badge ix-badge-${tone}`}>{value.replaceAll("_", " ")}</span>;
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return <label className="ix-field"><span>{label}</span>{children}</label>;
}

export function Empty({ title, detail, children }: { title: string; detail: string; children?: ReactNode }) {
  return <div className="ix-empty"><div className="ix-empty-mark">+</div><h3>{title}</h3><p>{detail}</p>{children}</div>;
}

export function Section({ eyebrow, title, detail, action, children }: {
  eyebrow?: string; title: string; detail?: string; action?: ReactNode; children: ReactNode;
}) {
  return <section className="ix-panel"><div className="ix-section-head"><div>
    {eyebrow && <span className="ix-eyebrow">{eyebrow}</span>}<h2>{title}</h2>{detail && <p>{detail}</p>}
  </div>{action}</div>{children}</section>;
}

export function date(value: string | null) {
  return value ? new Date(value).toLocaleString() : "No readings yet";
}

export function formValues(form: HTMLFormElement) { return new FormData(form); }
export function text(data: FormData, key: string) { return String(data.get(key) || "").trim(); }
export function optionalNumber(data: FormData, key: string) {
  return text(data, key) === "" ? null : Number(data.get(key));
}

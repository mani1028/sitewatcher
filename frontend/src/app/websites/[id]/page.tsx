"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Protected } from "@/components/Protected";
import { StatusDot } from "@/components/StatusDot";
import { api, Check, Incident, Website } from "@/lib/api";
import { formatDuration, formatMs, formatTime, intervalLabel, statusLabel } from "@/lib/format";

export default function WebsiteDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = Number(params.id);
  const [site, setSite] = useState<Website | null>(null);
  const [checks, setChecks] = useState<Check[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const [w, c, i] = await Promise.all([api.website(id), api.checks(id, 24), api.websiteIncidents(id)]);
      setSite(w);
      setChecks(c);
      setIncidents(i);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    }
  }, [id]);

  useEffect(() => {
    load();
    const timer = setInterval(load, 20000);
    return () => clearInterval(timer);
  }, [load]);

  const chartData = useMemo(
    () =>
      [...checks]
        .reverse()
        .filter((c) => c.response_time != null)
        .map((c) => ({
          time: new Date(c.checked_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
          ms: c.response_time,
        })),
    [checks],
  );

  async function toggleMaintenance() {
    if (!site) return;
    setSaving(true);
    try {
      const updated = await api.updateWebsite(site.id, { maintenance_mode: !site.maintenance_mode });
      setSite(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed");
    } finally {
      setSaving(false);
    }
  }

  async function removeSite() {
    if (!site || !confirm(`Delete ${site.name}?`)) return;
    await api.deleteWebsite(site.id);
    router.push("/dashboard");
  }

  return (
    <Protected>
      {!site ? (
        <p className="text-ink-mute">{error || "Loading…"}</p>
      ) : (
        <div className="space-y-8 animate-rise">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <Link href="/dashboard" className="text-xs uppercase tracking-wide text-ink-mute hover:text-teal">
                ← Dashboard
              </Link>
              <div className="mt-2 flex items-center gap-3">
                <StatusDot status={site.status} pulse={site.status === "DOWN"} className="h-3 w-3" />
                <h1 className="font-display text-3xl font-semibold tracking-tight text-ink">{site.name}</h1>
              </div>
              <p className="mt-1 font-mono text-sm text-ink-mute">{site.url}</p>
              <p className="mt-3 text-sm text-ink-soft">
                {statusLabel(site.status)} · {site.uptime_percent.toFixed(2)}% uptime · checked every{" "}
                {intervalLabel(site.check_interval)}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Link href={`/websites/${site.id}/edit`} className="btn-primary">
                Edit
              </Link>
              <button className="btn-secondary" onClick={toggleMaintenance} disabled={saving}>
                {site.maintenance_mode ? "Exit maintenance" : "Maintenance mode"}
              </button>
              <button className="btn-danger" onClick={removeSite}>
                Delete
              </button>
            </div>
          </div>

          {error && <p className="text-sm text-alert-down">{error}</p>}

          <section className="grid gap-4 sm:grid-cols-3">
            <Metric label="Response" value={site.status === "DOWN" ? "DOWN" : formatMs(site.last_response_time)} />
            <Metric label="Last status" value={site.last_status_code ? String(site.last_status_code) : "—"} />
            <Metric
              label="SSL expires"
              value={site.ssl_expires_at ? formatTime(site.ssl_expires_at) : site.monitor_ssl ? "Pending" : "Off"}
            />
          </section>

          <section className="surface rounded-3xl p-6 shadow-soft">
            <h2 className="font-display text-lg font-semibold text-ink">Response time</h2>
            <p className="mt-1 text-sm text-ink-mute">Last 24 hours</p>
            <div className="mt-6 h-64">
              {chartData.length === 0 ? (
                <div className="flex h-full items-center justify-center text-sm text-ink-mute">
                  Waiting for the first checks…
                </div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={chartData}>
                    <defs>
                      <linearGradient id="rt" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#0B5F4A" stopOpacity={0.35} />
                        <stop offset="100%" stopColor="#0B5F4A" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid stroke="rgba(19,33,43,0.06)" vertical={false} />
                    <XAxis dataKey="time" tick={{ fill: "#6B7C87", fontSize: 11 }} axisLine={false} tickLine={false} minTickGap={40} />
                    <YAxis tick={{ fill: "#6B7C87", fontSize: 11 }} axisLine={false} tickLine={false} width={48} />
                    <Tooltip
                      contentStyle={{
                        borderRadius: 12,
                        border: "1px solid rgba(19,33,43,0.08)",
                        boxShadow: "0 12px 30px rgba(19,33,43,0.08)",
                      }}
                      formatter={(value) => [`${Math.round(Number(value))}ms`, "Response"]}
                    />
                    <Area type="monotone" dataKey="ms" stroke="#0B5F4A" fill="url(#rt)" strokeWidth={2} />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </div>
          </section>

          <section className="grid gap-6 lg:grid-cols-2">
            <div className="surface rounded-3xl p-6 shadow-soft">
              <h2 className="font-display text-lg font-semibold text-ink">Recent checks</h2>
              <ul className="mt-4 max-h-80 space-y-3 overflow-auto">
                {checks.slice(0, 30).map((check) => (
                  <li key={check.id} className="flex items-center gap-3 text-sm">
                    <StatusDot status={check.status} />
                    <span className="w-28 font-mono text-ink-mute">{formatTime(check.checked_at)}</span>
                    <span className="w-12 font-mono text-ink">{check.status_code ?? "—"}</span>
                    <span className="font-mono text-ink-soft">{formatMs(check.response_time)}</span>
                  </li>
                ))}
              </ul>
            </div>

            <div className="surface rounded-3xl p-6 shadow-soft">
              <h2 className="font-display text-lg font-semibold text-ink">Incidents</h2>
              <ul className="mt-4 max-h-80 space-y-3 overflow-auto">
                {incidents.length === 0 && <li className="text-sm text-ink-mute">No incidents for this site.</li>}
                {incidents.map((incident) => (
                  <li key={incident.id} className="border-b border-ink/5 pb-3 text-sm last:border-0">
                    <div className="flex items-center gap-2">
                      <StatusDot status={incident.status === "open" ? "DOWN" : "UP"} />
                      <span className="font-medium capitalize text-ink">{incident.status}</span>
                      <span className="text-ink-mute">· {formatDuration(incident.duration_seconds)}</span>
                    </div>
                    <p className="mt-1 text-ink-soft">{incident.reason}</p>
                    <p className="mt-1 text-xs text-ink-mute">{formatTime(incident.started_at)}</p>
                  </li>
                ))}
              </ul>
            </div>
          </section>
        </div>
      )}
    </Protected>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="surface rounded-3xl px-5 py-4 shadow-soft">
      <p className="text-xs uppercase tracking-wide text-ink-mute">{label}</p>
      <p className="mt-2 font-display text-2xl font-semibold text-ink">{value}</p>
    </div>
  );
}

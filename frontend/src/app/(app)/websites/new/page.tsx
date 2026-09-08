"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { BackLink } from "@/components/BackLink";
import { api, SiteCategory, SiteOwner } from "@/lib/api";
import { SITE_CATEGORIES, SITE_OWNERS } from "@/lib/categories";

export default function NewWebsitePage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [healthUrl, setHealthUrl] = useState("");
  const [owner, setOwner] = useState<SiteOwner>("inhouse");
  const [category, setCategory] = useState<SiteCategory>("website");
  const [checkInterval, setCheckInterval] = useState(60);
  const [timeout, setTimeoutSec] = useState(10);
  const [expectedStatus, setExpectedStatus] = useState(200);
  const [monitorSsl, setMonitorSsl] = useState(true);
  const [whatsappAlerts, setWhatsappAlerts] = useState(false);
  const [highPriority, setHighPriority] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const site = await api.createWebsite({
        name,
        url,
        health_url: healthUrl.trim() || null,
        owner,
        category,
        check_interval: checkInterval,
        timeout,
        expected_status: expectedStatus,
        monitor_ssl: monitorSsl,
        whatsapp_alerts: whatsappAlerts,
        high_priority: highPriority,
      });
      router.push(`/websites/${site.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add website");
    } finally {
      setLoading(false);
    }
  }

  return (
      <div className="mx-auto max-w-2xl animate-rise space-y-5 sm:space-y-6">
        <BackLink href="/dashboard" label="Back" />

        <div>
          <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-ink-mute sm:text-xs">
            Projects
          </p>
          <h1 className="mt-1 font-display text-2xl font-semibold tracking-tight text-ink sm:text-3xl">
            Add website
          </h1>
          <p className="mt-1.5 text-sm text-ink-soft">
            Choose ownership first (client vs in-house), then type. They stay separate in the dashboard.
          </p>
        </div>

        <form onSubmit={onSubmit} className="space-y-5">
          <section className="surface space-y-4 rounded-2xl p-5 shadow-soft sm:rounded-3xl sm:p-6">
            <h2 className="font-display text-base font-semibold text-ink">Basics</h2>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Name">
                <input
                  className="input"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="JobNeedX"
                  required
                />
              </Field>
              <Field label="Type">
                <select
                  className="input"
                  value={category}
                  onChange={(e) => setCategory(e.target.value as SiteCategory)}
                >
                  {SITE_CATEGORIES.map((c) => (
                    <option key={c.value} value={c.value}>
                      {c.label}
                    </option>
                  ))}
                </select>
              </Field>
            </div>
            <Field label="URL">
              <input
                className="input"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://jobneedx.com"
                required
              />
            </Field>
            <Field label="Health / API URL (optional)">
              <input
                className="input"
                value={healthUrl}
                onChange={(e) => setHealthUrl(e.target.value)}
                placeholder="https://jobneedx.com/api/health"
              />
              <p className="mt-1.5 text-xs text-ink-mute">
                If set, both the frontend URL and this backend/API URL must return OK — otherwise the site is Down.
              </p>
            </Field>
            <Field label="Ownership">
              <select className="input" value={owner} onChange={(e) => setOwner(e.target.value as SiteOwner)}>
                {SITE_OWNERS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
              <p className="mt-1.5 text-xs text-ink-mute">
                Client sites stay filtered and labeled apart from in-house projects.
              </p>
            </Field>
          </section>

          <section className="surface space-y-4 rounded-2xl p-5 shadow-soft sm:rounded-3xl sm:p-6">
            <h2 className="font-display text-base font-semibold text-ink">Monitoring</h2>
            <div className="grid gap-4 sm:grid-cols-3">
              <Field label="Check every">
                <select
                  className="input"
                  value={checkInterval}
                  onChange={(e) => setCheckInterval(Number(e.target.value))}
                >
                  <option value={60}>1 minute</option>
                  <option value={300}>5 minutes</option>
                  <option value={600}>10 minutes</option>
                  <option value={3600}>1 hour</option>
                  <option value={86400}>1 day</option>
                </select>
              </Field>
              <Field label="Timeout (sec)">
                <input
                  className="input"
                  type="number"
                  min={3}
                  max={60}
                  value={timeout}
                  onChange={(e) => setTimeoutSec(Number(e.target.value))}
                />
              </Field>
              <Field label="Expected status">
                <input
                  className="input"
                  type="number"
                  min={100}
                  max={599}
                  value={expectedStatus}
                  onChange={(e) => setExpectedStatus(Number(e.target.value))}
                />
              </Field>
            </div>
            <label className="flex cursor-pointer items-center gap-2.5 rounded-xl border border-ink/8 bg-white/60 px-3.5 py-3 text-sm text-ink transition hover:bg-white sm:max-w-xs">
              <input
                type="checkbox"
                checked={monitorSsl}
                onChange={(e) => setMonitorSsl(e.target.checked)}
                className="h-4 w-4 rounded border-ink/20 text-teal"
              />
              Monitor SSL certificate
            </label>
            <label className="flex cursor-pointer items-start gap-2.5 rounded-xl border border-ink/8 bg-white/60 px-3.5 py-3 text-sm text-ink transition hover:bg-white">
              <input
                type="checkbox"
                checked={whatsappAlerts}
                onChange={(e) => setWhatsappAlerts(e.target.checked)}
                className="mt-0.5 h-4 w-4 rounded border-ink/20 text-teal"
              />
              <span>
                WhatsApp alerts
                <span className="mt-0.5 block text-xs text-ink-mute">
                  Off by default. Also needs WhatsApp enabled in Settings.
                </span>
              </span>
            </label>
            <label className="flex cursor-pointer items-start gap-2.5 rounded-xl border border-ink/8 bg-white/60 px-3.5 py-3 text-sm text-ink transition hover:bg-white">
              <input
                type="checkbox"
                checked={highPriority}
                onChange={(e) => setHighPriority(e.target.checked)}
                className="mt-0.5 h-4 w-4 rounded border-ink/20 text-teal"
              />
              <span>
                High priority
                <span className="mt-0.5 block text-xs text-ink-mute">
                  While down, re-check every 30 seconds. Use for critical in-house sites only.
                </span>
              </span>
            </label>
          </section>

          {error && <p className="text-sm text-alert-down">{error}</p>}

          <div className="flex justify-end">
            <button className="btn-primary h-11 px-6 sm:min-w-[10rem]" disabled={loading}>
              {loading ? "Adding…" : "Add website"}
            </button>
          </div>
        </form>
      </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-ink-mute">{label}</span>
      {children}
    </label>
  );
}

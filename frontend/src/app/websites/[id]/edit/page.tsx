"use client";

import { FormEvent, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { BackLink } from "@/components/BackLink";
import { Protected } from "@/components/Protected";
import { api, SiteCategory, SiteOwner } from "@/lib/api";
import { SITE_CATEGORIES, SITE_OWNERS } from "@/lib/categories";

export default function EditWebsitePage() {
  const params = useParams();
  const router = useRouter();
  const id = Number(params.id);

  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [healthUrl, setHealthUrl] = useState("");
  const [owner, setOwner] = useState<SiteOwner>("inhouse");
  const [category, setCategory] = useState<SiteCategory>("website");
  const [checkInterval, setCheckInterval] = useState(60);
  const [timeout, setTimeoutSec] = useState(10);
  const [expectedStatus, setExpectedStatus] = useState(200);
  const [monitorSsl, setMonitorSsl] = useState(true);
  const [enabled, setEnabled] = useState(true);
  const [maintenanceMode, setMaintenanceMode] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    api
      .website(id)
      .then((site) => {
        setName(site.name);
        setUrl(site.url);
        setHealthUrl(site.health_url || "");
        setOwner((site.owner as SiteOwner) || "inhouse");
        setCategory((site.category as SiteCategory) || "website");
        setCheckInterval(site.check_interval);
        setTimeoutSec(site.timeout);
        setExpectedStatus(site.expected_status);
        setMonitorSsl(site.monitor_ssl);
        setEnabled(site.enabled);
        setMaintenanceMode(site.maintenance_mode);
        setReady(true);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load"));
  }, [id]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await api.updateWebsite(id, {
        name,
        url,
        health_url: healthUrl.trim() || null,
        owner,
        category,
        check_interval: checkInterval,
        timeout,
        expected_status: expectedStatus,
        monitor_ssl: monitorSsl,
        enabled,
        maintenance_mode: maintenanceMode,
      });
      router.push(`/websites/${id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save website");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Protected>
      <div className="mx-auto max-w-2xl animate-rise space-y-5 sm:space-y-6">
        <BackLink href={`/websites/${id}`} label="Back to site" />

        <div>
          <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-ink-mute sm:text-xs">
            Projects
          </p>
          <h1 className="mt-1 font-display text-2xl font-semibold tracking-tight text-ink sm:text-3xl">
            Edit website
          </h1>
          <p className="mt-1.5 text-sm text-ink-soft">
            Update URL, type, check interval, SSL monitoring, and more.
          </p>
        </div>

        {!ready ? (
          <p className="text-ink-mute">{error || "Loading…"}</p>
        ) : (
          <form onSubmit={onSubmit} className="space-y-5">
            <section className="surface space-y-4 rounded-2xl p-5 shadow-soft sm:rounded-3xl sm:p-6">
              <h2 className="font-display text-base font-semibold text-ink">Basics</h2>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Name">
                  <input className="input" value={name} onChange={(e) => setName(e.target.value)} required />
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
                <input className="input" value={url} onChange={(e) => setUrl(e.target.value)} required />
              </Field>
              <Field label="Health / API URL (optional)">
                <input
                  className="input"
                  value={healthUrl}
                  onChange={(e) => setHealthUrl(e.target.value)}
                  placeholder="https://example.com/api/health"
                />
                <p className="mt-1.5 text-xs text-ink-mute">
                  Both frontend and this URL must succeed, or the site is marked Down.
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

              <div className="grid gap-3 sm:grid-cols-3">
                <Toggle
                  label="Monitor SSL"
                  checked={monitorSsl}
                  onChange={setMonitorSsl}
                />
                <Toggle
                  label="Monitoring on"
                  checked={enabled}
                  onChange={setEnabled}
                />
                <Toggle
                  label="Maintenance"
                  checked={maintenanceMode}
                  onChange={setMaintenanceMode}
                />
              </div>
            </section>

            {error && <p className="text-sm text-alert-down">{error}</p>}

            <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
              <button
                type="button"
                className="btn-secondary h-11 px-5"
                onClick={() => router.push(`/websites/${id}`)}
              >
                Cancel
              </button>
              <button className="btn-primary h-11 px-6 sm:min-w-[9rem]" disabled={loading}>
                {loading ? "Saving…" : "Save changes"}
              </button>
            </div>
          </form>
        )}
      </div>
    </Protected>
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

function Toggle({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="flex cursor-pointer items-center gap-2.5 rounded-xl border border-ink/8 bg-white/60 px-3.5 py-3 text-sm text-ink transition hover:bg-white">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="h-4 w-4 rounded border-ink/20 text-teal"
      />
      {label}
    </label>
  );
}

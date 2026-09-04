"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Protected } from "@/components/Protected";
import { api } from "@/lib/api";

export default function EditWebsitePage() {
  const params = useParams();
  const router = useRouter();
  const id = Number(params.id);

  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
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
      <div className="mx-auto max-w-xl animate-rise">
        <Link href={`/websites/${id}`} className="text-xs uppercase tracking-wide text-ink-mute hover:text-teal">
          ← Back to site
        </Link>
        <p className="mt-4 text-xs font-medium uppercase tracking-[0.18em] text-ink-mute">Projects</p>
        <h1 className="mt-1 font-display text-3xl font-semibold tracking-tight text-ink">Edit website</h1>
        <p className="mt-2 text-sm text-ink-soft">Update URL, check interval, SSL monitoring, and more.</p>

        {!ready ? (
          <p className="mt-8 text-ink-mute">{error || "Loading…"}</p>
        ) : (
          <form onSubmit={onSubmit} className="surface mt-8 space-y-5 rounded-3xl p-6 shadow-soft">
            <Field label="Name">
              <input className="input" value={name} onChange={(e) => setName(e.target.value)} required />
            </Field>
            <Field label="URL">
              <input className="input" value={url} onChange={(e) => setUrl(e.target.value)} required />
            </Field>
            <div className="grid gap-4 sm:grid-cols-2">
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
                </select>
              </Field>
              <Field label="Timeout (seconds)">
                <input
                  className="input"
                  type="number"
                  min={3}
                  max={60}
                  value={timeout}
                  onChange={(e) => setTimeoutSec(Number(e.target.value))}
                />
              </Field>
            </div>
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

            <label className="flex items-center gap-3 text-sm text-ink">
              <input
                type="checkbox"
                checked={monitorSsl}
                onChange={(e) => setMonitorSsl(e.target.checked)}
                className="h-4 w-4 rounded border-ink/20 text-teal"
              />
              Monitor SSL certificate
            </label>
            <label className="flex items-center gap-3 text-sm text-ink">
              <input
                type="checkbox"
                checked={enabled}
                onChange={(e) => setEnabled(e.target.checked)}
                className="h-4 w-4 rounded border-ink/20 text-teal"
              />
              Monitoring enabled
            </label>
            <label className="flex items-center gap-3 text-sm text-ink">
              <input
                type="checkbox"
                checked={maintenanceMode}
                onChange={(e) => setMaintenanceMode(e.target.checked)}
                className="h-4 w-4 rounded border-ink/20 text-teal"
              />
              Maintenance mode
            </label>

            {error && <p className="text-sm text-alert-down">{error}</p>}

            <div className="flex gap-3">
              <button type="button" className="btn-secondary flex-1" onClick={() => router.push(`/websites/${id}`)}>
                Cancel
              </button>
              <button className="btn-primary flex-1" disabled={loading}>
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

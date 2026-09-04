"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { Protected } from "@/components/Protected";
import { api } from "@/lib/api";

export default function NewWebsitePage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [checkInterval, setCheckInterval] = useState(60);
  const [timeout, setTimeoutSec] = useState(10);
  const [expectedStatus, setExpectedStatus] = useState(200);
  const [monitorSsl, setMonitorSsl] = useState(true);
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
        check_interval: checkInterval,
        timeout,
        expected_status: expectedStatus,
        monitor_ssl: monitorSsl,
      });
      router.push(`/websites/${site.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add website");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Protected>
      <div className="mx-auto max-w-xl animate-rise">
        <p className="text-xs font-medium uppercase tracking-[0.18em] text-ink-mute">Projects</p>
        <h1 className="mt-1 font-display text-3xl font-semibold tracking-tight text-ink">Add website</h1>
        <p className="mt-2 text-sm text-ink-soft">
          Add any project URL — production, staging, APIs. You’ll get email alerts when it’s down.
        </p>

        <form onSubmit={onSubmit} className="surface mt-8 space-y-5 rounded-3xl p-6 shadow-soft">
          <Field label="Name">
            <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="JobNeedX" required />
          </Field>
          <Field label="URL">
            <input
              className="input"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://jobneedx.com"
              required
            />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Check every">
              <select className="input" value={checkInterval} onChange={(e) => setCheckInterval(Number(e.target.value))}>
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

          {error && <p className="text-sm text-alert-down">{error}</p>}

          <button className="btn-primary w-full" disabled={loading}>
            {loading ? "Adding…" : "Add website"}
          </button>
        </form>
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

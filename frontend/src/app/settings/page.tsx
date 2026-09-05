"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { Eye, EyeOff, Mail, Plus, Trash2 } from "lucide-react";
import { Protected } from "@/components/Protected";
import { api, Settings } from "@/lib/api";

const MAX_ALERT_EMAILS = 20;

function splitEmails(value: string): string[] {
  const parts = value
    .split(/[,;\n]+/)
    .map((p) => p.trim())
    .filter(Boolean);
  return parts.length ? parts : [""];
}

function joinEmails(emails: string[]): string {
  return emails.map((e) => e.trim()).filter(Boolean).join(", ");
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [alertEmails, setAlertEmails] = useState<string[]>([""]);
  const [password, setPassword] = useState("");
  const [smtpPassword, setSmtpPassword] = useState("");
  const [showSmtpPassword, setShowSmtpPassword] = useState(false);
  const [showAdminPassword, setShowAdminPassword] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api
      .settings()
      .then((s) => {
        setSettings(s);
        setAlertEmails(splitEmails(s.alert_email));
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load"));
  }, []);

  function updateAlertEmail(index: number, value: string) {
    setAlertEmails((prev) => prev.map((email, i) => (i === index ? value : email)));
  }

  function addAlertEmail() {
    setAlertEmails((prev) => (prev.length >= MAX_ALERT_EMAILS ? prev : [...prev, ""]));
  }

  function removeAlertEmail(index: number) {
    setAlertEmails((prev) => {
      const next = prev.filter((_, i) => i !== index);
      return next.length ? next : [""];
    });
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!settings) return;
    const joined = joinEmails(alertEmails);
    if (!joined) {
      setError("Add at least one alert email.");
      return;
    }
    setLoading(true);
    setMessage("");
    setError("");
    try {
      const payload: Record<string, unknown> = {
        alert_email: joined,
        notification_enabled: settings.notification_enabled,
        slow_threshold_ms: settings.slow_threshold_ms,
        failure_threshold: settings.failure_threshold,
        recovery_threshold: settings.recovery_threshold,
        smtp_host: settings.smtp_host,
        smtp_port: settings.smtp_port,
        smtp_user: settings.smtp_user,
        smtp_from: settings.smtp_from,
        smtp_use_tls: settings.smtp_use_tls,
      };
      if (smtpPassword) payload.smtp_password = smtpPassword;
      if (password) payload.password = password;
      const updated = await api.updateSettings(payload);
      setSettings(updated);
      setAlertEmails(splitEmails(updated.alert_email));
      setPassword("");
      setSmtpPassword("");
      setMessage("Settings saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setLoading(false);
    }
  }

  async function sendTest() {
    setMessage("");
    setError("");
    try {
      await api.testEmail();
      setMessage("Test email sent. Check your inbox.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Test email failed");
    }
  }

  return (
    <Protected>
      <div className="animate-rise space-y-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-ink-mute sm:text-xs">
              Account
            </p>
            <h1 className="mt-1 font-display text-2xl font-semibold tracking-tight text-ink sm:text-3xl">
              Settings
            </h1>
            <p className="mt-2 max-w-xl text-sm text-ink-soft">
              Configure who gets alerts and the SMTP mailbox that sends them.
            </p>
          </div>
          <Link href="/emails" className="btn-secondary h-10 shrink-0 px-4 text-sm">
            <Mail className="h-4 w-4" />
            View sent emails
          </Link>
        </div>

        {!settings ? (
          <p className="text-ink-mute">{error || "Loading…"}</p>
        ) : (
          <form onSubmit={onSubmit} className="space-y-5">
            <div className="grid gap-5 lg:grid-cols-2 lg:items-start">
              <Card title="Notifications" subtitle="Who receives down / recovery alerts">
                <div className="mb-2 flex items-center justify-between gap-3">
                  <span className="text-xs font-medium uppercase tracking-wide text-ink-mute">
                    Alert emails
                  </span>
                  <span className="text-xs text-ink-mute">
                    {alertEmails.filter((e) => e.trim()).length}/{MAX_ALERT_EMAILS}
                  </span>
                </div>
                <ul className="space-y-2">
                  {alertEmails.map((email, index) => (
                    <li key={index} className="flex items-center gap-2">
                      <input
                        className="input"
                        type="email"
                        value={email}
                        onChange={(e) => updateAlertEmail(index, e.target.value)}
                        placeholder={`teammate${index + 1}@company.com`}
                        required={index === 0}
                        aria-label={`Alert email ${index + 1}`}
                      />
                      <button
                        type="button"
                        className="btn-icon shrink-0"
                        onClick={() => removeAlertEmail(index)}
                        disabled={alertEmails.length === 1}
                        aria-label={`Remove email ${index + 1}`}
                        title="Remove"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </li>
                  ))}
                </ul>
                <div className="mt-3 flex flex-wrap items-center gap-3">
                  <button
                    type="button"
                    className="btn-secondary h-9 px-3 text-sm"
                    onClick={addAlertEmail}
                    disabled={alertEmails.length >= MAX_ALERT_EMAILS}
                  >
                    <Plus className="h-4 w-4" />
                    Add email
                  </button>
                  <label className="flex items-center gap-2 text-sm text-ink">
                    <input
                      type="checkbox"
                      checked={settings.notification_enabled}
                      onChange={(e) =>
                        setSettings({ ...settings, notification_enabled: e.target.checked })
                      }
                      className="h-4 w-4 rounded border-ink/20"
                    />
                    Enable notifications
                  </label>
                </div>
              </Card>

              <Card title="SMTP sender" subtitle="Mailbox used to send alerts">
                <div
                  className={
                    settings.smtp_configured
                      ? "mb-4 rounded-xl bg-teal-soft/60 px-3.5 py-2.5 text-sm text-teal"
                      : "mb-4 rounded-xl bg-amber-50 px-3.5 py-2.5 text-sm text-alert-slow"
                  }
                >
                  {settings.smtp_configured
                    ? "Sender configured — alerts go from this mailbox."
                    : "Add SMTP details so SiteWatch can send alerts."}
                </div>

                <div className="grid gap-3 sm:grid-cols-[minmax(0,1.4fr)_7.5rem]">
                  <Field label="SMTP host">
                    <input
                      className="input"
                      placeholder="smtp.gmail.com"
                      value={settings.smtp_host}
                      onChange={(e) => setSettings({ ...settings, smtp_host: e.target.value })}
                    />
                  </Field>
                  <Field label="Port">
                    <input
                      className="input"
                      inputMode="numeric"
                      pattern="[0-9]*"
                      placeholder="587"
                      value={settings.smtp_port || ""}
                      onChange={(e) => {
                        const raw = e.target.value.replace(/\D/g, "");
                        setSettings({
                          ...settings,
                          smtp_port: raw === "" ? 0 : Math.min(65535, Number(raw)),
                        });
                      }}
                    />
                  </Field>
                </div>

                <div className="mt-3 grid gap-3">
                  <Field label="Username (Gmail login)">
                    <input
                      className="input"
                      value={settings.smtp_user}
                      onChange={(e) => setSettings({ ...settings, smtp_user: e.target.value })}
                    />
                  </Field>
                  <Field label="Password">
                    <div className="relative">
                      <input
                        className="input pr-11"
                        type={showSmtpPassword ? "text" : "password"}
                        placeholder={settings.smtp_configured ? "•••••••• (unchanged)" : "SMTP password"}
                        value={smtpPassword}
                        onChange={(e) => setSmtpPassword(e.target.value)}
                        autoComplete="new-password"
                      />
                      <button
                        type="button"
                        className="absolute right-2 top-1/2 -translate-y-1/2 rounded-lg p-1.5 text-ink-mute transition hover:bg-mist-deep hover:text-ink"
                        onClick={() => setShowSmtpPassword((v) => !v)}
                        aria-label={showSmtpPassword ? "Hide password" : "Show password"}
                      >
                        {showSmtpPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </button>
                    </div>
                  </Field>
                  <Field label="Sender name (shown in inbox)">
                    <input
                      className="input"
                      placeholder='SiteWatch <you@gmail.com>'
                      value={settings.smtp_from}
                      onChange={(e) => setSettings({ ...settings, smtp_from: e.target.value })}
                    />
                    <span className="mt-1.5 block text-xs text-ink-mute">
                      Recipients see the name, e.g. <span className="font-medium text-ink-soft">SiteWatch</span>
                    </span>
                  </Field>
                </div>

                <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
                  <label className="flex items-start gap-2 text-sm text-ink">
                    <input
                      type="checkbox"
                      checked={settings.smtp_use_tls}
                      onChange={(e) => setSettings({ ...settings, smtp_use_tls: e.target.checked })}
                      className="mt-0.5 h-4 w-4 rounded border-ink/20"
                    />
                    <span>
                      Use encryption
                      <span className="mt-0.5 block text-xs text-ink-mute">587 STARTTLS · 465 SSL</span>
                    </span>
                  </label>
                  <button type="button" className="btn-secondary h-9 px-3 text-sm" onClick={sendTest}>
                    Send test email
                  </button>
                </div>
              </Card>
            </div>

            <div className="grid gap-5 lg:grid-cols-2">
              <Card title="Monitoring thresholds" subtitle="When a site is marked down or recovered">
                <div className="grid grid-cols-3 gap-3">
                  <Field label="Slow (ms)">
                    <input
                      className="input"
                      inputMode="numeric"
                      pattern="[0-9]*"
                      value={settings.slow_threshold_ms || ""}
                      onChange={(e) => {
                        const raw = e.target.value.replace(/\D/g, "");
                        setSettings({
                          ...settings,
                          slow_threshold_ms: raw === "" ? 0 : Number(raw),
                        });
                      }}
                    />
                  </Field>
                  <Field label="Fails → DOWN">
                    <input
                      className="input"
                      inputMode="numeric"
                      pattern="[0-9]*"
                      value={settings.failure_threshold || ""}
                      onChange={(e) => {
                        const raw = e.target.value.replace(/\D/g, "");
                        setSettings({
                          ...settings,
                          failure_threshold: raw === "" ? 0 : Number(raw),
                        });
                      }}
                    />
                  </Field>
                  <Field label="OK → UP">
                    <input
                      className="input"
                      inputMode="numeric"
                      pattern="[0-9]*"
                      value={settings.recovery_threshold || ""}
                      onChange={(e) => {
                        const raw = e.target.value.replace(/\D/g, "");
                        setSettings({
                          ...settings,
                          recovery_threshold: raw === "" ? 0 : Number(raw),
                        });
                      }}
                    />
                  </Field>
                </div>
              </Card>

              <Card title="Admin password" subtitle={`Signed in as ${settings.email}`}>
                <Field label="New password">
                  <div className="relative max-w-md">
                    <input
                      className="input pr-11"
                      type={showAdminPassword ? "text" : "password"}
                      placeholder="Leave blank to keep current"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      autoComplete="new-password"
                    />
                    <button
                      type="button"
                      className="absolute right-2 top-1/2 -translate-y-1/2 rounded-lg p-1.5 text-ink-mute transition hover:bg-mist-deep hover:text-ink"
                      onClick={() => setShowAdminPassword((v) => !v)}
                      aria-label={showAdminPassword ? "Hide password" : "Show password"}
                    >
                      {showAdminPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  </div>
                </Field>
              </Card>
            </div>

            <div className="flex flex-col-reverse items-stretch gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="min-h-[1.25rem] text-sm">
                {message && <p className="text-teal">{message}</p>}
                {error && <p className="text-alert-down">{error}</p>}
              </div>
              <button className="btn-primary h-11 px-8 sm:min-w-[10rem]" disabled={loading}>
                {loading ? "Saving…" : "Save settings"}
              </button>
            </div>
          </form>
        )}
      </div>
    </Protected>
  );
}

function Card({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="surface rounded-2xl p-5 shadow-soft sm:rounded-3xl sm:p-6">
      <div className="mb-4">
        <h2 className="font-display text-base font-semibold text-ink sm:text-lg">{title}</h2>
        {subtitle ? <p className="mt-1 text-xs text-ink-mute sm:text-sm">{subtitle}</p> : null}
      </div>
      {children}
    </section>
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

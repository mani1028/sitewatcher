"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { Eye, EyeOff, Mail, Plus, Trash2 } from "lucide-react";
import { api, Settings } from "@/lib/api";

const MAX_ALERT_EMAILS = 20;
const MAX_WHATSAPP = 20;

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

function splitPhones(value: string): string[] {
  // Comma / semicolon / newline only — keep spaces inside a number (+1 346 …)
  const parts = value
    .split(/[,;\n]+/)
    .map((p) => p.trim())
    .filter(Boolean);
  return parts.length ? parts : [""];
}

function joinPhones(phones: string[]): string {
  return phones.map((p) => p.trim()).filter(Boolean).join(", ");
}

function isLikelyPhone(value: string): boolean {
  const digits = value.replace(/\D/g, "");
  // Accept local 10-digit Indian mobiles; backend will prefix +91
  if (digits.length === 10 && /^[6-9]/.test(digits)) return true;
  return digits.length >= 8 && digits.length <= 15;
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [alertEmails, setAlertEmails] = useState<string[]>([""]);
  const [whatsappNumbers, setWhatsappNumbers] = useState<string[]>([""]);
  const [password, setPassword] = useState("");
  const [smtpPassword, setSmtpPassword] = useState("");
  const [whatsappToken, setWhatsappToken] = useState("");
  const [showSmtpPassword, setShowSmtpPassword] = useState(false);
  const [showWhatsappToken, setShowWhatsappToken] = useState(false);
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
        setWhatsappNumbers(splitPhones(s.whatsapp_recipients || ""));
        setSmtpPassword(s.smtp_password || "");
        setWhatsappToken(s.plivo_auth_token || "");
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

  function updateWhatsappNumber(index: number, value: string) {
    setWhatsappNumbers((prev) => prev.map((phone, i) => (i === index ? value : phone)));
  }

  function addWhatsappNumber() {
    setWhatsappNumbers((prev) => (prev.length >= MAX_WHATSAPP ? prev : [...prev, ""]));
  }

  function removeWhatsappNumber(index: number) {
    setWhatsappNumbers((prev) => {
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
    const phones = whatsappNumbers.map((p) => p.trim()).filter(Boolean);
    if (settings.whatsapp_enabled && phones.length === 0) {
      setError("Add at least one WhatsApp recipient number (with country code).");
      setLoading(false);
      return;
    }
    if (phones.some((p) => !isLikelyPhone(p))) {
      setError("Each WhatsApp number needs a country code (e.g. +91… or +1 346…).");
      setLoading(false);
      return;
    }
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
        whatsapp_enabled: settings.whatsapp_enabled,
        plivo_auth_id: settings.plivo_auth_id,
        whatsapp_display_number: settings.whatsapp_display_number,
        whatsapp_recipients: joinPhones(whatsappNumbers),
        whatsapp_owner_scope: settings.whatsapp_owner_scope || "inhouse",
        whatsapp_template_name: settings.whatsapp_template_name,
        whatsapp_template_lang: settings.whatsapp_template_lang || "en_US",
      };
      if (smtpPassword) payload.smtp_password = smtpPassword;
      if (whatsappToken.trim()) payload.plivo_auth_token = whatsappToken.trim();
      if (password) payload.password = password;
      const updated = await api.updateSettings(payload);
      setSettings(updated);
      setAlertEmails(splitEmails(updated.alert_email));
      setWhatsappNumbers(splitPhones(updated.whatsapp_recipients || ""));
      setPassword("");
      setSmtpPassword("");
      setWhatsappToken("");
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

  async function saveWhatsappFields(): Promise<Settings> {
    if (!settings) throw new Error("Settings not loaded");
    const phones = whatsappNumbers.map((p) => p.trim()).filter(Boolean);
    if (phones.length === 0) {
      throw new Error("Add at least one WhatsApp recipient number (with country code).");
    }
    if (!(settings.plivo_auth_id || "").trim()) {
      throw new Error("Add Plivo Auth ID from Plivo Console, then retry.");
    }
    if (!whatsappToken.trim() && !settings.plivo_token_configured) {
      throw new Error("Paste Plivo Auth Token from Plivo Console, then retry.");
    }
    if (!(settings.whatsapp_display_number || "").trim()) {
      throw new Error("Add Plivo WhatsApp From number (e.g. +13464802677).");
    }
    if (!(settings.whatsapp_template_name || "").trim()) {
      throw new Error(
        "Add approved Template name (Plivo → WhatsApp → Templates). Required for permanent alerts.",
      );
    }
    const payload: Record<string, unknown> = {
      whatsapp_enabled: true,
      plivo_auth_id: settings.plivo_auth_id.trim(),
      whatsapp_display_number: settings.whatsapp_display_number.trim(),
      whatsapp_recipients: joinPhones(whatsappNumbers),
      whatsapp_owner_scope: settings.whatsapp_owner_scope || "inhouse",
      whatsapp_template_name: settings.whatsapp_template_name.trim(),
      whatsapp_template_lang: (settings.whatsapp_template_lang || "en_US").trim() || "en_US",
      whatsapp_phone_number_id: "",
      whatsapp_access_token: "",
    };
    if (whatsappToken.trim()) payload.plivo_auth_token = whatsappToken.trim();
    const updated = await api.updateSettings(payload);
    setSettings(updated);
    setWhatsappNumbers(splitPhones(updated.whatsapp_recipients || ""));
    setWhatsappToken("");
    return updated;
  }

  async function copyWebhook() {
    const url = settings?.whatsapp_webhook_url || "https://sitewatch.ai4bzr.com/api/webhooks/plivo/whatsapp";
    try {
      await navigator.clipboard.writeText(url);
      setMessage("Webhook URL copied. Paste it in Plivo WhatsApp settings.");
      setError("");
    } catch {
      setError(`Copy failed — select and copy: ${url}`);
    }
  }

  async function sendWhatsappTest() {
    setMessage("");
    setError("");
    try {
      const saved = await saveWhatsappFields();
      const to = saved.whatsapp_recipients || joinPhones(whatsappNumbers);
      const res = await api.testWhatsapp(to || undefined);
      setMessage(res.message || "Test WhatsApp queued. Check the recipient phones.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Test WhatsApp failed");
    }
  }

  return (
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
            Configure email and WhatsApp alerts. Digests show whether Frontend or Backend/API is down.
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
                <Field label="App password">
                  <div className="relative">
                    <input
                      className="input pr-11"
                      type={showSmtpPassword ? "text" : "password"}
                      placeholder="Gmail app password"
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

          <Card
            title="WhatsApp (Plivo)"
            subtitle="Alerts send via Plivo. Paste the webhook URL in your Plivo console."
          >
            <div className="mb-4 rounded-xl border border-ink/10 bg-white/70 px-3.5 py-3">
              <p className="text-xs font-medium uppercase tracking-wide text-ink-mute">
                Plivo webhook URL
              </p>
              <p className="mt-1 break-all font-mono text-sm text-ink">
                {settings.whatsapp_webhook_url ||
                  "https://sitewatch.ai4bzr.com/api/webhooks/plivo/whatsapp"}
              </p>
              <button type="button" className="btn-secondary mt-3 h-9 px-3 text-sm" onClick={copyWebhook}>
                Copy webhook URL
              </button>
              <p className="mt-2 text-xs text-ink-mute">
                In Plivo → WhatsApp → Webhooks, paste this URL for status / incoming events.
              </p>
            </div>

            <div
              className={
                settings.whatsapp_configured
                  ? "mb-4 rounded-xl bg-teal-soft/60 px-3.5 py-2.5 text-sm text-teal"
                  : "mb-4 rounded-xl bg-amber-50 px-3.5 py-2.5 text-sm text-alert-slow"
              }
            >
              {settings.whatsapp_configured
                ? "Permanent Plivo template alerts ready — includes Frontend vs Backend/API."
                : "Add Plivo Auth ID + Auth Token + From + approved Template name + recipients, then Save."}
            </div>

            <label className="mb-4 flex items-center gap-2 text-sm text-ink">
              <input
                type="checkbox"
                checked={settings.whatsapp_enabled}
                onChange={(e) => setSettings({ ...settings, whatsapp_enabled: e.target.checked })}
                className="h-4 w-4 rounded border-ink/20"
              />
              Enable WhatsApp alerts
            </label>

            <div className="grid gap-3 lg:grid-cols-2">
              <Field label="Plivo Auth ID">
                <input
                  className="input"
                  placeholder="From Plivo Console → Auth ID"
                  value={settings.plivo_auth_id || ""}
                  onChange={(e) => setSettings({ ...settings, plivo_auth_id: e.target.value })}
                />
              </Field>
              <Field label="From number (WhatsApp)">
                <input
                  className="input"
                  placeholder="+1 346 480 2677"
                  value={settings.whatsapp_display_number}
                  onChange={(e) =>
                    setSettings({ ...settings, whatsapp_display_number: e.target.value })
                  }
                />
              </Field>
              <Field label="Plivo Auth Token">
                <div className="relative">
                  <input
                    className="input pr-11"
                    type={showWhatsappToken ? "text" : "password"}
                    placeholder={
                      settings.plivo_token_configured
                        ? "Saved — paste new token to replace"
                        : "From Plivo Console → Auth Token"
                    }
                    value={whatsappToken}
                    onChange={(e) => setWhatsappToken(e.target.value)}
                    autoComplete="new-password"
                  />
                  <button
                    type="button"
                    className="absolute right-2 top-1/2 -translate-y-1/2 rounded-lg p-1.5 text-ink-mute transition hover:bg-mist-deep hover:text-ink"
                    onClick={() => setShowWhatsappToken((v) => !v)}
                    aria-label={showWhatsappToken ? "Hide token" : "Show token"}
                  >
                    {showWhatsappToken ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </Field>
              <Field label="Send WhatsApp for">
                <select
                  className="input"
                  value={settings.whatsapp_owner_scope || "inhouse"}
                  onChange={(e) =>
                    setSettings({
                      ...settings,
                      whatsapp_owner_scope: e.target.value as Settings["whatsapp_owner_scope"],
                    })
                  }
                >
                  <option value="inhouse">In-house sites only</option>
                  <option value="client">Client sites only</option>
                  <option value="all">All sites</option>
                </select>
              </Field>
              <Field label="Template name (required)">
                <input
                  className="input"
                  placeholder="e.g. sitewatch_alert"
                  value={settings.whatsapp_template_name || ""}
                  onChange={(e) =>
                    setSettings({ ...settings, whatsapp_template_name: e.target.value })
                  }
                />
              </Field>
              <Field label="Template language">
                <input
                  className="input"
                  placeholder="en_US"
                  value={settings.whatsapp_template_lang || "en_US"}
                  onChange={(e) =>
                    setSettings({ ...settings, whatsapp_template_lang: e.target.value })
                  }
                />
              </Field>
            </div>
            <div className="mt-3 rounded-xl border border-ink/10 bg-white/70 px-3.5 py-3 text-sm text-ink">
              <p className="font-medium">Permanent setup (one-time in Plivo)</p>
              <ol className="mt-2 list-decimal space-y-1 pl-4 text-ink-mute">
                <li>Plivo → WhatsApp → Templates → Create</li>
                <li>
                  Category <span className="font-mono text-ink">UTILITY</span>, language{" "}
                  <span className="font-mono text-ink">en_US</span>
                </li>
                <li>
                  Body example:{" "}
                  <span className="font-mono text-ink">SiteWatch alert: {"{{1}}"}</span>
                </li>
                <li>Submit and wait until status is Approved</li>
                <li>Paste exact template name above → Save → Send test WhatsApp</li>
              </ol>
            </div>

            <div className="mt-4">
              <div className="mb-2 flex items-center justify-between gap-3">
                <span className="text-xs font-medium uppercase tracking-wide text-ink-mute">
                  Recipient numbers
                </span>
                <span className="text-xs text-ink-mute">
                  {whatsappNumbers.filter((p) => p.trim()).length}/{MAX_WHATSAPP}
                </span>
              </div>
              <ul className="space-y-2">
                {whatsappNumbers.map((phone, index) => (
                  <li key={index} className="flex items-center gap-2">
                    <input
                      className="input"
                      type="tel"
                      value={phone}
                      onChange={(e) => updateWhatsappNumber(index, e.target.value)}
                      placeholder="+91 98XXXXXXXX"
                      inputMode="tel"
                      autoComplete="tel"
                      aria-label={`WhatsApp recipient ${index + 1}`}
                    />
                    <button
                      type="button"
                      className="btn-icon shrink-0"
                      onClick={() => removeWhatsappNumber(index)}
                      disabled={whatsappNumbers.length === 1}
                      aria-label={`Remove number ${index + 1}`}
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
                  onClick={addWhatsappNumber}
                  disabled={whatsappNumbers.length >= MAX_WHATSAPP}
                >
                  <Plus className="h-4 w-4" />
                  Add recipient
                </button>
                <button type="button" className="btn-secondary h-9 px-3 text-sm" onClick={sendWhatsappTest}>
                  Send test WhatsApp
                </button>
              </div>
              <p className="mt-2 text-xs text-ink-mute">
                Messages send from your Plivo WhatsApp number (
                {settings.whatsapp_display_number || "+1 346 480 2677"}). Enable WhatsApp per site on Edit
                website.
              </p>
            </div>
          </Card>

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

            <Card title="Admin password" subtitle="Optional — leave blank to keep current">
              <Field label="New password">
                <div className="relative">
                  <input
                    className="input pr-11"
                    type={showAdminPassword ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    autoComplete="new-password"
                    minLength={6}
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

          {error && <p className="text-sm text-alert-down">{error}</p>}
          {message && <p className="text-sm text-teal">{message}</p>}

          <button className="btn-primary" disabled={loading}>
            {loading ? "Saving…" : "Save settings"}
          </button>
        </form>
      )}
    </div>
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
    <div className="block">
      <span className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-ink-mute">{label}</span>
      {children}
    </div>
  );
}

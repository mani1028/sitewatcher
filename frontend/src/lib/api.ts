const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type SiteCategory = "portal" | "website" | "microservice" | "other";
export type SiteOwner = "inhouse" | "client";

export type Website = {
  id: number;
  name: string;
  url: string;
  health_url?: string | null;
  category: SiteCategory;
  owner: SiteOwner;
  enabled: boolean;
  check_interval: number;
  timeout: number;
  expected_status: number;
  monitor_ssl: boolean;
  maintenance_mode: boolean;
  whatsapp_alerts?: boolean;
  high_priority?: boolean;
  status: "UP" | "DOWN" | "SLOW" | "UNKNOWN" | "MAINTENANCE";
  consecutive_failures: number;
  consecutive_successes: number;
  last_checked_at: string | null;
  last_response_time: number | null;
  last_status_code: number | null;
  last_error: string | null;
  next_check_at: string | null;
  ssl_expires_at: string | null;
  uptime_percent: number;
  created_at: string;
};

export type Check = {
  id: number;
  website_id: number;
  status: string;
  status_code: number | null;
  response_time: number | null;
  error_type: string | null;
  error_message: string | null;
  checked_at: string;
};

export type Incident = {
  id: number;
  website_id: number;
  website_name?: string | null;
  website_url?: string | null;
  started_at: string;
  resolved_at: string | null;
  duration_seconds: number | null;
  reason: string;
  status: string;
};

export type Dashboard = {
  total: number;
  up: number;
  down: number;
  slow: number;
  maintenance: number;
  overall_uptime: number;
  websites: Website[];
  recent_incidents: Incident[];
};

export type Settings = {
  email: string;
  alert_email: string;
  notification_enabled: boolean;
  slow_threshold_ms: number;
  failure_threshold: number;
  recovery_threshold: number;
  smtp_host: string;
  smtp_port: number;
  smtp_user: string;
  smtp_from: string;
  smtp_use_tls: boolean;
  smtp_password?: string;
  smtp_configured: boolean;
  whatsapp_enabled: boolean;
  whatsapp_phone_number_id?: string;
  whatsapp_display_number: string;
  whatsapp_recipients: string;
  whatsapp_owner_scope: "inhouse" | "client" | "all";
  whatsapp_template_name: string;
  whatsapp_template_lang: string;
  whatsapp_token_configured?: boolean;
  whatsapp_configured: boolean;
  plivo_auth_id: string;
  plivo_auth_token?: string;
  plivo_token_configured: boolean;
  whatsapp_webhook_url: string;
};

export type NotificationLog = {
  id: number;
  website_id: number | null;
  incident_id: number | null;
  kind: string;
  subject: string;
  sent_to: string;
  success: boolean;
  created_at: string;
};

export type NotificationPage = {
  items: NotificationLog[];
  total: number;
  page: number;
  limit: number;
  pages: number;
};

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("sitewatch_token");
}

export function setToken(token: string) {
  localStorage.setItem("sitewatch_token", token);
}

export function clearToken() {
  localStorage.removeItem("sitewatch_token");
}

export function isLoggedIn() {
  return Boolean(getToken());
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };
  if (token) {
    (headers as Record<string, string>)["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_URL}/api${path}`, {
    ...options,
    headers,
  });

  if (res.status === 401) {
    clearToken();
    if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
      const returnTo = `${window.location.pathname}${window.location.search}`;
      window.location.href = `/login?returnTo=${encodeURIComponent(returnTo)}`;
    }
    throw new Error("Unauthorized");
  }

  if (!res.ok) {
    let detail = "Request failed";
    try {
      const data = await res.json();
      detail = data.detail || detail;
    } catch {
      // ignore
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  login: (email: string, password: string) =>
    request<{ access_token: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  dashboard: () => request<Dashboard>("/dashboard"),
  website: (id: number) => request<Website>(`/websites/${id}`),
  createWebsite: (payload: Record<string, unknown>) =>
    request<Website>("/websites", { method: "POST", body: JSON.stringify(payload) }),
  updateWebsite: (id: number, payload: Record<string, unknown>) =>
    request<Website>(`/websites/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteWebsite: (id: number) =>
    request<{ ok: boolean }>(`/websites/${id}`, { method: "DELETE" }),
  checks: (id: number, hours = 24) => request<Check[]>(`/websites/${id}/checks?hours=${hours}`),
  websiteIncidents: (id: number) => request<Incident[]>(`/websites/${id}/incidents`),
  incidents: (status?: string) =>
    request<Incident[]>(`/incidents${status ? `?status_filter=${status}` : ""}`),
  settings: () => request<Settings>("/settings"),
  updateSettings: (payload: Record<string, unknown>) =>
    request<Settings>("/settings", { method: "PUT", body: JSON.stringify(payload) }),
  testEmail: () => request<{ ok: boolean }>("/settings/test-email", { method: "POST", body: "{}" }),
  testWhatsapp: (to?: string) =>
    request<{ ok: boolean; message?: string }>("/settings/test-whatsapp", {
      method: "POST",
      body: JSON.stringify(to ? { to } : {}),
    }),
  notifications: (page = 1, limit = 20, filters?: { kind?: string; status?: string }) => {
    const params = new URLSearchParams({ page: String(page), limit: String(limit) });
    if (filters?.kind) params.set("kind", filters.kind);
    if (filters?.status) params.set("status", filters.status);
    return request<NotificationPage>(`/notifications?${params.toString()}`);
  },
};

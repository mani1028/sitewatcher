export function formatMs(ms: number | null | undefined) {
  if (ms == null) return "—";
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.round(ms)}ms`;
}

/** Short human-readable error for dense lists (full text via title tooltip). */
export function shortError(message: string | null | undefined): string {
  if (!message) return "";
  const m = message.toLowerCase();
  if (m.includes("name or service not known") || m.includes("nodename nor servname")) return "DNS not found";
  if (m.includes("certificate") || m.includes("ssl") || m.includes("tls")) return "SSL/TLS error";
  if (m.includes("timed out") || m.includes("timeout")) return "Timed out";
  if (m.includes("connection refused")) return "Connection refused";
  if (m.includes("connection reset")) return "Connection reset";
  if (m.includes("unreachable")) return "Unreachable";
  if (m.includes("401") || m.includes("unauthorized")) return "Unauthorized";
  if (m.includes("403") || m.includes("forbidden")) return "Forbidden";
  if (m.includes("404")) return "Not found (404)";
  if (m.includes("500") || m.includes("502") || m.includes("503") || m.includes("504")) return "Server error";
  const clean = message.replace(/^\[.*?\]\s*/, "").trim();
  return clean.length > 42 ? `${clean.slice(0, 40)}…` : clean;
}

export function formatDuration(seconds: number | null | undefined) {
  if (seconds == null) return "—";
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  const hours = Math.floor(mins / 60);
  const remMins = mins % 60;
  if (hours) return `${hours}h ${remMins}m`;
  if (mins) return `${mins}m ${secs}s`;
  return `${secs}s`;
}

export function formatTime(iso: string | null | undefined) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export type SiteLike = {
  status: string;
  consecutive_failures?: number;
  consecutive_successes?: number;
  maintenance_mode?: boolean;
};

/** Visual status used in the UI (includes FAILING / RECOVERING). */
export function displayStatus(site: SiteLike): string {
  if (site.maintenance_mode || site.status === "MAINTENANCE") return "MAINTENANCE";
  if (site.status === "DOWN") {
    if ((site.consecutive_successes || 0) > 0) return "RECOVERING";
    return "DOWN";
  }
  if ((site.consecutive_failures || 0) > 0) return "FAILING";
  return site.status;
}

export function statusLabel(status: string) {
  switch (status) {
    case "UP":
      return "Operational";
    case "DOWN":
      return "Down";
    case "FAILING":
      return "Failing";
    case "RECOVERING":
      return "Recovering";
    case "SLOW":
      return "Slow";
    case "MAINTENANCE":
      return "Maintenance";
    default:
      return "Unknown";
  }
}

export function statusRank(status: string): number {
  switch (status) {
    case "DOWN":
      return 0;
    case "FAILING":
      return 1;
    case "RECOVERING":
      return 2;
    case "SLOW":
      return 3;
    case "UNKNOWN":
      return 4;
    case "MAINTENANCE":
      return 5;
    case "UP":
      return 6;
    default:
      return 7;
  }
}

export function intervalLabel(seconds: number) {
  if (seconds === 60) return "1 minute";
  if (seconds === 300) return "5 minutes";
  if (seconds === 600) return "10 minutes";
  if (seconds === 3600) return "1 hour";
  if (seconds === 86400) return "1 day";
  return `${seconds}s`;
}

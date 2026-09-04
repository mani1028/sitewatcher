export function formatMs(ms: number | null | undefined) {
  if (ms == null) return "—";
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.round(ms)}ms`;
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
  maintenance_mode?: boolean;
};

/** Visual status used in the UI (includes FAILING before confirmed DOWN). */
export function displayStatus(site: SiteLike): string {
  if (site.maintenance_mode || site.status === "MAINTENANCE") return "MAINTENANCE";
  if (site.status === "DOWN") return "DOWN";
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
    case "SLOW":
      return 2;
    case "UNKNOWN":
      return 3;
    case "MAINTENANCE":
      return 4;
    case "UP":
      return 5;
    default:
      return 6;
  }
}

export function intervalLabel(seconds: number) {
  if (seconds === 60) return "1 minute";
  if (seconds === 300) return "5 minutes";
  if (seconds === 600) return "10 minutes";
  if (seconds === 3600) return "1 hour";
  return `${seconds}s`;
}

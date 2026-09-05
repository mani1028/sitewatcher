import clsx from "clsx";

const DOT: Record<string, string> = {
  UP: "bg-alert-up",
  DOWN: "bg-alert-down",
  FAILING: "bg-alert-down",
  RECOVERING: "bg-alert-slow",
  SLOW: "bg-alert-slow",
  MAINTENANCE: "bg-ink-mute",
  UNKNOWN: "bg-ink-mute",
  open: "bg-alert-down",
  resolved: "bg-alert-up",
};

export function StatusDot({
  status,
  pulse = false,
  className,
}: {
  status: string;
  pulse?: boolean;
  className?: string;
}) {
  const shouldPulse = pulse || status === "DOWN" || status === "FAILING" || status === "RECOVERING";
  return (
    <span
      className={clsx(
        "inline-block h-2.5 w-2.5 shrink-0 rounded-full",
        DOT[status] || "bg-ink-mute",
        shouldPulse && "animate-pulse-dot",
        className,
      )}
      aria-hidden
    />
  );
}

const BADGE: Record<string, string> = {
  UP: "bg-teal-soft text-teal",
  DOWN: "bg-red-100 text-alert-down",
  FAILING: "bg-red-100 text-alert-down",
  RECOVERING: "bg-amber-100 text-alert-slow",
  SLOW: "bg-amber-100 text-alert-slow",
  MAINTENANCE: "bg-mist-deep text-ink-soft",
  UNKNOWN: "bg-mist-deep text-ink-mute",
};

export function StatusBadge({
  status,
  label,
  detail,
}: {
  status: string;
  label?: string;
  detail?: string;
}) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold tracking-wide",
        BADGE[status] || BADGE.UNKNOWN,
      )}
    >
      <StatusDot status={status} className="h-1.5 w-1.5" />
      {label || status}
      {detail ? <span className="font-normal opacity-80">{detail}</span> : null}
    </span>
  );
}

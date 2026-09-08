"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { StatusDot } from "@/components/StatusDot";
import { api, Incident } from "@/lib/api";
import { formatDuration, formatTime } from "@/lib/format";

export default function IncidentsPage() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [filter, setFilter] = useState<"" | "open" | "resolved">("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setIncidents(await api.incidents(filter || undefined));
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    }
  }, [filter]);

  useEffect(() => {
    load();
  }, [load]);

  return (
      <div className="animate-rise space-y-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end sm:justify-between sm:gap-4">
          <div>
            <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-ink-mute sm:text-xs">History</p>
            <h1 className="mt-1 font-display text-2xl font-semibold tracking-tight text-ink sm:text-3xl">Incidents</h1>
          </div>
          <div className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1 sm:mx-0 sm:overflow-visible sm:px-0 sm:pb-0">
            {(["", "open", "resolved"] as const).map((value) => (
              <button
                key={value || "all"}
                className={filter === value ? "btn-primary h-9 shrink-0 px-3 text-sm" : "btn-secondary h-9 shrink-0 px-3 text-sm"}
                onClick={() => setFilter(value)}
              >
                {value || "All"}
              </button>
            ))}
          </div>
        </div>

        {error && <p className="text-sm text-alert-down">{error}</p>}

        <div className="surface overflow-hidden rounded-3xl shadow-soft">
          {incidents.length === 0 ? (
            <p className="px-6 py-12 text-center text-sm text-ink-mute">No incidents found.</p>
          ) : (
            <ul className="divide-y divide-ink/5">
              {incidents.map((incident) => (
                <li key={incident.id}>
                  <Link
                    href={`/websites/${incident.website_id}`}
                    className="flex items-start gap-3 px-3 py-3.5 transition hover:bg-white/60 sm:items-center sm:gap-4 sm:px-5 sm:py-4"
                  >
                    <StatusDot status={incident.status === "open" ? "DOWN" : "UP"} className="mt-1.5 sm:mt-0" />
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-medium text-ink">
                        {incident.website_name || `Site #${incident.website_id}`}
                      </p>
                      <p className="truncate text-xs text-ink-mute">{incident.reason}</p>
                      <p className="mt-1 text-xs capitalize text-ink-mute sm:hidden">
                        {incident.status} · {formatDuration(incident.duration_seconds)} · {formatTime(incident.started_at)}
                      </p>
                    </div>
                    <div className="hidden shrink-0 text-right text-sm sm:block">
                      <p className="capitalize text-ink">{incident.status}</p>
                      <p className="text-xs text-ink-mute">
                        {formatDuration(incident.duration_seconds)} · {formatTime(incident.started_at)}
                      </p>
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
  );
}

"use client";

import { useCallback, useEffect, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Protected } from "@/components/Protected";
import { api, NotificationLog, NotificationPage } from "@/lib/api";
import { formatTime } from "@/lib/format";

const PAGE_SIZE = 20;

type FilterKey = "all" | "sent" | "failed" | "down" | "recovery" | "test";

const FILTERS: { key: FilterKey; label: string }[] = [
  { key: "all", label: "All" },
  { key: "sent", label: "Sent" },
  { key: "failed", label: "Failed" },
  { key: "down", label: "Down" },
  { key: "recovery", label: "Up" },
  { key: "test", label: "Test" },
];

function filterParams(filter: FilterKey): { kind?: string; status?: string } {
  if (filter === "sent" || filter === "failed") return { status: filter };
  if (filter === "down" || filter === "recovery" || filter === "test") return { kind: filter };
  return {};
}

function kindMeta(kind: string) {
  if (kind === "down") return { label: "Down", className: "bg-alert-down/15 text-alert-down" };
  if (kind === "recovery") return { label: "Up", className: "bg-teal-soft text-teal" };
  if (kind === "test") return { label: "Test", className: "bg-mist-deep text-ink-soft" };
  return { label: kind, className: "bg-mist-deep text-ink-soft" };
}

function recipientSummary(sentTo: string) {
  const recipients = sentTo
    .split(/[,;]+/)
    .map((e) => e.trim())
    .filter(Boolean);
  if (recipients.length === 0) return null;
  if (recipients.length === 1) return { text: recipients[0], title: recipients[0] };
  return { text: `${recipients.length} recipients`, title: recipients.join(", ") };
}

export default function EmailsPage() {
  const [data, setData] = useState<NotificationPage | null>(null);
  const [page, setPage] = useState(1);
  const [filter, setFilter] = useState<FilterKey>("all");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async (nextPage: number, nextFilter: FilterKey) => {
    setLoading(true);
    try {
      const result = await api.notifications(nextPage, PAGE_SIZE, filterParams(nextFilter));
      setData(result);
      setPage(result.page);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(page, filter);
  }, [load, page, filter]);

  function changeFilter(next: FilterKey) {
    setFilter(next);
    setPage(1);
  }

  return (
    <Protected>
      <div className="animate-rise space-y-5 sm:space-y-6">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-ink-mute sm:text-xs">
              History
            </p>
            <h1 className="mt-1 font-display text-2xl font-semibold tracking-tight text-ink sm:text-3xl">
              Emails
            </h1>
            <p className="mt-1.5 text-sm text-ink-soft">
              Sent alerts and tests. Failed emails are removed after 10 days.
            </p>
          </div>
          {data && (
            <p className="text-xs text-ink-mute sm:text-sm">
              {data.total} {data.total === 1 ? "email" : "emails"}
              {data.pages > 1 ? ` · page ${data.page}/${data.pages}` : ""}
            </p>
          )}
        </div>

        <div className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1 sm:mx-0 sm:flex-wrap sm:overflow-visible sm:px-0 sm:pb-0">
          {FILTERS.map((item) => (
            <button
              key={item.key}
              type="button"
              className={
                filter === item.key
                  ? "btn-primary h-9 shrink-0 px-3.5 text-sm"
                  : "btn-secondary h-9 shrink-0 px-3.5 text-sm"
              }
              onClick={() => changeFilter(item.key)}
            >
              {item.label}
            </button>
          ))}
        </div>

        {error && <p className="text-sm text-alert-down">{error}</p>}

        <div className="surface overflow-hidden rounded-2xl shadow-soft sm:rounded-3xl">
          {loading && !data ? (
            <p className="px-5 py-12 text-center text-sm text-ink-mute">Loading…</p>
          ) : !data || data.items.length === 0 ? (
            <p className="px-5 py-12 text-center text-sm text-ink-mute">
              {filter === "all" ? "No emails sent yet." : "No emails match this filter."}
            </p>
          ) : (
            <ul className="divide-y divide-ink/5">
              {data.items.map((n: NotificationLog) => {
                const kind = kindMeta(n.kind);
                const recipients = recipientSummary(n.sent_to);
                return (
                  <li
                    key={n.id}
                    className="flex items-start gap-3 px-3 py-3.5 sm:items-center sm:gap-4 sm:px-5 sm:py-3.5"
                  >
                    <span
                      className={`mt-0.5 shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide sm:mt-0 ${kind.className}`}
                    >
                      {kind.label}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                        <p className="truncate text-sm font-medium text-ink" title={n.subject}>
                          {n.subject}
                        </p>
                        <span
                          className={`rounded-full px-1.5 py-0.5 text-[10px] font-semibold uppercase ${
                            n.success ? "bg-teal-soft text-teal" : "bg-alert-down/15 text-alert-down"
                          }`}
                        >
                          {n.success ? "Sent" : "Failed"}
                        </span>
                      </div>
                      <p className="mt-0.5 text-xs text-ink-mute">
                        {formatTime(n.created_at)}
                        {recipients && (
                          <>
                            {" · "}
                            <span title={recipients.title}>{recipients.text}</span>
                          </>
                        )}
                      </p>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        {data && data.pages > 1 && (
          <div className="flex items-center justify-between gap-3">
            <button
              type="button"
              className="btn-secondary h-9 px-3 text-sm disabled:opacity-40"
              disabled={page <= 1 || loading}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              <ChevronLeft className="h-4 w-4" />
              Prev
            </button>
            <p className="text-xs text-ink-mute">
              {data.page} / {data.pages}
            </p>
            <button
              type="button"
              className="btn-secondary h-9 px-3 text-sm disabled:opacity-40"
              disabled={page >= data.pages || loading}
              onClick={() => setPage((p) => Math.min(data.pages, p + 1))}
            >
              Next
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        )}
      </div>
    </Protected>
  );
}

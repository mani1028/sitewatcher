"use client";

import Link from "next/link";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Pencil, Plus, Search, Zap } from "lucide-react";
import { StatusBadge, StatusDot } from "@/components/StatusDot";
import { WhatsAppIcon } from "@/components/WhatsAppIcon";
import { api, Dashboard, Website } from "@/lib/api";
import {
  displayStatus,
  failureLayer,
  formatMs,
  statusLabel,
  statusRank,
} from "@/lib/format";
import {
  SITE_CATEGORIES,
  categoryLabel,
  ownerBadgeClass,
  ownerLabel,
} from "@/lib/categories";
import type { SiteCategory, SiteOwner } from "@/lib/api";

type Filter = "all" | "down" | "failing" | "slow" | "up";
type CategoryFilter = "all" | SiteCategory;
type OwnerFilter = "all" | SiteOwner;

function parseFilter(value: string | null): Filter {
  if (value === "down" || value === "failing" || value === "slow" || value === "up") return value;
  return "all";
}

function parseOwner(value: string | null): OwnerFilter {
  if (value === "inhouse" || value === "client") return value;
  return "all";
}

function parseCategory(value: string | null): CategoryFilter {
  if (value === "portal" || value === "website" || value === "microservice" || value === "other") {
    return value;
  }
  return "all";
}

function DashboardContent() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const filter = parseFilter(searchParams.get("status"));
  const ownerFilter = parseOwner(searchParams.get("owner"));
  const categoryFilter = parseCategory(searchParams.get("type"));
  const query = searchParams.get("q") || "";

  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState("");

  function updateParams(patch: Record<string, string | null>) {
    const next = new URLSearchParams(searchParams.toString());
    for (const [key, value] of Object.entries(patch)) {
      if (!value || value === "all") next.delete(key);
      else next.set(key, value);
    }
    const qs = next.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  }

  const load = useCallback(async () => {
    try {
      const dash = await api.dashboard();
      setData(dash);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 20000);
    return () => clearInterval(id);
  }, [load]);

  const failingCount = useMemo(
    () => (data ? data.websites.filter((w) => displayStatus(w) === "FAILING").length : 0),
    [data],
  );

  const problemCount = useMemo(
    () => (data ? data.down + failingCount + data.slow : 0),
    [data, failingCount],
  );

  const ownerCounts = useMemo(() => {
    if (!data) return { inhouse: 0, client: 0 };
    return {
      inhouse: data.websites.filter((w) => (w.owner || "inhouse") === "inhouse").length,
      client: data.websites.filter((w) => w.owner === "client").length,
    };
  }, [data]);

  const filtered = useMemo(() => {
    if (!data) return [] as Website[];
    const q = query.trim().toLowerCase();
    return [...data.websites]
      .filter((site) => {
        const status = displayStatus(site);
        if (filter === "down" && status !== "DOWN") return false;
        if (filter === "failing" && status !== "FAILING") return false;
        if (filter === "slow" && status !== "SLOW") return false;
        if (filter === "up" && status !== "UP") return false;
        const owner = site.owner || "inhouse";
        if (ownerFilter !== "all" && owner !== ownerFilter) return false;
        const cat = site.category || "website";
        if (categoryFilter !== "all" && cat !== categoryFilter) return false;
        if (!q) return true;
        return (
          site.name.toLowerCase().includes(q) ||
          site.url.toLowerCase().includes(q) ||
          categoryLabel(cat).toLowerCase().includes(q) ||
          ownerLabel(owner).toLowerCase().includes(q)
        );
      })
      .sort((a, b) => {
        const rank = statusRank(displayStatus(a)) - statusRank(displayStatus(b));
        if (rank !== 0) return rank;
        return a.name.localeCompare(b.name);
      });
  }, [data, filter, ownerFilter, categoryFilter, query]);

  const grouped = useMemo(() => {
    if (ownerFilter !== "all") {
      return [{ key: ownerFilter as SiteOwner, sites: filtered }];
    }
    return [
      { key: "inhouse" as const, sites: filtered.filter((s) => (s.owner || "inhouse") === "inhouse") },
      { key: "client" as const, sites: filtered.filter((s) => s.owner === "client") },
    ].filter((g) => g.sites.length > 0);
  }, [filtered, ownerFilter]);

  return (
    <div className="animate-rise space-y-6 sm:space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-2 sm:gap-4">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-ink-mute sm:text-xs">
            Overview
          </p>
          <h1 className="mt-1 font-display text-2xl font-semibold tracking-tight text-ink sm:text-3xl">
            Dashboard
          </h1>
        </div>
        <p className="text-xs text-ink-mute sm:text-sm">Auto-refreshes every 20s</p>
      </div>

      {error && <p className="text-sm text-alert-down">{error}</p>}

      {data && (
        <>
          {problemCount > 0 && (
            <div className="rounded-2xl border border-alert-down/20 bg-red-50 px-4 py-3 text-sm text-alert-down sm:px-5 sm:py-4">
              <span className="font-semibold">
                {data.down} down
                {failingCount ? ` · ${failingCount} failing` : ""}
                {data.slow ? ` · ${data.slow} slow` : ""}
              </span>
              <span className="text-alert-down/80"> — tap a status above the list to focus.</span>
            </div>
          )}

          <section className="grid grid-cols-2 gap-2 sm:gap-3 md:grid-cols-5">
            <StatButton
              label="Websites"
              value={String(data.total)}
              active={filter === "all"}
              onClick={() => updateParams({ status: null })}
            />
            <StatButton
              label="UP"
              value={String(data.up)}
              tone="up"
              active={filter === "up"}
              onClick={() => updateParams({ status: "up" })}
            />
            <StatButton
              label="DOWN"
              value={String(data.down)}
              tone="down"
              active={filter === "down"}
              onClick={() => updateParams({ status: "down" })}
            />
            <StatButton
              label="SLOW"
              value={String(data.slow)}
              tone="slow"
              active={filter === "slow"}
              onClick={() => updateParams({ status: "slow" })}
            />
            <div className="col-span-2 rounded-2xl border border-ink/5 bg-white/70 px-3 py-2.5 sm:px-4 sm:py-3 md:col-span-1">
              <p className="text-[11px] uppercase tracking-wide text-ink-mute sm:text-xs">
                Overall uptime
              </p>
              <p className="mt-1 font-display text-2xl font-semibold text-ink sm:mt-2 sm:text-3xl">
                {data.overall_uptime.toFixed(2)}%
              </p>
            </div>
          </section>

          <section>
            <div className="mb-4 flex flex-col gap-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <h2 className="font-display text-lg font-semibold text-ink sm:text-xl">Websites</h2>
                <div className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1 sm:mx-0 sm:overflow-visible sm:px-0 sm:pb-0">
                  {(
                    [
                      ["all", "All", data.total],
                      ["inhouse", "In-house", ownerCounts.inhouse],
                      ["client", "Client", ownerCounts.client],
                    ] as const
                  ).map(([value, label, count]) => (
                    <button
                      key={value}
                      type="button"
                      className={
                        ownerFilter === value
                          ? value === "client"
                            ? "h-9 shrink-0 rounded-xl bg-amber-100 px-3 text-sm font-medium text-amber-900 ring-1 ring-amber-200"
                            : "btn-primary h-9 shrink-0 px-3 text-sm"
                          : "btn-secondary h-9 shrink-0 px-3 text-sm"
                      }
                      onClick={() => updateParams({ owner: value === "all" ? null : value })}
                    >
                      {label}
                      <span className="ml-1.5 opacity-70">({count})</span>
                    </button>
                  ))}
                </div>
              </div>

              <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                <div className="relative flex-1">
                  <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-mute" />
                  <input
                    className="input !pl-10"
                    placeholder="Search by name or URL…"
                    value={query}
                    onChange={(e) => updateParams({ q: e.target.value || null })}
                  />
                </div>
                <label className="block shrink-0 sm:w-44">
                  <span className="sr-only">Type</span>
                  <select
                    className="input"
                    value={categoryFilter}
                    onChange={(e) =>
                      updateParams({
                        type: e.target.value === "all" ? null : e.target.value,
                      })
                    }
                  >
                    <option value="all">All types</option>
                    {SITE_CATEGORIES.map((c) => (
                      <option key={c.value} value={c.value}>
                        {c.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block shrink-0 sm:w-40">
                  <span className="sr-only">Status</span>
                  <select
                    className="input"
                    value={filter}
                    onChange={(e) =>
                      updateParams({
                        status: e.target.value === "all" ? null : e.target.value,
                      })
                    }
                  >
                    <option value="all">All statuses</option>
                    <option value="down">Down{data.down ? ` (${data.down})` : ""}</option>
                    <option value="failing">
                      Failing{failingCount ? ` (${failingCount})` : ""}
                    </option>
                    <option value="slow">Slow{data.slow ? ` (${data.slow})` : ""}</option>
                    <option value="up">Up</option>
                  </select>
                </label>
              </div>
            </div>

            {data.websites.length === 0 ? (
              <div className="surface rounded-2xl px-5 py-12 text-center shadow-soft sm:rounded-3xl sm:px-6 sm:py-14">
                <p className="font-display text-lg text-ink">No projects yet</p>
                <p className="mt-2 text-sm text-ink-soft">
                  Add jobneedx.com, staging, APIs — anything you need watched.
                </p>
                <Link href="/websites/new" className="btn-primary mt-6 inline-flex">
                  <Plus className="h-4 w-4" />
                  Add your first site
                </Link>
              </div>
            ) : filtered.length === 0 ? (
              <div className="surface rounded-2xl px-5 py-10 text-center text-sm text-ink-mute shadow-soft sm:rounded-3xl sm:px-6">
                No websites match this filter.
                <button
                  type="button"
                  className="ml-2 text-teal underline-offset-2 hover:underline"
                  onClick={() => router.replace(pathname, { scroll: false })}
                >
                  Clear filters
                </button>
              </div>
            ) : (
              <div className="space-y-6">
                {grouped.map((group) => (
                  <div key={group.key}>
                    {ownerFilter === "all" && (
                      <div className="mb-2 flex items-center gap-2 px-1">
                        <span
                          className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${ownerBadgeClass(group.key)}`}
                        >
                          {ownerLabel(group.key)}
                        </span>
                        <span className="text-xs text-ink-mute">{group.sites.length}</span>
                      </div>
                    )}
                    <div className="surface overflow-hidden rounded-2xl shadow-soft sm:rounded-3xl">
                      <ul className="divide-y divide-ink/5">
                        {group.sites.map((site) => (
                          <SiteRow key={site.id} site={site} />
                        ))}
                      </ul>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}

export default function DashboardPage() {
  return (
    <Suspense
      fallback={<p className="text-ink-mute">Loading dashboard…</p>}
    >
      <DashboardContent />
    </Suspense>
  );
}

function SiteRow({ site }: { site: Website }) {
  const status = displayStatus(site);
  const isProblem = status === "DOWN" || status === "FAILING";
  const badgeDetail =
    status === "FAILING"
      ? `· ${site.consecutive_failures} fail${site.consecutive_failures === 1 ? "" : "s"}`
      : status === "RECOVERING"
        ? `· ${site.consecutive_successes} ok`
        : undefined;
  const owner = site.owner || "inhouse";

  return (
    <li>
      <div
        className={
          isProblem
            ? "bg-red-50/70 transition hover:bg-red-50"
            : status === "SLOW"
              ? "bg-amber-50/50 transition hover:bg-amber-50/80"
              : "transition hover:bg-white/70"
        }
      >
        <div className="flex items-start gap-2 px-3 py-3.5 sm:items-center sm:gap-3 sm:px-5 sm:py-4">
          <Link
            href={`/websites/${site.id}`}
            className="flex min-w-0 flex-1 items-start gap-3 sm:items-center sm:gap-4"
          >
            <StatusDot status={status} className="mt-1.5 h-3 w-3 shrink-0 sm:mt-0" />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <p className="truncate font-medium text-ink">{site.name}</p>
                <StatusBadge status={status} label={statusLabel(status)} detail={badgeDetail} />
                <span
                  className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${ownerBadgeClass(owner)}`}
                >
                  {ownerLabel(owner)}
                </span>
                <span className="rounded-full bg-mist-deep px-2 py-0.5 text-[11px] font-medium text-ink-soft">
                  {categoryLabel(site.category)}
                </span>
              </div>
              <p className="mt-0.5 truncate font-mono text-xs text-ink-mute">
                {site.url.replace(/^https?:\/\//, "")}
              </p>
              {isProblem && site.last_error ? (
                <p className="mt-1 truncate text-xs text-alert-down" title={site.last_error}>
                  <span className="font-semibold">{failureLayer(site.last_error)}</span>
                  {" · "}
                  {site.last_error}
                </p>
              ) : null}
              <p className="mt-1 text-xs text-ink-mute sm:hidden">
                <span
                  className={
                    isProblem
                      ? "font-semibold text-alert-down"
                      : status === "SLOW"
                        ? "font-semibold text-alert-slow"
                        : "text-ink"
                  }
                >
                  {status === "DOWN" ? "DOWN" : formatMs(site.last_response_time)}
                </span>
                {" · "}
                {site.uptime_percent.toFixed(2)}% uptime
              </p>
            </div>
            <div className="hidden shrink-0 text-right sm:block">
              <p
                className={
                  isProblem
                    ? "font-mono text-sm font-semibold text-alert-down"
                    : status === "SLOW"
                      ? "font-mono text-sm font-semibold text-alert-slow"
                      : "font-mono text-sm text-ink"
                }
              >
                {status === "DOWN" ? "DOWN" : formatMs(site.last_response_time)}
              </p>
              <p className="text-xs text-ink-mute">{site.uptime_percent.toFixed(2)}% uptime</p>
            </div>
          </Link>
          {site.high_priority ? (
            <span
              className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-amber-100 text-amber-700"
              title="High priority — re-checks every 30s while down"
              aria-label="High priority"
            >
              <Zap className="h-4 w-4" />
            </span>
          ) : null}
          {site.whatsapp_alerts ? (
            <span
              className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#25D366]/15 text-[#25D366]"
              title="WhatsApp alerts enabled"
              aria-label="WhatsApp alerts enabled"
            >
              <WhatsAppIcon className="h-4 w-4" />
            </span>
          ) : null}
          <Link
            href={`/websites/${site.id}/edit`}
            className="btn-icon shrink-0"
            aria-label={`Edit ${site.name}`}
            title="Edit"
          >
            <Pencil className="h-4 w-4" />
          </Link>
        </div>
      </div>
    </li>
  );
}

function StatButton({
  label,
  value,
  tone,
  active,
  onClick,
}: {
  label: string;
  value: string;
  tone?: "up" | "down" | "slow";
  active?: boolean;
  onClick: () => void;
}) {
  const color =
    tone === "up"
      ? "text-alert-up"
      : tone === "down"
        ? "text-alert-down"
        : tone === "slow"
          ? "text-alert-slow"
          : "text-ink";
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        active
          ? "rounded-2xl border border-teal/30 bg-teal-soft/70 px-3 py-2.5 text-left transition sm:px-4 sm:py-3"
          : "rounded-2xl border border-ink/5 bg-white/70 px-3 py-2.5 text-left transition hover:bg-white sm:px-4 sm:py-3"
      }
    >
      <p className="text-[11px] uppercase tracking-wide text-ink-mute sm:text-xs">{label}</p>
      <p className={`mt-1 font-display text-2xl font-semibold sm:mt-2 sm:text-3xl ${color}`}>{value}</p>
    </button>
  );
}

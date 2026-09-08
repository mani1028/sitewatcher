"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Activity, LayoutDashboard, LogOut, Mail, Plus, Settings, Siren } from "lucide-react";
import clsx from "clsx";
import { clearToken } from "@/lib/api";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/incidents", label: "Incidents", icon: Siren },
  { href: "/emails", label: "Emails", icon: Mail },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();

  function logout() {
    clearToken();
    router.push("/login");
  }

  return (
    <div className="min-h-screen pb-[4.75rem] md:pb-0">
      <header className="sticky top-0 z-20 border-b border-ink/5 bg-white/75 backdrop-blur-md">
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-3 px-4 sm:h-[3.75rem] sm:gap-5 sm:px-5">
          <Link href="/dashboard" className="group flex min-w-0 shrink-0 items-center gap-2.5">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-teal text-white transition group-hover:bg-teal-bright sm:h-9 sm:w-9">
              <Activity className="h-4 w-4" />
            </span>
            <div className="min-w-0">
              <p className="font-display text-base font-semibold leading-none tracking-tight text-ink sm:text-[1.05rem]">
                SiteWatch
              </p>
              <p className="mt-1 hidden text-[10px] uppercase tracking-[0.14em] text-ink-mute sm:block">
                Monitoring
              </p>
            </div>
          </Link>

          <nav className="ml-2 hidden items-center gap-0.5 md:flex">
            {NAV.map((item) => {
              const active =
                item.href === "/dashboard"
                  ? pathname.startsWith("/dashboard") || pathname.startsWith("/websites")
                  : pathname.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={clsx(
                    "rounded-lg px-3 py-2 text-sm transition",
                    active
                      ? "bg-teal/10 font-semibold text-teal"
                      : "text-ink-soft hover:bg-mist/80 hover:text-ink",
                  )}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>

          <div className="ml-auto flex items-center gap-2">
            <Link
              href="/websites/new"
              className="btn-primary h-9 gap-1.5 px-3.5 text-sm sm:h-10 sm:px-4"
            >
              <Plus className="h-4 w-4" />
              <span className="hidden sm:inline">Add site</span>
            </Link>
            <button
              type="button"
              className="btn-icon"
              aria-label="Log out"
              title="Log out"
              onClick={logout}
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6 sm:px-5 sm:py-8">{children}</main>

      <nav className="fixed inset-x-0 bottom-0 z-20 border-t border-ink/8 bg-white/90 backdrop-blur-md md:hidden">
        <div className="mx-auto grid max-w-6xl grid-cols-4 px-1 pb-[max(0.35rem,env(safe-area-inset-bottom))] pt-1">
          {NAV.map((item) => {
            const active =
              item.href === "/dashboard"
                ? pathname.startsWith("/dashboard") || pathname.startsWith("/websites")
                : pathname.startsWith(item.href);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={clsx(
                  "flex flex-col items-center gap-0.5 rounded-xl px-1 py-2 text-[10px] font-medium transition",
                  active ? "text-teal" : "text-ink-mute",
                )}
              >
                <span
                  className={clsx(
                    "flex h-8 w-8 items-center justify-center rounded-full transition",
                    active ? "bg-teal/10" : "bg-transparent",
                  )}
                >
                  <Icon className="h-4 w-4" />
                </span>
                {item.label}
              </Link>
            );
          })}
        </div>
      </nav>
    </div>
  );
}

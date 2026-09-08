"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { isLoggedIn } from "@/lib/api";
import { AppShell } from "@/components/AppShell";

export function Protected({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!isLoggedIn()) {
      const search = typeof window !== "undefined" ? window.location.search : "";
      const returnTo = `${pathname}${search}`;
      const target =
        returnTo && !returnTo.startsWith("/login")
          ? `/login?returnTo=${encodeURIComponent(returnTo)}`
          : "/login";
      router.replace(target);
      return;
    }
    setReady(true);
  }, [router, pathname]);

  if (!ready) {
    return (
      <div className="flex min-h-screen items-center justify-center text-ink-mute">
        Checking session…
      </div>
    );
  }

  return <AppShell>{children}</AppShell>;
}

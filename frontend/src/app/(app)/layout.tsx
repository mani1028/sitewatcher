"use client";

import { Protected } from "@/components/Protected";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return <Protected>{children}</Protected>;
}

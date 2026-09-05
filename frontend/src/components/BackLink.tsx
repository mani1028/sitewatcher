import Link from "next/link";
import { ArrowLeft } from "lucide-react";

export function BackLink({ href, label }: { href: string; label: string }) {
  return (
    <Link
      href={href}
      className="inline-flex h-9 items-center gap-2 rounded-full border border-ink/10 bg-white/80 px-3.5 text-sm font-medium text-ink-soft transition hover:border-ink/15 hover:bg-white hover:text-ink"
    >
      <ArrowLeft className="h-4 w-4" />
      {label}
    </Link>
  );
}

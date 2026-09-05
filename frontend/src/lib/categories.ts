import type { SiteCategory, SiteOwner } from "@/lib/api";

/** Technical type — independent of who owns the site. */
export const SITE_CATEGORIES: { value: SiteCategory; label: string }[] = [
  { value: "website", label: "Website" },
  { value: "portal", label: "Portal" },
  { value: "microservice", label: "Microservices" },
  { value: "other", label: "Other" },
];

/** Ownership — separate from type so client and in-house never mix in filters. */
export const SITE_OWNERS: { value: SiteOwner; label: string }[] = [
  { value: "inhouse", label: "In-house" },
  { value: "client", label: "Client" },
];

export function categoryLabel(category: string | null | undefined): string {
  const found = SITE_CATEGORIES.find((c) => c.value === category);
  return found?.label || "Website";
}

export function ownerLabel(owner: string | null | undefined): string {
  const found = SITE_OWNERS.find((o) => o.value === owner);
  return found?.label || "In-house";
}

export function ownerBadgeClass(owner: string | null | undefined): string {
  return owner === "client"
    ? "bg-amber-100 text-amber-900 ring-1 ring-amber-200/80"
    : "bg-teal-soft text-teal ring-1 ring-teal/20";
}

"""One-shot import of client websites (owner=client, interval=1 day)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from urllib.parse import urlparse

from sqlalchemy import func, select

from app.database import SessionLocal
from app.models import SiteCategory, SiteOwner, Website

# name, url, category — APK / missing-URL entries omitted
CLIENT_SITES: list[tuple[str, str, str]] = [
    ("Ante womens clothing", "https://ante-web.ai4devops.online/", SiteCategory.WEBSITE.value),
    ("avista", "https://avistha.ai4devops.online/", SiteCategory.WEBSITE.value),
    ("Cori mint indian kitchen", "https://corimint.ai4devops.online/", SiteCategory.WEBSITE.value),
    ("Corporate Astrology", "https://ca.ai4devops.online/", SiteCategory.WEBSITE.value),
    ("Dotfit", "https://dotfit.aibzr.com/", SiteCategory.WEBSITE.value),
    ("Dotfit Admin", "https://admin-dotfit.aibzr.com/", SiteCategory.PORTAL.value),
    ("Gems and Jewelry", "https://gem-diamonds.aibzr.com/", SiteCategory.WEBSITE.value),
    ("Magna", "https://magna.ai4devops.online/", SiteCategory.WEBSITE.value),
    ("New Life Rehab", "https://newliferehabhospital.com/", SiteCategory.WEBSITE.value),
    ("Otix mens tailoring", "https://otix.ai4devops.online/", SiteCategory.WEBSITE.value),
    ("Kaira Pet Store", "https://kairakennels.com/", SiteCategory.WEBSITE.value),
    ("sadguru sai natural foods", "https://sadgurusai.ai4bzr.in/", SiteCategory.WEBSITE.value),
    ("sadguru sai natural foods Admin", "https://sadgurusai-admin.ai4bzr.in/", SiteCategory.PORTAL.value),
    ("Sar Wall Decors", "https://sarwalldecors.com/", SiteCategory.WEBSITE.value),
    ("Sar Wall Decors Admin", "https://swd.ai4devops.online/", SiteCategory.PORTAL.value),
    ("Secured Investigation Services", "https://sis.aibzr.com/", SiteCategory.WEBSITE.value),
    ("Visa Leap", "https://visaleap.aibzr.com/", SiteCategory.WEBSITE.value),
    ("VML", "https://vml.aibzr.com/", SiteCategory.WEBSITE.value),
    ("VML admin portal", "https://vml-admin.aibzr.com/", SiteCategory.PORTAL.value),
    ("Prathiba home tution", "https://prathibhahometuition.in/", SiteCategory.WEBSITE.value),
    ("IBeauty", "https://ibeauty.aibzr.com/", SiteCategory.WEBSITE.value),
    ("Water Purifier", "https://waterpurifierserviceshyderabad.in/", SiteCategory.WEBSITE.value),
    ("Hyderabad Eye Clinic", "https://hyderabadeyeclinic.com/", SiteCategory.WEBSITE.value),
    ("Cinemates", "https://cinemates.in/", SiteCategory.WEBSITE.value),
    ("Cinemates Admin Portal", "https://adminportal.cinemates.in/", SiteCategory.PORTAL.value),
    ("Cori mint", "https://corimint.com/", SiteCategory.WEBSITE.value),
    ("Cori mint admin", "https://corimint-admin.ai4devops.online/", SiteCategory.PORTAL.value),
    ("patny website", "https://patnysanitary.com/", SiteCategory.WEBSITE.value),
    ("patny admin dashboard", "https://admin.patnysanitary.com/", SiteCategory.PORTAL.value),
    ("Trievent", "https://trievent.in/", SiteCategory.WEBSITE.value),
    ("Bhavani jeweleries", "https://bhavanijewellers.in/", SiteCategory.WEBSITE.value),
    ("pickles", "https://pickle.aibzr.com/", SiteCategory.WEBSITE.value),
    ("pickles admin portal", "https://admin-pickle.aibzr.com/", SiteCategory.PORTAL.value),
    ("Kalki import and exports", "https://kalki.aibzr.com/", SiteCategory.WEBSITE.value),
    ("krishmart", "https://api.krishmart.shop/", SiteCategory.MICROSERVICE.value),
    ("krishmart-admin", "https://admin.krishmart.shop/", SiteCategory.PORTAL.value),
    ("Neha fruit and juice bar", "https://neha.ai4bzr.in/", SiteCategory.WEBSITE.value),
    ("Break Time", "https://breaktime.ai4bzr.in/", SiteCategory.WEBSITE.value),
    ("PY BANGALORE IYENGER BAKERY", "https://pybangalore-iyengerbakery.ai4bzr.in/", SiteCategory.WEBSITE.value),
    ("ivana", "https://ivana.aibzr.com/", SiteCategory.WEBSITE.value),
]

DAY = 86400


def normalize_url(url: str) -> str:
    value = url.strip()
    if not value.startswith(("http://", "https://")):
        value = "https://" + value
    parsed = urlparse(value)
    host = (parsed.netloc or "").lower().rstrip(".")
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    scheme = "https" if parsed.scheme in ("http", "https") else parsed.scheme
    return f"{scheme}://{host}{path}"


def url_key(url: str) -> str:
    """Compare hosts+paths ignoring trailing slash / http vs https."""
    n = normalize_url(url)
    parsed = urlparse(n)
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    path = parsed.path.rstrip("/") or ""
    return f"{host}{path}"


async def main() -> None:
    now = datetime.now(timezone.utc)
    added = 0
    updated = 0
    skipped = 0

    async with SessionLocal() as db:
        existing = list((await db.execute(select(Website))).scalars().all())
        by_key = {url_key(w.url): w for w in existing}
        by_name = {w.name.strip().lower(): w for w in existing}

        for name, url, category in CLIENT_SITES:
            key = url_key(url)
            final_url = normalize_url(url)
            match = by_key.get(key) or by_name.get(name.strip().lower())
            if match:
                changed = False
                if match.owner != SiteOwner.CLIENT.value:
                    match.owner = SiteOwner.CLIENT.value
                    changed = True
                if match.check_interval != DAY:
                    match.check_interval = DAY
                    changed = True
                if match.category != category:
                    match.category = category
                    changed = True
                if match.url != final_url:
                    match.url = final_url
                    changed = True
                if changed:
                    updated += 1
                else:
                    skipped += 1
                continue

            db.add(
                Website(
                    name=name[:120],
                    url=final_url[:500],
                    category=category,
                    owner=SiteOwner.CLIENT.value,
                    enabled=True,
                    check_interval=DAY,
                    timeout=10,
                    expected_status=200,
                    monitor_ssl=True,
                    next_check_at=now,
                )
            )
            added += 1

        await db.commit()
        total_clients = await db.scalar(
            select(func.count()).select_from(Website).where(Website.owner == SiteOwner.CLIENT.value)
        )
        print(f"added={added} updated={updated} unchanged={skipped} client_total={total_clients}")


if __name__ == "__main__":
    asyncio.run(main())

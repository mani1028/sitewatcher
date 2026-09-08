import asyncio
import logging
import socket
import ssl
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import httpx
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import SessionLocal
from app.email_service import (
    build_client_report_email,
    build_digest_email,
    failure_layer,
    format_duration,
    format_ist,
    send_email,
)
from app.whatsapp_service import send_whatsapp_digest
from app.models import (
    Check,
    CheckStatus,
    Incident,
    IncidentStatus,
    NotificationLog,
    SettingsRow,
    SiteOwner,
    SiteStatus,
    Website,
)


logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class ProbeResult:
    ok: bool
    status_code: int | None
    response_time_ms: float | None
    error_type: str | None = None
    error_message: str | None = None


_TRANSIENT_STATUS = {502, 503, 504}


async def _probe_url(
    url: str,
    *,
    timeout_sec: int,
    expected_status: int,
    follow_redirects: bool = True,
    label: str = "URL",
) -> ProbeResult:
    timeout = httpx.Timeout(
        connect=min(3.0, timeout_sec),
        read=max(1.0, timeout_sec - 3),
        write=3.0,
        pool=3.0,
    )
    started = datetime.now(timezone.utc)
    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=follow_redirects,
            max_redirects=5,
            verify=True,
            headers={"User-Agent": "SiteWatch/1.0", "Accept": "application/json, text/html, */*"},
        ) as client:
            response = await client.get(url)
            elapsed_ms = (datetime.now(timezone.utc) - started).total_seconds() * 1000
            ok = response.status_code == expected_status
            return ProbeResult(
                ok=ok,
                status_code=response.status_code,
                response_time_ms=round(elapsed_ms, 2),
                error_type=None if ok else "unexpected_status",
                error_message=None if ok else f"{label}: expected {expected_status}, got {response.status_code}",
            )
    except httpx.TooManyRedirects:
        elapsed_ms = (datetime.now(timezone.utc) - started).total_seconds() * 1000
        return ProbeResult(
            False,
            None,
            round(elapsed_ms, 2),
            "redirect_loop",
            f"{label}: redirect loop (exceeded 5 redirects)",
        )
    except httpx.TimeoutException:
        elapsed_ms = (datetime.now(timezone.utc) - started).total_seconds() * 1000
        return ProbeResult(False, None, round(elapsed_ms, 2), "timeout", f"{label}: connection timeout")
    except httpx.ConnectError as exc:
        return ProbeResult(False, None, None, "connection", f"{label}: {str(exc)[:380]}")
    except Exception as exc:  # noqa: BLE001
        return ProbeResult(False, None, None, "error", f"{label}: {str(exc)[:380]}")


async def _probe_url_resilient(
    url: str,
    *,
    timeout_sec: int,
    expected_status: int,
    follow_redirects: bool = True,
    label: str = "URL",
    retries: int = 1,
) -> ProbeResult:
    """Retry once on transient gateway errors / timeouts (common for health APIs)."""
    result = await _probe_url(
        url,
        timeout_sec=timeout_sec,
        expected_status=expected_status,
        follow_redirects=follow_redirects,
        label=label,
    )
    if result.ok or retries <= 0:
        return result
    transient = result.error_type == "timeout" or (
        result.status_code is not None and result.status_code in _TRANSIENT_STATUS
    )
    if not transient:
        return result
    await asyncio.sleep(2.0)
    return await _probe_url(
        url,
        timeout_sec=timeout_sec,
        expected_status=expected_status,
        follow_redirects=follow_redirects,
        label=label,
    )


async def probe_website(website: Website) -> ProbeResult:
    """Probe primary URL and optional health/API URL. Both must succeed."""
    primary = await _probe_url(
        website.url,
        timeout_sec=website.timeout,
        expected_status=website.expected_status,
        follow_redirects=True,
        label="Frontend",
    )
    health = (website.health_url or "").strip()
    if not health:
        # Keep legacy wording when there is no secondary check
        if primary.error_message and primary.error_message.startswith("Frontend: "):
            primary.error_message = primary.error_message.removeprefix("Frontend: ")
        return primary

    secondary = await _probe_url_resilient(
        health,
        timeout_sec=website.timeout,
        expected_status=website.expected_status,
        # Don't treat a login-page redirect as a healthy API
        follow_redirects=False,
        label="Backend/API",
        retries=1,
    )

    times = [t for t in (primary.response_time_ms, secondary.response_time_ms) if t is not None]
    combined_ms = round(max(times), 2) if times else None

    if primary.ok and secondary.ok:
        return ProbeResult(
            ok=True,
            status_code=secondary.status_code or primary.status_code,
            response_time_ms=combined_ms,
        )

    parts: list[str] = []
    if not primary.ok:
        parts.append(primary.error_message or "Frontend down")
    if not secondary.ok:
        parts.append(secondary.error_message or "Backend/API down")
    failed = secondary if not secondary.ok else primary
    return ProbeResult(
        ok=False,
        status_code=failed.status_code,
        response_time_ms=combined_ms,
        error_type=failed.error_type or "error",
        error_message="; ".join(parts)[:500],
    )

def check_ssl_expiry(url: str) -> datetime | None:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return None
    host = parsed.hostname
    if not host:
        return None
    port = parsed.port or 443
    try:
        context = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
                not_after = cert.get("notAfter")
                if not not_after:
                    return None
                return datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
    except Exception:  # noqa: BLE001
        logger.exception("SSL check failed for %s", url)
        return None


async def rolling_avg_response(db: AsyncSession, website_id: int, limit: int = 5) -> float | None:
    """Average recent successful response times only (ignore timeouts/errors)."""
    result = await db.execute(
        select(Check.response_time)
        .where(
            Check.website_id == website_id,
            Check.response_time.is_not(None),
            Check.status.in_([CheckStatus.UP, CheckStatus.SLOW]),
        )
        .order_by(Check.checked_at.desc())
        .limit(limit)
    )
    values = [v for v in result.scalars().all() if v is not None]
    if not values:
        return None
    return sum(values) / len(values)


async def recompute_uptime(db: AsyncSession, website_id: int) -> float:
    since = datetime.now(timezone.utc) - timedelta(days=7)
    total = await db.scalar(
        select(func.count()).select_from(Check).where(Check.website_id == website_id, Check.checked_at >= since)
    )
    if not total:
        return 100.0
    up = await db.scalar(
        select(func.count())
        .select_from(Check)
        .where(
            Check.website_id == website_id,
            Check.checked_at >= since,
            Check.status.in_([CheckStatus.UP, CheckStatus.SLOW]),
        )
    )
    return round(((up or 0) / total) * 100, 2)


async def process_website(db: AsyncSession, website: Website, settings_row: SettingsRow) -> None:
    now = datetime.now(timezone.utc)

    if website.maintenance_mode:
        website.status = SiteStatus.MAINTENANCE
        website.last_checked_at = now
        website.next_check_at = now + timedelta(seconds=website.check_interval)
        await db.commit()
        return

    result = await probe_website(website)
    website.last_checked_at = now
    website.last_response_time = result.response_time_ms
    website.last_status_code = result.status_code
    website.last_error = result.error_message

    check_status = CheckStatus.UP
    if not result.ok:
        check_status = CheckStatus.DOWN
    elif result.response_time_ms and result.response_time_ms >= settings_row.slow_threshold_ms:
        check_status = CheckStatus.SLOW
    else:
        avg = await rolling_avg_response(db, website.id)
        if avg and avg >= settings_row.slow_threshold_ms:
            check_status = CheckStatus.SLOW

    db.add(
        Check(
            website_id=website.id,
            status=check_status,
            status_code=result.status_code,
            response_time=result.response_time_ms,
            error_type=result.error_type,
            error_message=result.error_message,
            checked_at=now,
        )
    )

    if result.ok:
        website.consecutive_failures = 0
        website.consecutive_successes += 1

        if website.status in (SiteStatus.DOWN, SiteStatus.UNKNOWN) and website.consecutive_successes >= settings_row.recovery_threshold:
            open_incident = await db.scalar(
                select(Incident).where(
                    Incident.website_id == website.id,
                    Incident.status == IncidentStatus.OPEN,
                )
            )
            if open_incident:
                open_incident.status = IncidentStatus.RESOLVED
                open_incident.resolved_at = now
                open_incident.duration_seconds = int((now - open_incident.started_at).total_seconds())
                # Drop sub-2-minute blips from the digest entirely (down + recovery)
                if not open_incident.notification_sent and (open_incident.duration_seconds or 0) < 120:
                    open_incident.notification_sent = True
                    open_incident.recovery_notification_sent = True
                # Email is batched after the check cycle (see flush_alert_digest)

            website.status = SiteStatus.SLOW if check_status == CheckStatus.SLOW else SiteStatus.UP
        elif website.status != SiteStatus.DOWN:
            website.status = SiteStatus.SLOW if check_status == CheckStatus.SLOW else SiteStatus.UP
    else:
        website.consecutive_successes = 0
        website.consecutive_failures += 1

        if website.consecutive_failures >= settings_row.failure_threshold:
            if website.status != SiteStatus.DOWN:
                website.status = SiteStatus.DOWN
                open_incident = await db.scalar(
                    select(Incident).where(
                        Incident.website_id == website.id,
                        Incident.status == IncidentStatus.OPEN,
                    )
                )
                if not open_incident:
                    reason = result.error_message or result.error_type or "Website unreachable"
                    # Anti-flap: if this site just recovered, track the incident silently
                    suppress_notify = False
                    cooldown = max(0, settings.alert_flap_cooldown_seconds)
                    if cooldown:
                        last_resolved = await db.scalar(
                            select(Incident)
                            .where(
                                Incident.website_id == website.id,
                                Incident.status == IncidentStatus.RESOLVED,
                                Incident.resolved_at.is_not(None),
                            )
                            .order_by(Incident.resolved_at.desc())
                            .limit(1)
                        )
                        if last_resolved and last_resolved.resolved_at:
                            resolved_at = last_resolved.resolved_at
                            if resolved_at.tzinfo is None:
                                resolved_at = resolved_at.replace(tzinfo=timezone.utc)
                            if (now - resolved_at).total_seconds() < cooldown:
                                suppress_notify = True
                                logger.info(
                                    "Anti-flap: suppressing down email for %s (recovered %.0fs ago)",
                                    website.name,
                                    (now - resolved_at).total_seconds(),
                                )
                    incident = Incident(
                        website_id=website.id,
                        started_at=now,
                        reason=reason,
                        status=IncidentStatus.OPEN,
                        notification_sent=suppress_notify,
                        # If down mail is suppressed, skip recovery mail too
                        recovery_notification_sent=suppress_notify,
                    )
                    db.add(incident)
                    # Email is batched after the check cycle (see flush_alert_digest)

    # High priority: poll every ~30s while DOWN or still accumulating failures (FAILING)
    interval = website.check_interval
    if bool(getattr(website, "high_priority", False)):
        failing = website.status == SiteStatus.DOWN or website.consecutive_failures > 0
        if failing:
            interval = max(15, int(settings.high_priority_check_interval or 30))
    website.next_check_at = now + timedelta(seconds=interval)

    website.uptime_percent = await recompute_uptime(db, website.id)
    await db.commit()


async def flush_alert_digest(db: AsyncSession, settings_row: SettingsRow) -> None:
    """Send one group email for all newly down / recovered projects (never one mail per site)."""
    pending_downs = list(
        (
            await db.execute(
                select(Incident)
                .where(Incident.status == IncidentStatus.OPEN, Incident.notification_sent.is_(False))
                .order_by(Incident.started_at.desc())
            )
        ).scalars().all()
    )
    pending_recoveries = list(
        (
            await db.execute(
                select(Incident)
                .where(
                    Incident.status == IncidentStatus.RESOLVED,
                    Incident.recovery_notification_sent.is_(False),
                )
                .order_by(Incident.resolved_at.desc())
            )
        ).scalars().all()
    )
    if not pending_downs and not pending_recoveries:
        return

    # Debounce on the *oldest* pending event so flapping sites can't reset the timer forever
    now = datetime.now(timezone.utc)
    event_times: list[datetime] = []
    for incident in pending_downs:
        if incident.started_at:
            event_times.append(incident.started_at)
    for incident in pending_recoveries:
        if incident.resolved_at:
            event_times.append(incident.resolved_at)
    if event_times:
        oldest = min(event_times)
        newest = max(event_times)
        if oldest.tzinfo is None:
            oldest = oldest.replace(tzinfo=timezone.utc)
        if newest.tzinfo is None:
            newest = newest.replace(tzinfo=timezone.utc)
        age = (now - oldest).total_seconds()
        debounce = max(0, settings.digest_debounce_seconds)
        if age < debounce:
            logger.info(
                "Digest debounce: %s pending event(s), oldest %.0fs ago / newest %.0fs ago (wait %ss)",
                len(pending_downs) + len(pending_recoveries),
                age,
                (now - newest).total_seconds(),
                debounce,
            )
            return

    website_ids = {i.website_id for i in pending_downs} | {i.website_id for i in pending_recoveries}
    open_all = list(
        (
            await db.execute(
                select(Incident).where(Incident.status == IncidentStatus.OPEN).order_by(Incident.started_at.desc())
            )
        ).scalars().all()
    )
    website_ids |= {i.website_id for i in open_all}
    sites: dict[int, Website] = {}
    if website_ids:
        sites = {
            w.id: w
            for w in (await db.execute(select(Website).where(Website.id.in_(website_ids)))).scalars().all()
        }

    downs = []
    for incident in pending_downs:
        site = sites.get(incident.website_id)
        if not site:
            continue
        downs.append(
            {
                "name": site.name,
                "url": site.url,
                "reason": incident.reason,
                "layer": failure_layer(incident.reason),
                "owner": (site.owner.value if hasattr(site.owner, "value") else site.owner) or "inhouse",
                "whatsapp_alerts": bool(getattr(site, "whatsapp_alerts", False)),
                "detected_at": format_ist(incident.started_at),
            }
        )

    recoveries = []
    for incident in pending_recoveries:
        site = sites.get(incident.website_id)
        if not site:
            continue
        recoveries.append(
            {
                "name": site.name,
                "url": site.url,
                "owner": (site.owner.value if hasattr(site.owner, "value") else site.owner) or "inhouse",
                "whatsapp_alerts": bool(getattr(site, "whatsapp_alerts", False)),
                "downtime": format_duration(incident.duration_seconds),
                "recovered_at": format_ist(incident.resolved_at),
            }
        )

    still_down = []
    for incident in open_all:
        site = sites.get(incident.website_id)
        if not site:
            continue
        still_down.append(
            {
                "name": site.name,
                "url": site.url,
                "reason": incident.reason,
                "layer": failure_layer(incident.reason),
                "owner": (site.owner.value if hasattr(site.owner, "value") else site.owner) or "inhouse",
            }
        )

    subject, body, html_body = build_digest_email(
        downs=downs,
        recoveries=recoveries,
        still_down=still_down,
    )
    email_ok = await send_email(
        db,
        settings_row,
        subject=subject,
        body=body,
        html_body=html_body,
        kind="digest",
    )
    wa_ok = await send_whatsapp_digest(
        db,
        settings_row,
        downs=downs,
        recoveries=recoveries,
        subject=subject,
    )
    # Mark notified if at least one channel delivered. If both are off/misconfigured,
    # email_ok is False and wa_ok is False — keep pending for retry when SMTP works.
    if not email_ok and not wa_ok:
        return

    for incident in pending_downs:
        incident.notification_sent = True
    for incident in pending_recoveries:
        incident.recovery_notification_sent = True
    await db.commit()
    logger.info(
        "Sent group digest: %s down, %s recovered (email=%s whatsapp=%s subject=%s)",
        len(downs),
        len(recoveries),
        email_ok,
        wa_ok,
        subject,
    )


async def run_due_checks() -> None:
    async with SessionLocal() as db:
        settings_row = await db.scalar(select(SettingsRow).where(SettingsRow.id == 1))
        if not settings_row:
            return

        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(Website)
            .where(
                Website.enabled.is_(True),
                (Website.next_check_at.is_(None)) | (Website.next_check_at <= now),
            )
            .order_by(Website.next_check_at.nullsfirst())
            .limit(100)
        )
        websites = list(result.scalars().all())

        if websites:
            semaphore = asyncio.Semaphore(settings.max_concurrent_checks)

            async def _run(site_id: int) -> None:
                async with semaphore:
                    async with SessionLocal() as session:
                        site = await session.get(Website, site_id)
                        row = await session.scalar(select(SettingsRow).where(SettingsRow.id == 1))
                        if not site or not row or not site.enabled:
                            return
                        try:
                            await process_website(session, site, row)
                        except Exception:
                            logger.exception("Check failed for website %s", site_id)

            await asyncio.gather(*[_run(w.id) for w in websites])

        # Always attempt group digest (debounce may hold briefly to batch more sites)
        async with SessionLocal() as session:
            row = await session.scalar(select(SettingsRow).where(SettingsRow.id == 1))
            if row:
                try:
                    await flush_alert_digest(session, row)
                except Exception:
                    logger.exception("Failed to send alert digest")

async def run_ssl_checks() -> None:
    async with SessionLocal() as db:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=12)
        result = await db.execute(
            select(Website).where(
                Website.enabled.is_(True),
                Website.monitor_ssl.is_(True),
                (Website.ssl_checked_at.is_(None)) | (Website.ssl_checked_at <= cutoff),
            )
        )
        websites = list(result.scalars().all())
        for website in websites:
            expires = await asyncio.to_thread(check_ssl_expiry, website.url)
            website.ssl_expires_at = expires
            website.ssl_checked_at = now
        await db.commit()


async def cleanup_old_checks() -> None:
    """Drop old per-request check rows and trim notification logs to keep the DB light."""
    async with SessionLocal() as db:
        cutoff = datetime.now(timezone.utc) - timedelta(days=settings.check_retention_days)
        by_age = await db.execute(delete(Check).where(Check.checked_at < cutoff))

        # Keep only the newest N checks per website (charts still work; history stays small)
        per_site = max(5, settings.check_retention_per_site)
        by_cap = await db.execute(
            text(
                """
                DELETE FROM checks
                WHERE id IN (
                  SELECT id FROM (
                    SELECT id,
                           ROW_NUMBER() OVER (
                             PARTITION BY website_id ORDER BY checked_at DESC
                           ) AS rn
                    FROM checks
                  ) ranked
                  WHERE rn > :keep
                )
                """
            ),
            {"keep": per_site},
        )

        failed_cutoff = datetime.now(timezone.utc) - timedelta(days=settings.failed_email_retention_days)
        failed = await db.execute(
            delete(NotificationLog).where(
                NotificationLog.success.is_(False),
                NotificationLog.created_at < failed_cutoff,
            )
        )

        keep_notes = max(10, settings.notification_retention)
        notes = await db.execute(
            text(
                """
                DELETE FROM notifications
                WHERE id NOT IN (
                  SELECT id FROM (
                    SELECT id FROM notifications ORDER BY created_at DESC LIMIT :keep
                  ) newest
                )
                """
            ),
            {"keep": keep_notes},
        )

        await db.commit()
        logger.info(
            "Log cleanup: checks age=%s cap=%s; notifications failed=%s trim=%s (keep %s/site, %s days)",
            by_age.rowcount or 0,
            by_cap.rowcount or 0,
            failed.rowcount or 0,
            notes.rowcount or 0,
            per_site,
            settings.check_retention_days,
        )


async def send_client_status_report(slot: str = "morning") -> None:
    """Recheck all enabled client sites, then email a morning/evening summary."""
    slot_label = "Morning" if slot == "morning" else "Evening"
    async with SessionLocal() as db:
        settings_row = await db.scalar(select(SettingsRow).where(SettingsRow.id == 1))
        if not settings_row:
            return

        result = await db.execute(
            select(Website)
            .where(Website.enabled.is_(True), Website.owner == SiteOwner.CLIENT.value)
            .order_by(Website.name)
        )
        clients = list(result.scalars().all())
        if not clients:
            logger.info("Client %s report skipped — no client sites", slot_label)
            return

        ids = [w.id for w in clients]

    semaphore = asyncio.Semaphore(settings.max_concurrent_checks)

    async def _check(site_id: int) -> None:
        async with semaphore:
            async with SessionLocal() as session:
                site = await session.get(Website, site_id)
                row = await session.scalar(select(SettingsRow).where(SettingsRow.id == 1))
                if not site or not row or not site.enabled:
                    return
                try:
                    await process_website(session, site, row)
                except Exception:
                    logger.exception("Client report check failed for %s", site_id)

    await asyncio.gather(*[_check(i) for i in ids])

    async with SessionLocal() as db:
        settings_row = await db.scalar(select(SettingsRow).where(SettingsRow.id == 1))
        if not settings_row:
            return
        sites = list(
            (
                await db.execute(
                    select(Website)
                    .where(Website.id.in_(ids))
                    .order_by(Website.name)
                )
            ).scalars().all()
        )
        down: list[dict[str, str]] = []
        up: list[dict[str, str]] = []
        unknown: list[dict[str, str]] = []
        for site in sites:
            item = {"name": site.name, "url": site.url, "reason": site.last_error or ""}
            status = site.status.value if hasattr(site.status, "value") else str(site.status)
            if status == SiteStatus.DOWN.value:
                down.append(item)
            elif status in (SiteStatus.UP.value, SiteStatus.SLOW.value):
                up.append(item)
            else:
                unknown.append(item)

        subject, body, html_body = build_client_report_email(
            slot_label=slot_label,
            checked_at=format_ist(),
            down=down,
            up=up,
            unknown=unknown,
        )
        ok = await send_email(
            db,
            settings_row,
            subject=subject,
            body=body,
            html_body=html_body,
            kind="client_report",
        )
        logger.info(
            "Client %s report sent=%s (up=%s down=%s unknown=%s)",
            slot_label,
            ok,
            len(up),
            len(down),
            len(unknown),
        )

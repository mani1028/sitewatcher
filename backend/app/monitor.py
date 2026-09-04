import asyncio
import logging
import socket
import ssl
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import httpx
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import SessionLocal
from app.email_service import build_down_email, build_recovery_email, format_duration, format_ist, send_email
from app.models import (
    Check,
    CheckStatus,
    Incident,
    IncidentStatus,
    NotificationLog,
    SettingsRow,
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


async def probe_website(website: Website) -> ProbeResult:
    timeout = httpx.Timeout(
        connect=min(3.0, website.timeout),
        read=max(1.0, website.timeout - 3),
        write=3.0,
        pool=3.0,
    )
    started = datetime.now(timezone.utc)
    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            verify=True,
            headers={"User-Agent": "SiteWatch/1.0"},
        ) as client:
            response = await client.get(website.url)
            elapsed_ms = (datetime.now(timezone.utc) - started).total_seconds() * 1000
            ok = response.status_code == website.expected_status
            return ProbeResult(
                ok=ok,
                status_code=response.status_code,
                response_time_ms=round(elapsed_ms, 2),
                error_type=None if ok else "unexpected_status",
                error_message=None if ok else f"Expected {website.expected_status}, got {response.status_code}",
            )
    except httpx.TimeoutException:
        elapsed_ms = (datetime.now(timezone.utc) - started).total_seconds() * 1000
        return ProbeResult(False, None, round(elapsed_ms, 2), "timeout", "Connection timeout")
    except httpx.ConnectError as exc:
        return ProbeResult(False, None, None, "connection", str(exc)[:400])
    except Exception as exc:  # noqa: BLE001
        return ProbeResult(False, None, None, "error", str(exc)[:400])


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
    result = await db.execute(
        select(Check.response_time)
        .where(Check.website_id == website_id, Check.response_time.is_not(None))
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
    website.next_check_at = now + timedelta(seconds=website.check_interval)

    if website.maintenance_mode:
        website.status = SiteStatus.MAINTENANCE
        website.last_checked_at = now
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
                if not open_incident.recovery_notification_sent:
                    subject, body, html_body = build_recovery_email(
                        name=website.name,
                        url=website.url,
                        downtime=format_duration(open_incident.duration_seconds),
                        recovered_at=format_ist(now),
                        website_id=website.id,
                    )
                    await send_email(
                        db,
                        settings_row,
                        subject=subject,
                        body=body,
                        html_body=html_body,
                        website_id=website.id,
                        incident_id=open_incident.id,
                        kind="recovery",
                    )
                    open_incident.recovery_notification_sent = True

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
                    incident = Incident(
                        website_id=website.id,
                        started_at=now,
                        reason=reason,
                        status=IncidentStatus.OPEN,
                    )
                    db.add(incident)
                    await db.flush()
                    subject, body, html_body = build_down_email(
                        name=website.name,
                        url=website.url,
                        reason=reason,
                        detected_at=format_ist(now),
                        website_id=website.id,
                    )
                    await send_email(
                        db,
                        settings_row,
                        subject=subject,
                        body=body,
                        html_body=html_body,
                        website_id=website.id,
                        incident_id=incident.id,
                        kind="down",
                    )
                    incident.notification_sent = True

    website.uptime_percent = await recompute_uptime(db, website.id)
    await db.commit()


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
        if not websites:
            return

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
    async with SessionLocal() as db:
        cutoff = datetime.now(timezone.utc) - timedelta(days=settings.check_retention_days)
        await db.execute(delete(Check).where(Check.checked_at < cutoff))

        failed_cutoff = datetime.now(timezone.utc) - timedelta(days=settings.failed_email_retention_days)
        result = await db.execute(
            delete(NotificationLog).where(
                NotificationLog.success.is_(False),
                NotificationLog.created_at < failed_cutoff,
            )
        )
        await db.commit()
        logger.info(
            "Cleaned checks older than %s days; removed %s failed emails older than %s days",
            settings.check_retention_days,
            result.rowcount or 0,
            settings.failed_email_retention_days,
        )

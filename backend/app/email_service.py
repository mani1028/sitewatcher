import asyncio
import html
import logging
import re
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import parseaddr
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import NotificationLog, SettingsRow


logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_IST = ZoneInfo("Asia/Kolkata")


def format_ist(dt: datetime | None = None) -> str:
    """Format a timestamp in Indian Standard Time for alert emails."""
    value = dt or datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(_IST).strftime("%Y-%m-%d %H:%M IST")



def normalize_alert_emails(value: str) -> list[str]:
    """Parse comma/semicolon/whitespace-separated emails into a unique list."""
    parts = re.split(r"[,;\s]+", value.strip())
    emails: list[str] = []
    seen: set[str] = set()
    for part in parts:
        candidate = part.strip().strip("<>")
        if not candidate:
            continue
        _, addr = parseaddr(candidate if "<" in part else f"<{candidate}>")
        email = (addr or candidate).strip()
        key = email.lower()
        if not _EMAIL_RE.match(email) or key in seen:
            continue
        seen.add(key)
        emails.append(email)
    return emails


def format_duration(seconds: int | None) -> str:
    if seconds is None:
        return "unknown"
    minutes, secs = divmod(max(seconds, 0), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {secs}s"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def _dashboard_url(website_id: int | None = None) -> str:
    base = get_settings().frontend_url.rstrip("/")
    if website_id:
        return f"{base}/websites/{website_id}"
    return base


def _wrap_html(*, title: str, status: str, status_color: str, name: str, url: str, rows: list[tuple[str, str]], footer_link: str) -> str:
    safe_name = html.escape(name)
    safe_url = html.escape(url)
    safe_title = html.escape(title)
    details = "".join(
        f"""
        <tr>
          <td style="padding:6px 0;color:#6b7280;font-size:13px;width:90px;vertical-align:top;">{html.escape(label)}</td>
          <td style="padding:6px 0;color:#111827;font-size:14px;">{html.escape(value)}</td>
        </tr>
        """
        for label, value in rows
        if value
    )
    return f"""<!DOCTYPE html>
<html>
<body style="margin:0;padding:24px;background:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:520px;margin:0 auto;background:#ffffff;border-radius:10px;overflow:hidden;border:1px solid #e5e7eb;">
    <tr>
      <td style="padding:20px 24px 8px;font-size:13px;letter-spacing:0.04em;text-transform:uppercase;color:#6b7280;">SiteWatch</td>
    </tr>
    <tr>
      <td style="padding:0 24px 8px;">
        <span style="display:inline-block;padding:4px 10px;border-radius:999px;background:{status_color};color:#ffffff;font-size:12px;font-weight:600;">{html.escape(status)}</span>
      </td>
    </tr>
    <tr>
      <td style="padding:4px 24px 8px;font-size:22px;font-weight:650;color:#111827;line-height:1.3;">{safe_name}</td>
    </tr>
    <tr>
      <td style="padding:0 24px 20px;">
        <a href="{safe_url}" style="color:#2563eb;font-size:15px;word-break:break-all;text-decoration:none;">{safe_url}</a>
      </td>
    </tr>
    <tr>
      <td style="padding:0 24px 8px;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0">{details}</table>
      </td>
    </tr>
    <tr>
      <td style="padding:16px 24px 24px;border-top:1px solid #f3f4f6;">
        <a href="{html.escape(footer_link)}" style="display:inline-block;padding:10px 14px;background:#111827;color:#ffffff;text-decoration:none;border-radius:8px;font-size:13px;font-weight:600;">Open in SiteWatch</a>
      </td>
    </tr>
  </table>
  <p style="max-width:520px;margin:12px auto 0;text-align:center;color:#9ca3af;font-size:12px;">{safe_title}</p>
</body>
</html>"""


def _short_cell(value: str, limit: int = 80) -> str:
    text = (value or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _data_table(
    headers: list[str],
    rows: list[list[str]],
    *,
    accent: str | None = None,
) -> str:
    """Compact HTML data table for digest / report emails."""
    if not rows:
        return ""
    head = "".join(
        f'<th style="padding:8px 10px;text-align:left;font-size:11px;font-weight:600;'
        f'letter-spacing:0.04em;text-transform:uppercase;color:#6b7280;'
        f'border-bottom:1px solid #e5e7eb;background:#f9fafb;">{html.escape(h)}</th>'
        for h in headers
    )
    body_rows = []
    for i, cells in enumerate(rows):
        bg = "#ffffff" if i % 2 == 0 else "#fafafa"
        tds = []
        for j, cell in enumerate(cells):
            # First column often holds status badge HTML already escaped by caller via safe flag
            if j == 0 and cell.startswith("<"):
                tds.append(
                    f'<td style="padding:9px 10px;vertical-align:top;border-bottom:1px solid #f3f4f6;">{cell}</td>'
                )
            else:
                tds.append(
                    f'<td style="padding:9px 10px;vertical-align:top;border-bottom:1px solid #f3f4f6;'
                    f'font-size:13px;color:#111827;line-height:1.35;">{cell}</td>'
                )
        body_rows.append(f'<tr style="background:{bg};">{"".join(tds)}</tr>')
    bar = (
        f'<div style="height:3px;background:{accent};border-radius:2px 2px 0 0;"></div>'
        if accent
        else ""
    )
    return f"""
    {bar}
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
           style="width:100%;border-collapse:collapse;border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;">
      <thead><tr>{head}</tr></thead>
      <tbody>{"".join(body_rows)}</tbody>
    </table>
    """


def _status_pill(label: str, color: str) -> str:
    return (
        f'<span style="display:inline-block;padding:3px 8px;border-radius:999px;'
        f'background:{color};color:#ffffff;font-size:11px;font-weight:600;'
        f'white-space:nowrap;">{html.escape(label)}</span>'
    )


def _site_cell(name: str, url: str) -> str:
    return (
        f'<div style="font-weight:600;color:#111827;font-size:13px;">{html.escape(name)}</div>'
        f'<a href="{html.escape(url)}" style="color:#2563eb;font-size:11px;word-break:break-all;'
        f'text-decoration:none;">{html.escape(url.replace("https://", "").replace("http://", ""))}</a>'
    )


def build_digest_email(
    *,
    downs: list[dict[str, str]],
    recoveries: list[dict[str, str]],
    still_down: list[dict[str, str]] | None = None,
) -> tuple[str, str, str]:
    """One email covering all newly down / recovered projects in a check cycle."""
    still_down = still_down or []
    parts: list[str] = []
    if downs:
        parts.append(f"{len(downs)} down")
    if recoveries:
        parts.append(f"{len(recoveries)} recovered")
    subject = "SiteWatch: " + (", ".join(parts) if parts else "status update")

    text_lines = ["SiteWatch status update", ""]
    if downs:
        text_lines.append(f"DOWN ({len(downs)})")
        for item in downs:
            text_lines.append(f"- {item['name']} — {item['url']}")
            text_lines.append(f"  Reason: {item.get('reason') or 'unreachable'}")
            if item.get("detected_at"):
                text_lines.append(f"  Detected: {item['detected_at']}")
        text_lines.append("")
    if recoveries:
        text_lines.append(f"RECOVERED ({len(recoveries)})")
        for item in recoveries:
            text_lines.append(f"- {item['name']} — {item['url']}")
            if item.get("downtime"):
                text_lines.append(f"  Downtime: {item['downtime']}")
            if item.get("recovered_at"):
                text_lines.append(f"  Recovered: {item['recovered_at']}")
        text_lines.append("")
    other_still = [s for s in still_down if s.get("name") not in {d["name"] for d in downs}]
    if other_still:
        text_lines.append(f"STILL DOWN ({len(other_still)})")
        for item in other_still:
            text_lines.append(f"- {item['name']} — {item['url']}")
            if item.get("reason"):
                text_lines.append(f"  Reason: {item['reason']}")
        text_lines.append("")
    text_lines.append(f"Dashboard: {_dashboard_url()}")
    text = "\n".join(text_lines)

    sections: list[str] = []

    if downs:
        rows = [
            [
                _status_pill("Down", "#dc2626"),
                _site_cell(item["name"], item["url"]),
                html.escape(_short_cell(item.get("reason") or "unreachable", 90)),
                html.escape(item.get("detected_at") or "—"),
            ]
            for item in downs
        ]
        sections.append(
            f"""
            <tr><td style="padding:8px 24px 4px;font-size:12px;font-weight:600;color:#dc2626;">Down · {len(downs)}</td></tr>
            <tr><td style="padding:0 24px 16px;">{_data_table(["Status", "Site", "Reason", "Detected"], rows, accent="#dc2626")}</td></tr>
            """
        )

    if recoveries:
        rows = [
            [
                _status_pill("Up", "#16a34a"),
                _site_cell(item["name"], item["url"]),
                html.escape(item.get("downtime") or "—"),
                html.escape(item.get("recovered_at") or "—"),
            ]
            for item in recoveries
        ]
        sections.append(
            f"""
            <tr><td style="padding:8px 24px 4px;font-size:12px;font-weight:600;color:#16a34a;">Recovered · {len(recoveries)}</td></tr>
            <tr><td style="padding:0 24px 16px;">{_data_table(["Status", "Site", "Downtime", "Recovered"], rows, accent="#16a34a")}</td></tr>
            """
        )

    if other_still:
        rows = [
            [
                _status_pill("Still down", "#b45309"),
                _site_cell(item["name"], item["url"]),
                html.escape(_short_cell(item.get("reason") or "—", 90)),
            ]
            for item in other_still
        ]
        sections.append(
            f"""
            <tr><td style="padding:8px 24px 4px;font-size:12px;font-weight:600;color:#b45309;">Still down · {len(other_still)}</td></tr>
            <tr><td style="padding:0 24px 16px;">{_data_table(["Status", "Site", "Reason"], rows, accent="#b45309")}</td></tr>
            """
        )

    html_body = f"""<!DOCTYPE html>
<html>
<body style="margin:0;padding:24px;background:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:640px;margin:0 auto;background:#ffffff;border-radius:10px;overflow:hidden;border:1px solid #e5e7eb;">
    <tr>
      <td style="padding:18px 24px 4px;font-size:12px;letter-spacing:0.06em;text-transform:uppercase;color:#6b7280;">SiteWatch</td>
    </tr>
    <tr>
      <td style="padding:2px 24px 6px;font-size:20px;font-weight:650;color:#111827;">Status update</td>
    </tr>
    <tr>
      <td style="padding:0 24px 14px;font-size:13px;color:#6b7280;">{html.escape(format_ist())}</td>
    </tr>
    {"".join(sections)}
    <tr>
      <td style="padding:12px 24px 22px;border-top:1px solid #f3f4f6;">
        <a href="{html.escape(_dashboard_url())}" style="display:inline-block;padding:10px 14px;background:#111827;color:#ffffff;text-decoration:none;border-radius:8px;font-size:13px;font-weight:600;">Open SiteWatch</a>
      </td>
    </tr>
  </table>
</body>
</html>"""
    return subject, text, html_body


def build_down_email(*, name: str, url: str, reason: str, detected_at: str, website_id: int | None = None) -> tuple[str, str, str]:
    return build_digest_email(
        downs=[{"name": name, "url": url, "reason": reason, "detected_at": detected_at}],
        recoveries=[],
    )


def build_recovery_email(
    *,
    name: str,
    url: str,
    downtime: str,
    recovered_at: str,
    website_id: int | None = None,
) -> tuple[str, str, str]:
    return build_digest_email(
        downs=[],
        recoveries=[{"name": name, "url": url, "downtime": downtime, "recovered_at": recovered_at}],
    )


def build_test_email() -> tuple[str, str, str]:
    dash = _dashboard_url()
    subject = "SiteWatch test"
    text = (
        "SiteWatch email is working.\n\n"
        f"Dashboard: {dash}\n"
    )
    html_body = f"""<!DOCTYPE html>
<html>
<body style="margin:0;padding:24px;background:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:520px;margin:0 auto;background:#ffffff;border-radius:10px;overflow:hidden;border:1px solid #e5e7eb;">
    <tr><td style="padding:20px 24px 8px;font-size:13px;letter-spacing:0.04em;text-transform:uppercase;color:#6b7280;">SiteWatch</td></tr>
    <tr><td style="padding:4px 24px 8px;font-size:22px;font-weight:650;color:#111827;">Email is working</td></tr>
    <tr><td style="padding:0 24px 20px;color:#4b5563;font-size:14px;line-height:1.5;">Your SMTP settings are configured correctly. Downtime alerts will look like this and include the site URL.</td></tr>
    <tr><td style="padding:0 24px 24px;"><a href="{html.escape(dash)}" style="display:inline-block;padding:10px 14px;background:#111827;color:#ffffff;text-decoration:none;border-radius:8px;font-size:13px;font-weight:600;">Open SiteWatch</a></td></tr>
  </table>
</body>
</html>"""
    return subject, text, html_body


def build_client_report_email(
    *,
    slot_label: str,
    checked_at: str,
    down: list[dict[str, str]],
    up: list[dict[str, str]],
    unknown: list[dict[str, str]] | None = None,
) -> tuple[str, str, str]:
    """Morning / evening client-site status report — neat status table."""
    unknown = unknown or []
    total = len(down) + len(up) + len(unknown)
    subject = f"Client sites · {slot_label} — {len(down)} down / {len(up)} up"

    text_lines = [
        f"SiteWatch client report ({slot_label})",
        f"Checked: {checked_at}",
        f"Total: {total} · Up: {len(up)} · Down: {len(down)} · Unknown: {len(unknown)}",
        "",
    ]
    if down:
        text_lines.append(f"DOWN ({len(down)})")
        for item in down:
            text_lines.append(f"- {item['name']} — {item['url']}")
            if item.get("reason"):
                text_lines.append(f"  {item['reason']}")
        text_lines.append("")
    if unknown:
        text_lines.append(f"UNKNOWN ({len(unknown)})")
        for item in unknown:
            text_lines.append(f"- {item['name']} — {item['url']}")
        text_lines.append("")
    text_lines.append(f"UP ({len(up)})")
    for item in up:
        text_lines.append(f"- {item['name']}")
    text_lines.append("")
    text_lines.append(f"Dashboard: {_dashboard_url()}")
    text = "\n".join(text_lines)

    table_rows: list[list[str]] = []
    for item in down:
        table_rows.append(
            [
                _status_pill("Down", "#dc2626"),
                _site_cell(item["name"], item["url"]),
                html.escape(_short_cell(item.get("reason") or "—", 100)),
            ]
        )
    for item in unknown:
        table_rows.append(
            [
                _status_pill("Unknown", "#6b7280"),
                _site_cell(item["name"], item["url"]),
                "—",
            ]
        )
    for item in up:
        table_rows.append(
            [
                _status_pill("Up", "#16a34a"),
                _site_cell(item["name"], item["url"]),
                "—",
            ]
        )

    table_html = _data_table(["Status", "Site", "Note"], table_rows)

    html_body = f"""<!DOCTYPE html>
<html>
<body style="margin:0;padding:24px;background:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:640px;margin:0 auto;background:#ffffff;border-radius:10px;overflow:hidden;border:1px solid #e5e7eb;">
    <tr><td style="padding:18px 24px 4px;font-size:12px;letter-spacing:0.06em;text-transform:uppercase;color:#6b7280;">SiteWatch · Clients</td></tr>
    <tr><td style="padding:2px 24px 4px;font-size:20px;font-weight:650;color:#111827;">{html.escape(slot_label)} report</td></tr>
    <tr>
      <td style="padding:0 24px 16px;color:#6b7280;font-size:13px;">
        {html.escape(checked_at)} · {total} sites ·
        <span style="color:#16a34a;font-weight:600;">{len(up)} up</span> ·
        <span style="color:#dc2626;font-weight:600;">{len(down)} down</span>
        {f' · <span style="color:#6b7280;font-weight:600;">{len(unknown)} unknown</span>' if unknown else ''}
      </td>
    </tr>
    <tr><td style="padding:0 24px 18px;">{table_html}</td></tr>
    <tr>
      <td style="padding:12px 24px 22px;border-top:1px solid #f3f4f6;">
        <a href="{html.escape(_dashboard_url())}" style="display:inline-block;padding:10px 14px;background:#111827;color:#ffffff;text-decoration:none;border-radius:8px;font-size:13px;font-weight:600;">Open SiteWatch</a>
      </td>
    </tr>
  </table>
</body>
</html>"""
    return subject, text, html_body


def _smtp_ports(port: int, use_tls: bool) -> list[int]:
    """Primary port first, then common fallback (587 ↔ 465)."""
    ports = [port]
    if use_tls:
        fallback = 465 if port == 587 else 587 if port == 465 else None
        if fallback and fallback not in ports:
            ports.append(fallback)
    return ports


def _send_on_port(
    *,
    host: str,
    port: int,
    user: str,
    password: str,
    use_tls: bool,
    from_addr: str,
    to_addrs: list[str],
    subject: str,
    body: str,
    html_body: str | None = None,
) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = ", ".join(to_addrs)
    msg.set_content(body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")

    use_ssl = use_tls and port in (465, 8465)

    if use_ssl:
        with smtplib.SMTP_SSL(host, port, timeout=20) as server:
            if user:
                server.login(user, password)
            server.send_message(msg, to_addrs=to_addrs)
    elif use_tls:
        with smtplib.SMTP(host, port, timeout=20) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            if user:
                server.login(user, password)
            server.send_message(msg, to_addrs=to_addrs)
    else:
        with smtplib.SMTP(host, port, timeout=20) as server:
            if user:
                server.login(user, password)
            server.send_message(msg, to_addrs=to_addrs)


def _send_smtp_sync(
    *,
    host: str,
    port: int,
    user: str,
    password: str,
    use_tls: bool,
    from_addr: str,
    to_addrs: list[str],
    subject: str,
    body: str,
    html_body: str | None = None,
) -> None:
    # Gmail app passwords are often pasted with spaces
    password = (password or "").replace(" ", "")
    last_error: Exception | None = None
    for try_port in _smtp_ports(port, use_tls):
        try:
            _send_on_port(
                host=host,
                port=try_port,
                user=user,
                password=password,
                use_tls=use_tls,
                from_addr=from_addr,
                to_addrs=to_addrs,
                subject=subject,
                body=body,
                html_body=html_body,
            )
            if try_port != port:
                logger.info("SMTP succeeded on fallback port %s", try_port)
            return
        except Exception as exc:
            last_error = exc
            logger.warning("SMTP failed on port %s: %s", try_port, exc)
    assert last_error is not None
    raise last_error


async def send_email(
    db: AsyncSession,
    settings_row: SettingsRow,
    *,
    subject: str,
    body: str,
    html_body: str | None = None,
    to: str | None = None,
    website_id: int | None = None,
    incident_id: int | None = None,
    kind: str = "alert",
) -> bool:
    if not settings_row.notification_enabled:
        return False

    recipients = normalize_alert_emails(to or settings_row.alert_email)
    sent_to = ", ".join(recipients) if recipients else (to or settings_row.alert_email)

    if not recipients:
        logger.warning("No valid alert emails; skipping: %s", subject)
        db.add(
            NotificationLog(
                website_id=website_id,
                incident_id=incident_id,
                kind=kind,
                subject=subject,
                body=body,
                sent_to=sent_to,
                success=False,
            )
        )
        await db.commit()
        return False

    if not settings_row.smtp_host:
        logger.warning("SMTP not configured; skipping email: %s", subject)
        db.add(
            NotificationLog(
                website_id=website_id,
                incident_id=incident_id,
                kind=kind,
                subject=subject,
                body=body,
                sent_to=sent_to,
                success=False,
            )
        )
        await db.commit()
        return False

    try:
        await asyncio.to_thread(
            _send_smtp_sync,
            host=settings_row.smtp_host,
            port=settings_row.smtp_port,
            user=settings_row.smtp_user,
            password=settings_row.smtp_password,
            use_tls=settings_row.smtp_use_tls,
            from_addr=settings_row.smtp_from or settings_row.smtp_user,
            to_addrs=recipients,
            subject=subject,
            body=body,
            html_body=html_body,
        )
        success = True
        error_detail = None
    except Exception as exc:
        logger.exception("Failed to send email")
        success = False
        error_detail = str(exc)

    db.add(
        NotificationLog(
            website_id=website_id,
            incident_id=incident_id,
            kind=kind,
            subject=subject,
            body=body if success else f"{body}\n\nError: {error_detail}",
            sent_to=sent_to,
            success=success,
        )
    )
    await db.commit()
    if not success and error_detail:
        # Stash last error on the row object for API handlers (not persisted)
        settings_row._last_email_error = error_detail  # type: ignore[attr-defined]
    return success

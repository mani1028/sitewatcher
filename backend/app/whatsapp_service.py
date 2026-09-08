"""WhatsApp alerts via Plivo Messaging API."""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.email_service import format_ist
from app.models import NotificationLog, SettingsRow, SiteOwner


logger = logging.getLogger(__name__)


def normalize_whatsapp_numbers(value: str) -> list[str]:
    """Parse comma/semicolon/newline-separated numbers → digits-only E.164 (no +)."""
    parts = re.split(r"[,;\n]+", (value or "").strip())
    numbers: list[str] = []
    seen: set[str] = set()
    for part in parts:
        raw = part.strip()
        if not raw:
            continue
        had_plus = raw.startswith("+") or raw.startswith("00")
        bare = re.sub(r"\D", "", raw)
        if bare.startswith("00"):
            bare = bare[2:]
        if not had_plus and len(bare) == 10 and bare[0] in "6789":
            bare = "91" + bare
        if not (8 <= len(bare) <= 15):
            continue
        if bare in seen:
            continue
        seen.add(bare)
        numbers.append(bare)
    return numbers


def e164(digits: str) -> str:
    bare = re.sub(r"\D", "", digits or "")
    return f"+{bare}" if bare else ""


def webhook_url() -> str:
    base = get_settings().frontend_url.rstrip("/")
    return f"{base}/api/webhooks/plivo/whatsapp"


def humanize_whatsapp_error(detail: str) -> str:
    text = detail or ""
    lower = text.lower()
    if (
        "401" in lower
        or "authentication" in lower
        or "unauthorized" in lower
        or "access level" in lower
        or "proper credentials" in lower
    ):
        return (
            "Plivo rejected Auth ID / Auth Token. "
            "Open Plivo Console → copy Auth ID and Auth Token into Settings, click Save, then retry."
        )
    if "alphanumeric" in lower or "character length" in lower or ("src" in lower and "invalid" in lower):
        return (
            "Plivo From number rejected. Use your WhatsApp-enabled Plivo number in E.164 "
            "(e.g. +13464802677), Save, then retry. Confirm WhatsApp is enabled for that number in Plivo."
        )
    if "380" in lower or "24 hour" in lower or "24 hours" in lower:
        return (
            "WhatsApp blocked free-form text (error 380). Permanent fix: create an approved UTILITY "
            "template in Plivo (body with {{1}}), put the template name in Settings, Save, retry."
        )
    if "template" in lower or "not exist" in lower or "not found" in lower:
        return (
            "Template rejected. In Plivo → WhatsApp → Templates, create/approve a UTILITY template "
            "with one body variable {{1}}, then enter the exact template name + language (e.g. en_US)."
        )
    return text[:500]


def whatsapp_configured(row: SettingsRow) -> bool:
    auth_id, token = _plivo_creds(row)
    return bool(
        auth_id
        and token
        and (row.whatsapp_display_number or "").strip()
        and (row.whatsapp_template_name or "").strip()
        and normalize_whatsapp_numbers(row.whatsapp_recipients or "")
    )


def _plivo_creds(row: SettingsRow) -> tuple[str, str]:
    auth_id = (getattr(row, "plivo_auth_id", None) or "").strip()
    token = (getattr(row, "plivo_auth_token", None) or "").strip()
    return auth_id, token


def template_param_text(value: str) -> str:
    """WhatsApp template variables cannot contain newlines/tabs."""
    cleaned = re.sub(r"[\r\n\t]+", " | ", value or "")
    cleaned = re.sub(r" {2,}", " ", cleaned)
    return cleaned.strip()[:1024] or "SiteWatch alert"


def _compact_status(part: str | None) -> str:
    """Turn a probe fragment into a short cell value (502, timeout, down…)."""
    raw = (part or "").strip()
    if not raw:
        return "down"
    text = re.sub(
        r"^(frontend\s*\+\s*backend/?api|frontend|backend/?api)\s*:\s*",
        "",
        raw,
        flags=re.I,
    ).strip()
    if not text or text.upper() == "DOWN":
        return "down"

    m = re.search(r"expected\s+\d+\s*,\s*got\s+(\d+)", text, flags=re.I)
    if m:
        return m.group(1)
    m = re.search(r"\b(?:got|status)\s+(\d{3})\b", text, flags=re.I)
    if m:
        return m.group(1)
    low = text.lower()
    if "timeout" in low:
        return "timeout"
    if "connection" in low or "refused" in low:
        return "conn-fail"
    if "ssl" in low or "certificate" in low:
        return "ssl"
    if "unreachable" in low:
        return "down"
    return text[:16]


def probe_front_back(reason: str | None) -> tuple[str, str]:
    """Parse incident reason → (frontend status, backend status)."""
    raw = (reason or "").strip()
    if not raw:
        return ("down", "n/a")

    front_part: str | None = None
    back_part: str | None = None
    other: list[str] = []
    for part in re.split(r"\s*;\s*", raw):
        if not part.strip():
            continue
        low = part.lower()
        if low.startswith("frontend"):
            front_part = part
        elif low.startswith("backend"):
            back_part = part
        else:
            other.append(part)

    if front_part is not None or back_part is not None:
        front = _compact_status(front_part) if front_part else "OK"
        back = _compact_status(back_part) if back_part else "OK"
        return (front, back)

    # Legacy / single URL — site/frontend issue; backend not checked
    return (_compact_status(other[0] if other else raw), "n/a")


def _status_label(value: str) -> str:
    v = (value or "").strip()
    if v in {"OK", "ok"}:
        return "OK"
    if v in {"—", "-", "n/a", "NA"}:
        return "n/a"
    return v


def build_whatsapp_digest_text(
    *,
    downs: list[dict[str, str]],
    recoveries: list[dict[str, str]],
) -> str:
    """Mobile-friendly digest: clear Frontend vs Backend per site (no monospace table)."""
    stamp = format_ist()
    lines = [f"SiteWatch · {stamp}"]

    if downs:
        lines.append("")
        lines.append(f"DOWN ({len(downs)})")
        for i, item in enumerate(downs, start=1):
            name = (item.get("name") or "site").strip()
            front, back = probe_front_back(item.get("reason"))
            lines.append("")
            lines.append(f"{i}. {name}")
            lines.append(f"   Frontend: {_status_label(front)}")
            lines.append(f"   Backend:  {_status_label(back)}")

    if recoveries:
        lines.append("")
        lines.append(f"RECOVERED ({len(recoveries)})")
        for i, item in enumerate(recoveries, start=1):
            name = (item.get("name") or "site").strip()
            downtime = (item.get("downtime") or "").strip()
            lines.append("")
            if downtime:
                lines.append(f"{i}. {name}")
                lines.append(f"   Downtime: {downtime}")
            else:
                lines.append(f"{i}. {name} · back up")

    lines.append("")
    lines.append(get_settings().frontend_url.rstrip("/"))
    return "\n".join(lines).strip()[:4000]


def filter_by_owner_scope(
    items: list[dict[str, str]],
    scope: str,
) -> list[dict[str, str]]:
    scope = (scope or "inhouse").lower()
    if scope == "all":
        scoped = items
    else:
        wanted = SiteOwner.CLIENT.value if scope == "client" else SiteOwner.INHOUSE.value
        scoped = [i for i in items if (i.get("owner") or SiteOwner.INHOUSE.value) == wanted]
    return [i for i in scoped if i.get("whatsapp_alerts") in (True, "true", "1", 1)]


async def _post_plivo_message(
    *,
    auth_id: str,
    auth_token: str,
    src: str,
    dst: str,
    text: str,
    template_name: str = "",
    template_lang: str = "en_US",
) -> tuple[bool, str]:
    """Send WhatsApp via Plivo.

    Permanent (business-initiated) alerts require an approved template.
    Free-form text is only used for inbound session auto-replies.
    """
    url = f"https://api.plivo.com/v1/Account/{auth_id}/Message/"
    payload: dict[str, Any] = {
        "src": e164(src),
        "dst": e164(dst),
        "type": "whatsapp",
        "url": webhook_url(),
        "method": "POST",
    }
    name = (template_name or "").strip()
    if name:
        lang = (template_lang or "en_US").strip() or "en_US"
        payload["template"] = {
            "name": name,
            "language": lang,
            "components": [
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": template_param_text(text)}],
                }
            ],
        }
    else:
        payload["text"] = text

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            res = await client.post(url, auth=(auth_id, auth_token), json=payload)
        if res.status_code >= 400:
            detail = res.text[:500]
            logger.warning("Plivo WhatsApp send failed to %s: %s %s", dst, res.status_code, detail)
            return False, detail
        return True, res.text[:300]
    except Exception as exc:  # noqa: BLE001
        logger.exception("Plivo request error")
        return False, str(exc)[:500]


async def reply_whatsapp_session(
    settings_row: SettingsRow,
    *,
    to: str,
    text: str,
) -> tuple[bool, str]:
    """Reply inside an open session (inbound webhook) — free-form, no template."""
    auth_id, auth_token = _plivo_creds(settings_row)
    src = (settings_row.whatsapp_display_number or "").strip()
    if not auth_id or not auth_token or not src or not to:
        return False, "WhatsApp not configured"
    return await _post_plivo_message(
        auth_id=auth_id,
        auth_token=auth_token,
        src=src,
        dst=to,
        text=text,
        template_name="",
    )


async def send_whatsapp_message(
    db: AsyncSession,
    settings_row: SettingsRow,
    *,
    text: str,
    subject: str,
    kind: str = "whatsapp_digest",
    to: str | None = None,
) -> bool:
    if not settings_row.notification_enabled:
        return False
    if not settings_row.whatsapp_enabled:
        return False

    auth_id, auth_token = _plivo_creds(settings_row)
    src = (settings_row.whatsapp_display_number or "").strip()
    recipients = normalize_whatsapp_numbers(to or settings_row.whatsapp_recipients)
    template = (settings_row.whatsapp_template_name or "").strip()
    lang = (settings_row.whatsapp_template_lang or "en_US").strip() or "en_US"
    if not auth_id or not auth_token or not src or not recipients:
        return False
    # Template preferred for permanent (business-initiated) alerts. If blank, send free-form
    # text — works inside an open 24h WhatsApp session after the recipient messages first.

    any_ok = False
    errors: list[str] = []
    for number in recipients:
        ok, detail = await _post_plivo_message(
            auth_id=auth_id,
            auth_token=auth_token,
            src=src,
            dst=number,
            text=text,
            template_name=template,
            template_lang=lang,
        )
        db.add(
            NotificationLog(
                website_id=None,
                incident_id=None,
                kind=kind,
                subject=subject[:255],
                body=text[:4000],
                sent_to=e164(number),
                success=ok,
            )
        )
        if ok:
            any_ok = True
        else:
            errors.append(f"{number}: {detail}")

    await db.commit()
    if errors:
        setattr(settings_row, "_last_whatsapp_error", humanize_whatsapp_error("; ".join(errors)))
    return any_ok


async def send_whatsapp_digest(
    db: AsyncSession,
    settings_row: SettingsRow,
    *,
    downs: list[dict[str, str]],
    recoveries: list[dict[str, str]],
    subject: str,
) -> bool:
    if not settings_row.whatsapp_enabled:
        return False
    scope = getattr(settings_row, "whatsapp_owner_scope", "inhouse") or "inhouse"
    downs_f = filter_by_owner_scope(downs, scope)
    recoveries_f = filter_by_owner_scope(recoveries, scope)
    if not downs_f and not recoveries_f:
        logger.info("WhatsApp digest skipped: no opted-in sites in scope=%s", scope)
        return False
    text = build_whatsapp_digest_text(downs=downs_f, recoveries=recoveries_f)
    return await send_whatsapp_message(
        db,
        settings_row,
        text=text,
        subject=subject,
        kind="whatsapp_digest",
    )

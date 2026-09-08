from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import create_access_token, get_current_admin, hash_password, verify_password
from app.database import get_db
from app.email_service import build_test_email, send_email
from app.whatsapp_service import (
    build_whatsapp_digest_text,
    e164,
    reply_whatsapp_session,
    send_whatsapp_message,
    webhook_url,
    whatsapp_configured,
)
from app.models import Check, Incident, IncidentStatus, NotificationLog, SettingsRow, SiteStatus, Website
import logging

logger = logging.getLogger(__name__)
from app.schemas import (
    CheckOut,
    DashboardOut,
    IncidentOut,
    LoginRequest,
    NotificationOut,
    NotificationPage,
    SettingsOut,
    SettingsUpdate,
    TestEmailRequest,
    TestWhatsappRequest,
    TokenResponse,
    WebsiteCreate,
    WebsiteOut,
    WebsiteUpdate,
)


router = APIRouter()


def _normalize_optional_url(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    if not text.startswith(("http://", "https://")):
        text = f"https://{text}"
    return text.rstrip("/")


def serialize_incident(incident: Incident, website: Website | None = None) -> IncidentOut:
    site = website or getattr(incident, "website", None)
    return IncidentOut(
        id=incident.id,
        website_id=incident.website_id,
        website_name=site.name if site else None,
        website_url=site.url if site else None,
        started_at=incident.started_at,
        resolved_at=incident.resolved_at,
        duration_seconds=incident.duration_seconds,
        reason=incident.reason,
        status=incident.status.value if hasattr(incident.status, "value") else str(incident.status),
    )


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/auth/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    row = await db.scalar(select(SettingsRow).where(SettingsRow.id == 1))
    if not row or row.email.lower() != payload.email.lower() or not verify_password(payload.password, row.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return TokenResponse(access_token=create_access_token(row.email))


@router.get("/dashboard", response_model=DashboardOut)
async def dashboard(
    _: SettingsRow = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> DashboardOut:
    websites = list((await db.execute(select(Website).order_by(Website.name))).scalars().all())
    up = sum(1 for w in websites if w.status == SiteStatus.UP)
    down = sum(1 for w in websites if w.status == SiteStatus.DOWN)
    slow = sum(1 for w in websites if w.status == SiteStatus.SLOW)
    maintenance = sum(1 for w in websites if w.status == SiteStatus.MAINTENANCE)
    overall = round(sum(w.uptime_percent for w in websites) / len(websites), 2) if websites else 100.0

    incidents = list(
        (
            await db.execute(
                select(Incident)
                .options(selectinload(Incident.website))
                .order_by(Incident.started_at.desc())
                .limit(8)
            )
        ).scalars().all()
    )

    return DashboardOut(
        total=len(websites),
        up=up,
        down=down,
        slow=slow,
        maintenance=maintenance,
        overall_uptime=overall,
        websites=[WebsiteOut.model_validate(w) for w in websites],
        recent_incidents=[serialize_incident(i) for i in incidents],
    )


@router.get("/websites", response_model=list[WebsiteOut])
async def list_websites(
    _: SettingsRow = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> list[WebsiteOut]:
    rows = list((await db.execute(select(Website).order_by(Website.name))).scalars().all())
    return [WebsiteOut.model_validate(w) for w in rows]


@router.post("/websites", response_model=WebsiteOut)
async def create_website(
    payload: WebsiteCreate,
    _: SettingsRow = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> WebsiteOut:
    url = payload.url.strip()
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    url = url.rstrip("/")

    existing = await db.scalar(select(Website).where(Website.url == url))
    if existing:
        raise HTTPException(status_code=400, detail=f"Website already exists: {existing.name}")

    # Also block same host with/without trailing slash variants stored differently
    host_key = url.lower().removeprefix("https://").removeprefix("http://")
    rows = list((await db.execute(select(Website))).scalars().all())
    for row in rows:
        row_key = row.url.lower().removeprefix("https://").removeprefix("http://").rstrip("/")
        if row_key == host_key:
            raise HTTPException(status_code=400, detail=f"Website already exists: {row.name}")

    website = Website(
        name=payload.name.strip(),
        url=url,
        health_url=_normalize_optional_url(payload.health_url),
        category=payload.category,
        owner=payload.owner,
        check_interval=payload.check_interval,
        timeout=payload.timeout,
        expected_status=payload.expected_status,
        monitor_ssl=payload.monitor_ssl,
        whatsapp_alerts=bool(payload.whatsapp_alerts),
        high_priority=bool(payload.high_priority),
        next_check_at=datetime.now(timezone.utc),
    )
    db.add(website)
    await db.commit()
    await db.refresh(website)
    return WebsiteOut.model_validate(website)


@router.get("/websites/{website_id}", response_model=WebsiteOut)
async def get_website(
    website_id: int,
    _: SettingsRow = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> WebsiteOut:
    website = await db.get(Website, website_id)
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    return WebsiteOut.model_validate(website)


@router.put("/websites/{website_id}", response_model=WebsiteOut)
async def update_website(
    website_id: int,
    payload: WebsiteUpdate,
    _: SettingsRow = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> WebsiteOut:
    website = await db.get(Website, website_id)
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    data = payload.model_dump(exclude_unset=True)
    if "url" in data and data["url"]:
        url = data["url"].strip()
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        data["url"] = url.rstrip("/")
    if "health_url" in data:
        data["health_url"] = _normalize_optional_url(data.get("health_url"))
    if "name" in data and data["name"]:
        data["name"] = data["name"].strip()

    interval_changed = "check_interval" in data and data["check_interval"] != website.check_interval
    priority_on = data.get("high_priority") is True and not bool(getattr(website, "high_priority", False))
    for key, value in data.items():
        setattr(website, key, value)
    if (
        interval_changed
        or data.get("enabled") is True
        or "health_url" in data
        or "url" in data
        or priority_on
    ):
        website.next_check_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(website)
    return WebsiteOut.model_validate(website)


@router.delete("/websites/{website_id}")
async def delete_website(
    website_id: int,
    _: SettingsRow = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    website = await db.get(Website, website_id)
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    await db.delete(website)
    await db.commit()
    return {"ok": True}


@router.get("/websites/{website_id}/checks", response_model=list[CheckOut])
async def website_checks(
    website_id: int,
    hours: int = 24,
    _: SettingsRow = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> list[CheckOut]:
    website = await db.get(Website, website_id)
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    since = datetime.now(timezone.utc) - timedelta(hours=max(1, min(hours, 168)))
    rows = list(
        (
            await db.execute(
                select(Check)
                .where(Check.website_id == website_id, Check.checked_at >= since)
                .order_by(Check.checked_at.desc())
                .limit(500)
            )
        ).scalars().all()
    )
    return [CheckOut.model_validate(r) for r in rows]


@router.get("/websites/{website_id}/incidents", response_model=list[IncidentOut])
async def website_incidents(
    website_id: int,
    _: SettingsRow = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> list[IncidentOut]:
    website = await db.get(Website, website_id)
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    rows = list(
        (
            await db.execute(
                select(Incident)
                .where(Incident.website_id == website_id)
                .order_by(Incident.started_at.desc())
                .limit(100)
            )
        ).scalars().all()
    )
    return [serialize_incident(r, website) for r in rows]


@router.get("/incidents", response_model=list[IncidentOut])
async def list_incidents(
    status_filter: str | None = None,
    _: SettingsRow = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> list[IncidentOut]:
    query = select(Incident).options(selectinload(Incident.website)).order_by(Incident.started_at.desc()).limit(100)
    if status_filter == "open":
        query = query.where(Incident.status == IncidentStatus.OPEN)
    elif status_filter == "resolved":
        query = query.where(Incident.status == IncidentStatus.RESOLVED)
    rows = list((await db.execute(query)).scalars().all())
    return [serialize_incident(r) for r in rows]


def serialize_settings(row: SettingsRow) -> SettingsOut:
    plivo_id = (getattr(row, "plivo_auth_id", None) or "").strip()
    plivo_tok = (getattr(row, "plivo_auth_token", None) or "").strip()
    return SettingsOut(
        email=row.email,
        alert_email=row.alert_email,
        notification_enabled=row.notification_enabled,
        slow_threshold_ms=row.slow_threshold_ms,
        failure_threshold=row.failure_threshold,
        recovery_threshold=row.recovery_threshold,
        smtp_host=row.smtp_host,
        smtp_port=row.smtp_port,
        smtp_user=row.smtp_user,
        smtp_from=row.smtp_from,
        smtp_use_tls=row.smtp_use_tls,
        smtp_password=row.smtp_password or "",
        smtp_configured=bool(row.smtp_host),
        whatsapp_enabled=bool(row.whatsapp_enabled),
        whatsapp_phone_number_id=row.whatsapp_phone_number_id or "",
        whatsapp_display_number=row.whatsapp_display_number or "",
        whatsapp_recipients=row.whatsapp_recipients or "",
        whatsapp_owner_scope=row.whatsapp_owner_scope or "inhouse",
        whatsapp_template_name=row.whatsapp_template_name or "",
        whatsapp_template_lang=row.whatsapp_template_lang or "en",
        whatsapp_token_configured=bool((row.whatsapp_access_token or "").strip()),
        whatsapp_configured=whatsapp_configured(row),
        plivo_auth_id=plivo_id,
        plivo_auth_token=plivo_tok,
        plivo_token_configured=bool(plivo_tok),
        whatsapp_webhook_url=webhook_url(),
    )


@router.get("/settings", response_model=SettingsOut)
async def get_settings_api(
    row: SettingsRow = Depends(get_current_admin),
) -> SettingsOut:
    return serialize_settings(row)


@router.put("/settings", response_model=SettingsOut)
async def update_settings(
    payload: SettingsUpdate,
    row: SettingsRow = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> SettingsOut:
    data = payload.model_dump(exclude_unset=True)
    password = data.pop("password", None)
    meta_token = data.pop("whatsapp_access_token", None)
    plivo_token = data.pop("plivo_auth_token", None)
    for key, value in data.items():
        setattr(row, key, value)
    if meta_token is not None:
        # Allow clearing leftover Meta token with ""
        row.whatsapp_access_token = meta_token.strip()
    if plivo_token is not None and plivo_token.strip():
        row.plivo_auth_token = plivo_token.strip()
    if password:
        row.password_hash = hash_password(password)
    await db.commit()
    await db.refresh(row)
    return serialize_settings(row)


@router.post("/settings/test-email")
async def test_email(
    payload: TestEmailRequest,
    row: SettingsRow = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, bool | str]:
    if not row.smtp_host or not row.smtp_user:
        raise HTTPException(status_code=400, detail="Fill SMTP host and username, then Save settings.")
    if not row.smtp_password:
        raise HTTPException(
            status_code=400,
            detail="SMTP password is empty. Paste the Gmail app password and Save settings first.",
        )
    if not row.alert_email:
        raise HTTPException(status_code=400, detail="Add at least one Alert email, then Save settings.")

    subject, body, html_body = build_test_email()
    ok = await send_email(
        db,
        row,
        subject=subject,
        body=body,
        html_body=html_body,
        to=str(payload.to) if payload.to else None,
        kind="test",
    )
    if not ok:
        detail = getattr(row, "_last_email_error", None) or "Failed to send email. Check SMTP settings."
        if "BadCredentials" in detail or "Username and Password not accepted" in detail:
            detail = (
                "Gmail rejected the username/password. "
                "Create a new App Password at https://myaccount.google.com/apppasswords "
                "(2-Step Verification must be on), paste it in SMTP Password, Save, then retry."
            )
        raise HTTPException(status_code=400, detail=detail)
    return {"ok": True, "message": "Test email sent"}


@router.post("/settings/test-whatsapp")
async def test_whatsapp(
    payload: TestWhatsappRequest = TestWhatsappRequest(),
    row: SettingsRow = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, bool | str]:
    if not row.whatsapp_enabled:
        raise HTTPException(status_code=400, detail="Enable WhatsApp alerts, then Save settings.")
    auth_id = (getattr(row, "plivo_auth_id", None) or "").strip()
    token = (getattr(row, "plivo_auth_token", None) or "").strip()
    if not auth_id:
        raise HTTPException(
            status_code=400,
            detail="Add Plivo Auth ID (Console → Auth ID), then Save settings.",
        )
    if not token:
        raise HTTPException(
            status_code=400,
            detail="Paste Plivo Auth Token (Console → Auth Token), then Save settings.",
        )
    if not (row.whatsapp_display_number or "").strip():
        raise HTTPException(status_code=400, detail="Add Plivo WhatsApp From number (e.g. +13464802677), then Save.")

    to = payload.to
    if not to and not (row.whatsapp_recipients or "").strip():
        raise HTTPException(
            status_code=400,
            detail="Add at least one WhatsApp recipient number, click Save settings, then retry.",
        )

    text = build_whatsapp_digest_text(
        downs=[
            {
                "name": "aisync-innovations",
                "reason": "DOWN",
            },
            {
                "name": "visyscloudsolutions",
                "reason": "Backend/API: expected 200, got 502",
            },
            {
                "name": "visyscloudtech",
                "reason": "Frontend: expected 200, got 503; Backend/API: expected 200, got 502",
            },
        ],
        recoveries=[
            {"name": "demo-site", "downtime": "12m 4s"},
        ],
    )
    ok = await send_whatsapp_message(
        db,
        row,
        text=text,
        subject="SiteWatch WhatsApp test",
        kind="whatsapp_test",
        to=to,
    )
    if not ok:
        detail = getattr(row, "_last_whatsapp_error", None) or "Failed to send WhatsApp message."
        raise HTTPException(status_code=400, detail=detail)
    tmpl = (row.whatsapp_template_name or "").strip()
    if tmpl:
        msg = f"Test queued via template “{tmpl}”. Check the recipient phone (and Plivo Logs if it fails)."
    else:
        msg = (
            "Test queued. If you do not receive it: from the recipient phone, WhatsApp "
            f"{(row.whatsapp_display_number or '').strip()} once (say hi), then click Send test WhatsApp again. "
            "No template needed — WhatsApp allows free text for 24h after that."
        )
    return {"ok": True, "message": msg}


@router.api_route("/webhooks/plivo/whatsapp", methods=["GET", "POST"])
async def plivo_whatsapp_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Public Plivo status / inbound webhook — paste this URL in Plivo WhatsApp settings."""
    try:
        if request.method == "POST":
            content_type = request.headers.get("content-type", "")
            if "application/json" in content_type:
                payload = await request.json()
            else:
                form = await request.form()
                payload = {str(k): str(v) for k, v in form.items()}
            logger.info("Plivo WhatsApp webhook: %s", str(payload)[:800])

            # Inbound user message → open 24h session; auto-confirm (no template needed)
            status = str(payload.get("Status") or payload.get("status") or "").lower()
            text = str(payload.get("Text") or payload.get("Body") or payload.get("text") or "")
            from_raw = str(payload.get("From") or payload.get("from") or "")
            # Status callbacks have Status; inbound usually has Text/From without failed/queued
            is_status = bool(status) and status in {
                "queued",
                "sent",
                "delivered",
                "read",
                "failed",
                "undelivered",
            }
            if from_raw and not is_status:
                row = await db.scalar(select(SettingsRow).where(SettingsRow.id == 1))
                if row and row.whatsapp_enabled:
                    dst = e164(from_raw.replace("whatsapp:", ""))
                    ok, detail = await reply_whatsapp_session(
                        row,
                        to=dst,
                        text=(
                            "SiteWatch: WhatsApp alerts are on for 24 hours from this chat. "
                            "You will get downtime/recovery messages here (no template)."
                        ),
                    )
                    logger.info("Session auto-reply to %s ok=%s %s", dst, ok, detail[:120] if detail else "")
        else:
            logger.info("Plivo WhatsApp webhook ping")
    except Exception:  # noqa: BLE001
        logger.exception("Plivo webhook parse error")
    return {"status": "ok"}


@router.get("/notifications", response_model=NotificationPage)
async def list_notifications(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    kind: str | None = Query(None, pattern="^(down|recovery|test|digest|whatsapp_digest|whatsapp_test|client_report)$"),
    status: str | None = Query(None, pattern="^(sent|failed)$"),
    _: SettingsRow = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> NotificationPage:
    filters = []
    if kind:
        filters.append(NotificationLog.kind == kind)
    if status == "sent":
        filters.append(NotificationLog.success.is_(True))
    elif status == "failed":
        filters.append(NotificationLog.success.is_(False))

    count_stmt = select(func.count()).select_from(NotificationLog)
    list_stmt = select(NotificationLog).order_by(NotificationLog.created_at.desc())
    if filters:
        count_stmt = count_stmt.where(*filters)
        list_stmt = list_stmt.where(*filters)

    total = int(await db.scalar(count_stmt) or 0)
    pages = max(1, (total + limit - 1) // limit) if total else 1
    page = min(page, pages)
    offset = (page - 1) * limit
    rows = list((await db.execute(list_stmt.offset(offset).limit(limit))).scalars().all())
    return NotificationPage(
        items=[NotificationOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        limit=limit,
        pages=pages,
    )

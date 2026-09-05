from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import create_access_token, get_current_admin, hash_password, verify_password
from app.database import get_db
from app.email_service import build_test_email, send_email
from app.models import Check, Incident, IncidentStatus, NotificationLog, SettingsRow, SiteStatus, Website
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
    for key, value in data.items():
        setattr(website, key, value)
    if interval_changed or data.get("enabled") is True or "health_url" in data or "url" in data:
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


@router.get("/settings", response_model=SettingsOut)
async def get_settings_api(
    row: SettingsRow = Depends(get_current_admin),
) -> SettingsOut:
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
        smtp_configured=bool(row.smtp_host),
    )


@router.put("/settings", response_model=SettingsOut)
async def update_settings(
    payload: SettingsUpdate,
    row: SettingsRow = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> SettingsOut:
    data = payload.model_dump(exclude_unset=True)
    password = data.pop("password", None)
    for key, value in data.items():
        setattr(row, key, value)
    if password:
        row.password_hash = hash_password(password)
    await db.commit()
    await db.refresh(row)
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
        smtp_configured=bool(row.smtp_host),
    )


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


@router.get("/notifications", response_model=NotificationPage)
async def list_notifications(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    kind: str | None = Query(None, pattern="^(down|recovery|test)$"),
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

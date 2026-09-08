import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text

from app.auth import hash_password
from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.models import SettingsRow
from app.monitor import (
    cleanup_old_checks,
    run_due_checks,
    run_ssl_checks,
    send_client_status_report,
)
from app.routers import router


logging.basicConfig(level=logging.INFO)
logging.getLogger("apscheduler").setLevel(logging.WARNING)
logging.getLogger("apscheduler.executors.default").setLevel(logging.WARNING)
logging.getLogger("apscheduler.scheduler").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)
settings = get_settings()
scheduler = AsyncIOScheduler()


async def ensure_schema() -> None:
    """Apply lightweight schema upgrades on existing databases."""
    statements = [
        "ALTER TABLE settings ALTER COLUMN alert_email TYPE VARCHAR(2000)",
        "ALTER TABLE notifications ALTER COLUMN sent_to TYPE VARCHAR(2000)",
        "ALTER TABLE websites ADD COLUMN IF NOT EXISTS category VARCHAR(32) DEFAULT 'website'",
        "ALTER TABLE websites ADD COLUMN IF NOT EXISTS owner VARCHAR(32) DEFAULT 'inhouse'",
        "ALTER TABLE websites ADD COLUMN IF NOT EXISTS health_url VARCHAR(500)",
        "ALTER TABLE websites ADD COLUMN IF NOT EXISTS whatsapp_alerts BOOLEAN DEFAULT false",
        "UPDATE websites SET whatsapp_alerts = false WHERE whatsapp_alerts IS NULL",
        "ALTER TABLE websites ADD COLUMN IF NOT EXISTS high_priority BOOLEAN DEFAULT false",
        "UPDATE websites SET high_priority = false WHERE high_priority IS NULL",
        "ALTER TABLE settings ADD COLUMN IF NOT EXISTS whatsapp_enabled BOOLEAN DEFAULT false",
        "ALTER TABLE settings ADD COLUMN IF NOT EXISTS whatsapp_phone_number_id VARCHAR(64) DEFAULT ''",
        "ALTER TABLE settings ADD COLUMN IF NOT EXISTS whatsapp_display_number VARCHAR(32) DEFAULT ''",
        "ALTER TABLE settings ADD COLUMN IF NOT EXISTS whatsapp_access_token VARCHAR(500) DEFAULT ''",
        "ALTER TABLE settings ADD COLUMN IF NOT EXISTS whatsapp_recipients VARCHAR(2000) DEFAULT ''",
        "ALTER TABLE settings ADD COLUMN IF NOT EXISTS whatsapp_owner_scope VARCHAR(32) DEFAULT 'inhouse'",
        "ALTER TABLE settings ADD COLUMN IF NOT EXISTS whatsapp_template_name VARCHAR(128) DEFAULT ''",
        "ALTER TABLE settings ADD COLUMN IF NOT EXISTS whatsapp_template_lang VARCHAR(16) DEFAULT 'en'",
        "ALTER TABLE settings ADD COLUMN IF NOT EXISTS plivo_auth_id VARCHAR(64) DEFAULT ''",
        "ALTER TABLE settings ADD COLUMN IF NOT EXISTS plivo_auth_token VARCHAR(255) DEFAULT ''",
        "UPDATE settings SET whatsapp_display_number = '+1 346 480 2677' WHERE id = 1 AND (whatsapp_display_number IS NULL OR whatsapp_display_number = '')",
        # Heuristic backfill for existing rows still on default
        """
        UPDATE websites SET category = 'portal'
        WHERE (category IS NULL OR category = 'website')
          AND (url ILIKE '%://portal.%' OR url ILIKE '%/portal.%' OR name ILIKE '%portal%')
        """,
        """
        UPDATE websites SET category = 'microservice'
        WHERE (category IS NULL OR category = 'website')
          AND (url ILIKE '%api.%' OR url ILIKE '%://api%' OR name ILIKE '%api%'
               OR url ILIKE '%filemanager%' OR name ILIKE '%filemanager%')
        """,
        "UPDATE websites SET category = 'website' WHERE category IS NULL OR category = ''",
        "UPDATE websites SET owner = 'inhouse' WHERE owner IS NULL OR owner = ''",
    ]
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for stmt in statements:
            try:
                await conn.execute(text(stmt))
            except Exception:
                pass


async def seed_admin() -> None:
    async with SessionLocal() as db:
        existing = await db.scalar(select(SettingsRow).where(SettingsRow.id == 1))
        if existing:
            return
        db.add(
            SettingsRow(
                id=1,
                email=settings.admin_email,
                password_hash=hash_password(settings.admin_password),
                alert_email=settings.alert_email or settings.admin_email,
                notification_enabled=settings.notifications_enabled,
                slow_threshold_ms=settings.slow_threshold_ms,
                failure_threshold=settings.failure_threshold,
                recovery_threshold=settings.recovery_threshold,
                smtp_host=settings.smtp_host,
                smtp_port=settings.smtp_port,
                smtp_user=settings.smtp_user,
                smtp_password=settings.smtp_password,
                smtp_from=settings.smtp_from,
                smtp_use_tls=settings.smtp_use_tls,
            )
        )
        await db.commit()
        logger.info("Seeded admin account: %s", settings.admin_email)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await ensure_schema()
    await seed_admin()
    await cleanup_old_checks()

    scheduler.add_job(run_due_checks, "interval", seconds=settings.scheduler_tick_seconds, id="due_checks", max_instances=1)
    scheduler.add_job(run_ssl_checks, "interval", hours=6, id="ssl_checks", max_instances=1)
    scheduler.add_job(cleanup_old_checks, "interval", hours=1, id="cleanup", max_instances=1)
    scheduler.add_job(
        send_client_status_report,
        CronTrigger(hour=10, minute=0, timezone="Asia/Kolkata"),
        kwargs={"slot": "morning"},
        id="client_report_morning",
        max_instances=1,
    )
    scheduler.add_job(
        send_client_status_report,
        CronTrigger(hour=18, minute=0, timezone="Asia/Kolkata"),
        kwargs={"slot": "evening"},
        id="client_report_evening",
        max_instances=1,
    )
    scheduler.start()
    logger.info("SiteWatch monitor started (client reports 10:00 & 18:00 IST)")
    yield
    scheduler.shutdown(wait=False)
    await engine.dispose()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_url,
        "https://sitewatch.ai4bzr.com",
        "http://sitewatch.ai4bzr.com",
        "https://sitewatch.aibzr.com",
        "http://sitewatch.aibzr.com",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router, prefix="/api")

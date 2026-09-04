import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text

from app.auth import hash_password
from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.models import SettingsRow
from app.monitor import cleanup_old_checks, run_due_checks, run_ssl_checks
from app.routers import router


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
settings = get_settings()
scheduler = AsyncIOScheduler()


async def ensure_schema() -> None:
    """Widen columns for multi-recipient alerts on existing databases."""
    statements = [
        "ALTER TABLE settings ALTER COLUMN alert_email TYPE VARCHAR(2000)",
        "ALTER TABLE notifications ALTER COLUMN sent_to TYPE VARCHAR(2000)",
    ]
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for stmt in statements:
            try:
                await conn.execute(text(stmt))
            except Exception:
                # Column already wide enough, or table not ready yet
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
    scheduler.add_job(cleanup_old_checks, "cron", hour=3, minute=15, id="cleanup", max_instances=1)
    scheduler.start()
    logger.info("SiteWatch monitor started")
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

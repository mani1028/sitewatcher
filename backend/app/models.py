import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SiteStatus(str, enum.Enum):
    UP = "UP"
    DOWN = "DOWN"
    SLOW = "SLOW"
    UNKNOWN = "UNKNOWN"
    MAINTENANCE = "MAINTENANCE"


class CheckStatus(str, enum.Enum):
    UP = "UP"
    DOWN = "DOWN"
    SLOW = "SLOW"
    ERROR = "ERROR"


class IncidentStatus(str, enum.Enum):
    OPEN = "open"
    RESOLVED = "resolved"


class SiteCategory(str, enum.Enum):
    PORTAL = "portal"
    WEBSITE = "website"
    MICROSERVICE = "microservice"
    OTHER = "other"


class SiteOwner(str, enum.Enum):
    """Who the site belongs to — separate from technical type (category)."""

    INHOUSE = "inhouse"
    CLIENT = "client"


class Website(Base):
    __tablename__ = "websites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    # Optional API/backend health endpoint — both url and health_url must succeed
    health_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    category: Mapped[str] = mapped_column(String(32), default=SiteCategory.WEBSITE.value, index=True)
    owner: Mapped[str] = mapped_column(String(32), default=SiteOwner.INHOUSE.value, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    check_interval: Mapped[int] = mapped_column(Integer, default=60)
    timeout: Mapped[int] = mapped_column(Integer, default=10)
    expected_status: Mapped[int] = mapped_column(Integer, default=200)
    monitor_ssl: Mapped[bool] = mapped_column(Boolean, default=True)
    maintenance_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    # Opt-in WhatsApp alerts for this site (global WhatsApp must also be enabled)
    whatsapp_alerts: Mapped[bool] = mapped_column(Boolean, default=False)
    # While DOWN/FAILING, re-check every ~30s instead of the normal interval
    high_priority: Mapped[bool] = mapped_column(Boolean, default=False)

    status: Mapped[SiteStatus] = mapped_column(
        Enum(SiteStatus, name="site_status"), default=SiteStatus.UNKNOWN
    )
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    consecutive_successes: Mapped[int] = mapped_column(Integer, default=0)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_response_time: Mapped[float | None] = mapped_column(Float)
    last_status_code: Mapped[int | None] = mapped_column(Integer)
    last_error: Mapped[str | None] = mapped_column(String(500))
    next_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    ssl_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ssl_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    uptime_percent: Mapped[float] = mapped_column(Float, default=100.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    checks: Mapped[list["Check"]] = relationship(back_populates="website", cascade="all, delete-orphan")
    incidents: Mapped[list["Incident"]] = relationship(
        back_populates="website", cascade="all, delete-orphan"
    )


class Check(Base):
    __tablename__ = "checks"
    __table_args__ = (Index("ix_checks_website_checked", "website_id", "checked_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    website_id: Mapped[int] = mapped_column(ForeignKey("websites.id", ondelete="CASCADE"), index=True)
    status: Mapped[CheckStatus] = mapped_column(Enum(CheckStatus, name="check_status"))
    status_code: Mapped[int | None] = mapped_column(Integer)
    response_time: Mapped[float | None] = mapped_column(Float)
    error_type: Mapped[str | None] = mapped_column(String(120))
    error_message: Mapped[str | None] = mapped_column(String(500))
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    website: Mapped["Website"] = relationship(back_populates="checks")


class Incident(Base):
    __tablename__ = "incidents"
    __table_args__ = (Index("ix_incidents_website_started", "website_id", "started_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    website_id: Mapped[int] = mapped_column(ForeignKey("websites.id", ondelete="CASCADE"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(500), default="Website unreachable")
    status: Mapped[IncidentStatus] = mapped_column(
        Enum(IncidentStatus, name="incident_status"), default=IncidentStatus.OPEN
    )
    notification_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    recovery_notification_sent: Mapped[bool] = mapped_column(Boolean, default=False)

    website: Mapped["Website"] = relationship(back_populates="incidents")


class SettingsRow(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    alert_email: Mapped[str] = mapped_column(String(2000), nullable=False)
    notification_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    slow_threshold_ms: Mapped[int] = mapped_column(Integer, default=2000)
    failure_threshold: Mapped[int] = mapped_column(Integer, default=3)
    recovery_threshold: Mapped[int] = mapped_column(Integer, default=2)
    smtp_host: Mapped[str] = mapped_column(String(255), default="")
    smtp_port: Mapped[int] = mapped_column(Integer, default=587)
    smtp_user: Mapped[str] = mapped_column(String(255), default="")
    smtp_password: Mapped[str] = mapped_column(String(255), default="")
    smtp_from: Mapped[str] = mapped_column(String(255), default="SiteWatch <alerts@yourdomain.com>")
    smtp_use_tls: Mapped[bool] = mapped_column(Boolean, default=True)
    # WhatsApp Cloud API (Meta)
    whatsapp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    whatsapp_phone_number_id: Mapped[str] = mapped_column(String(64), default="")  # legacy Meta
    whatsapp_display_number: Mapped[str] = mapped_column(String(32), default="")
    whatsapp_access_token: Mapped[str] = mapped_column(String(500), default="")  # legacy Meta
    whatsapp_recipients: Mapped[str] = mapped_column(String(2000), default="")
    whatsapp_owner_scope: Mapped[str] = mapped_column(String(32), default="inhouse")
    whatsapp_template_name: Mapped[str] = mapped_column(String(128), default="")
    whatsapp_template_lang: Mapped[str] = mapped_column(String(16), default="en")
    plivo_auth_id: Mapped[str] = mapped_column(String(64), default="")
    plivo_auth_token: Mapped[str] = mapped_column(String(255), default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class NotificationLog(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    website_id: Mapped[int | None] = mapped_column(Integer)
    incident_id: Mapped[int | None] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(50))
    subject: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    sent_to: Mapped[str] = mapped_column(String(2000))
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

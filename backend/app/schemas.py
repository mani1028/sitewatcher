from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.email_service import normalize_alert_emails


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class WebsiteCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    url: str = Field(min_length=5, max_length=500)
    health_url: str | None = Field(default=None, max_length=500)
    category: Literal["portal", "website", "microservice", "other"] = "website"
    owner: Literal["inhouse", "client"] = "inhouse"
    check_interval: Literal[60, 300, 600, 3600, 86400] = 60
    timeout: int = Field(default=10, ge=3, le=60)
    expected_status: int = Field(default=200, ge=100, le=599)
    monitor_ssl: bool = True


class WebsiteUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    url: str | None = Field(default=None, min_length=5, max_length=500)
    health_url: str | None = Field(default=None, max_length=500)
    category: Literal["portal", "website", "microservice", "other"] | None = None
    owner: Literal["inhouse", "client"] | None = None
    enabled: bool | None = None
    check_interval: Literal[60, 300, 600, 3600, 86400] | None = None
    timeout: int | None = Field(default=None, ge=3, le=60)
    expected_status: int | None = Field(default=None, ge=100, le=599)
    monitor_ssl: bool | None = None
    maintenance_mode: bool | None = None


class WebsiteOut(BaseModel):
    id: int
    name: str
    url: str
    health_url: str | None = None
    category: str = "website"
    owner: str = "inhouse"
    enabled: bool
    check_interval: int
    timeout: int
    expected_status: int
    monitor_ssl: bool
    maintenance_mode: bool
    status: str
    consecutive_failures: int
    consecutive_successes: int
    last_checked_at: datetime | None
    last_response_time: float | None
    last_status_code: int | None
    last_error: str | None
    next_check_at: datetime | None
    ssl_expires_at: datetime | None
    uptime_percent: float
    created_at: datetime

    model_config = {"from_attributes": True}


class CheckOut(BaseModel):
    id: int
    website_id: int
    status: str
    status_code: int | None
    response_time: float | None
    error_type: str | None
    error_message: str | None
    checked_at: datetime

    model_config = {"from_attributes": True}


class IncidentOut(BaseModel):
    id: int
    website_id: int
    website_name: str | None = None
    website_url: str | None = None
    started_at: datetime
    resolved_at: datetime | None
    duration_seconds: int | None
    reason: str
    status: str

    model_config = {"from_attributes": True}


class SettingsOut(BaseModel):
    email: EmailStr
    alert_email: str
    notification_enabled: bool
    slow_threshold_ms: int
    failure_threshold: int
    recovery_threshold: int
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_from: str
    smtp_use_tls: bool
    smtp_configured: bool


class SettingsUpdate(BaseModel):
    alert_email: str | None = None
    notification_enabled: bool | None = None
    slow_threshold_ms: int | None = Field(default=None, ge=200, le=30000)
    failure_threshold: int | None = Field(default=None, ge=1, le=10)
    recovery_threshold: int | None = Field(default=None, ge=1, le=10)
    smtp_host: str | None = None
    smtp_port: int | None = Field(default=None, ge=1, le=65535)
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    smtp_use_tls: bool | None = None
    password: str | None = Field(default=None, min_length=6)

    @field_validator("alert_email")
    @classmethod
    def validate_alert_emails(cls, value: str | None) -> str | None:
        if value is None:
            return value
        emails = normalize_alert_emails(value)
        if not emails:
            raise ValueError("Enter at least one valid alert email")
        if len(emails) > 20:
            raise ValueError("Maximum 20 alert emails")
        return ", ".join(emails)


class DashboardOut(BaseModel):
    total: int
    up: int
    down: int
    slow: int
    maintenance: int
    overall_uptime: float
    websites: list[WebsiteOut]
    recent_incidents: list[IncidentOut]


class NotificationOut(BaseModel):
    id: int
    website_id: int | None
    incident_id: int | None
    kind: str
    subject: str
    sent_to: str
    success: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationPage(BaseModel):
    items: list[NotificationOut]
    total: int
    page: int
    limit: int
    pages: int


class TestEmailRequest(BaseModel):
    to: str | None = None

    @field_validator("to")
    @classmethod
    def validate_to(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        emails = normalize_alert_emails(value)
        if not emails:
            raise ValueError("Enter at least one valid email")
        return ", ".join(emails)

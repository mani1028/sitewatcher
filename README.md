**Live:** https://sitewatch.ai4bzr.com

# SiteWatch

Lightweight multi-project website monitoring with domain-mail alerts.

Add as many projects as you want (JobNeedX, staging, APIs, landing pages). SiteWatch checks them on a schedule, tracks UP / DOWN / SLOW, opens incidents, and emails you via SMTP when a site goes down or recovers.

## Stack

- **Frontend** — Next.js + TypeScript + Tailwind
- **Backend** — FastAPI + async monitoring worker
- **Database** — PostgreSQL
- **Cache / locks** — Redis
- **Email** — Domain SMTP (mail.yourdomain.com)

## Quick start

```bash
cp .env.example .env
# Edit SMTP settings in .env for real alerts

docker compose up --build
```

- App: http://localhost:3000
- API docs: http://localhost:8000/docs
- Login: `admin@sitewatch.app` / `admin123`

## Domain mail alerts

In **Settings** (or `.env`), set your SMTP **sender** (e.g. Gmail):

```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=SiteWatch <your@gmail.com>
ALERT_EMAIL=you@yourdomain.com, teammate@yourdomain.com
```

Use **587 + encryption** (STARTTLS); if it fails, **465** SSL is tried automatically. List multiple alert emails separated by commas — everyone gets the same down/recovery alerts. Then click **Send test email**.

## What you can do

1. Sign in
2. **Add site** for each project URL
3. Configure SMTP once
4. Watch the dashboard — it refreshes every 20s
5. Open a site for response-time charts, checks, and incidents

## Design rules baked in

- One async worker (max 20 concurrent checks)
- Default check interval: 1 minute
- 3 failures → DOWN, 2 successes → recovered
- One down email + one recovery email per incident
- Raw checks retained 7 days
- SSL checked about every 12 hours
- No microservices / WebSockets in v1

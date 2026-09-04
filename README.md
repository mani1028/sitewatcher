# SiteWatch

Lightweight multi-site uptime monitor. Checks your URLs on a schedule, tracks **UP / DOWN / SLOW**, opens incidents, and emails your team on down and recovery.

**Live:** https://sitewatch.ai4bzr.com

## Stack

| Layer | Use |
|--------|-----|
| Frontend | Next.js + TypeScript + Tailwind |
| Backend | FastAPI + async monitor worker |
| Database | PostgreSQL |
| Cache | Redis |
| Email | Any SMTP (Gmail app password, domain mail, etc.) |

## What to use (local)

```bash
cp .env.example .env
# Edit ADMIN_EMAIL / ADMIN_PASSWORD (and optional defaults)
docker compose up --build
```

| URL | Purpose |
|-----|---------|
| http://localhost:3000 | App |
| http://localhost:8000/docs | API docs |

Login uses `ADMIN_EMAIL` / `ADMIN_PASSWORD` from `.env`.

### Env files — what to use

| File | Use |
|------|-----|
| `.env.example` | Template for local `.env` |
| `.env` | Local secrets (**gitignored** — never commit) |
| `.env.production.example` | Template for production |
| `.env.production` | Server secrets (**gitignored**) |
| `.deploy.env` | SSH deploy host/user/password (**gitignored**) |

## What to update (Settings page)

Configure mail and recipients in the UI after login (preferred over env for day-to-day use).

### Notifications (recipients)

| Field | What to put |
|--------|-------------|
| **Alert emails** | One address per row — who should get down/recovery mail |
| **Enable email notifications** | On |

### SMTP sender (who sends)

| Field | Example (Gmail) |
|--------|------------------|
| **SMTP host** | `smtp.gmail.com` |
| **Port** | `587` (falls back to `465` SSL if needed) |
| **Username** | your Gmail address |
| **Password** | [Google App Password](https://myaccount.google.com/apppasswords) (16 chars, no spaces) |
| **From** | same as username or `SiteWatch <you@gmail.com>` |
| **Use encryption** | On |

Then **Save settings** → **Send test email**.

### Monitoring thresholds

| Field | Typical value |
|--------|----------------|
| Slow (ms) | `2000` |
| Failures → DOWN | `3` |
| Successes → UP | `2` |

## Daily use

1. Sign in  
2. **Add site** for each URL (prod, staging, APIs, …)  
3. Configure SMTP + alert emails once in Settings  
4. Dashboard auto-refreshes every 20s  
5. Open a site for response-time chart, recent checks, and incidents  

When a site fails the threshold: status → **DOWN**, one incident opens, one email to all recipients. On recovery: one recovery email.

## Production deploy

Requires local `.deploy.env` and server `.env.production` (not in git). See [deploy/README.md](deploy/README.md).

```bash
# From repo root, with .deploy.env present:
export $(grep -v '^#' .deploy.env | xargs)
rsync -az --delete \
  --exclude .venv --exclude node_modules --exclude .next --exclude .git \
  --exclude .env --exclude .deploy.env \
  -e "sshpass -e ssh -o PreferredAuthentications=password -o PubkeyAuthentication=no" \
  ./ $DEPLOY_USER@$DEPLOY_HOST:$DEPLOY_PATH/
sshpass -e ssh -o PreferredAuthentications=password -o PubkeyAuthentication=no $DEPLOY_USER@$DEPLOY_HOST \
  "cd $DEPLOY_PATH && docker compose -f docker-compose.prod.yml --env-file .env.production up --build -d"
```

Compose reads `POSTGRES_PASSWORD` and `FRONTEND_URL` from `.env.production`.

## Design defaults

- Max 20 concurrent checks  
- Default interval: 1 minute  
- 3 failures → DOWN, 2 successes → recovered  
- One down email + one recovery email per incident  
- Raw checks kept 7 days  
- SSL checked ~every 12 hours  

## Security

Do **not** commit:

- `.env`, `.env.production`, `.deploy.env`
- Real SMTP passwords, DB passwords, or SSH credentials

Use the `*.example` files as templates only.

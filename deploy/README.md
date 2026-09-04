# SiteWatch production deploy

**Live URL:** https://sitewatch.ai4bzr.com  
**Server path:** `/opt/visys/sitewatch`  
Credentials live in `.deploy.env` and `.env.production` on the server (not in git).

## Stack

Docker Compose (`docker-compose.prod.yml`):
- frontend → `127.0.0.1:13000`
- backend → `127.0.0.1:18080`
- postgres + redis (internal)

Nginx (`sitewatch.ai4bzr.com`) proxies `/` and `/api/` on port 80. Cloudflare Flexible SSL terminates HTTPS.

## Redeploy

From this repo (requires local `.deploy.env` — gitignored):

```bash
export $(grep -v "^#" .deploy.env | xargs)
rsync -az --delete --exclude .venv --exclude node_modules --exclude .next --exclude .git \
  --exclude .env --exclude .deploy.env \
  -e "sshpass -e ssh -o PreferredAuthentications=password -o PubkeyAuthentication=no" \
  ./ $DEPLOY_USER@$DEPLOY_HOST:$DEPLOY_PATH/
sshpass -e ssh -o PreferredAuthentications=password -o PubkeyAuthentication=no $DEPLOY_USER@$DEPLOY_HOST \
  "cd $DEPLOY_PATH && docker compose -f docker-compose.prod.yml --env-file .env.production up --build -d"
```

## Notes

- Production DNS is on **ai4bzr.com**.
- Configure SMTP in Settings after login for email alerts.
- Never commit `.env`, `.env.production`, or `.deploy.env`.

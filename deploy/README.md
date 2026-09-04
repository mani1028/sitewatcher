# SiteWatch production deploy

**Live URL:** https://sitewatch.ai4bzr.com  
**Server:** 95.217.40.106 (`/opt/visys/sitewatch`)  
**Login:** `admin@visyscloudtech.com` / `Admin@321`

## Stack

Docker Compose (`docker-compose.prod.yml`):
- frontend → `127.0.0.1:13000`
- backend → `127.0.0.1:18080`
- postgres + redis (internal)

Nginx (`sitewatch.ai4bzr.com`) proxies `/` and `/api/` on port 80. Cloudflare Flexible SSL terminates HTTPS.

## Redeploy

From this repo (requires `.deploy.env`):

```bash
export $(grep -v "^#" .deploy.env | xargs)
rsync -az --delete --exclude .venv --exclude node_modules --exclude .next --exclude .git   -e "sshpass -e ssh -o PreferredAuthentications=password -o PubkeyAuthentication=no"   ./ $DEPLOY_USER@$DEPLOY_HOST:$DEPLOY_PATH/
sshpass -e ssh -o PreferredAuthentications=password -o PubkeyAuthentication=no $DEPLOY_USER@$DEPLOY_HOST   "cd $DEPLOY_PATH && docker compose -f docker-compose.prod.yml up --build -d"
```

## Notes

- `aibzr.com` is not in the Cloudflare account used for DNS automation; production DNS is on **ai4bzr.com**.
- Configure SMTP in Settings after login for domain-mail alerts.

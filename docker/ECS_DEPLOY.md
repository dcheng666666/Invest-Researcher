# Alibaba Cloud ECS — production runbook

This stack uses [docker-compose.prod.yml](../docker-compose.prod.yml): **Nginx** (port 80, static UI + `/api` proxy) and **FastAPI** (internal port 8000 only). SQLite and disk cache live in Docker **named volumes** (`app_data`, `app_cache`).

## 1. ECS instance

- **Image**: Alibaba Cloud Linux 3 or Ubuntu 22.04 LTS (x86_64).
- **Size**: Start with 2 vCPU / 4 GiB RAM; scale from CloudMonitor.
- **Disk**: 40 GiB+ system disk is a reasonable default.

## 2. Network and security

- Bind an **EIP** and point your domain **A record** to the EIP.
- **Security group** inbound:
  - **22/tcp** — SSH (restrict source to your IP or a bastion).
  - **80/tcp** — HTTP (Nginx). Add **443/tcp** if you terminate TLS on the instance.
- Do **not** expose **8000** to the public internet.

## 3. Install Docker

On Alibaba Cloud Linux 3, follow the official Docker CE install guide for that distribution. On Ubuntu, install `docker.io` (or Docker’s official repo) and ensure the `docker` group exists.

Install **Docker Compose v2** (plugin: `docker compose`) or standalone `docker-compose`. The commands below use `docker-compose`; if your host has the plugin, use `docker compose` instead.

## 4. Deploy application

```bash
sudo mkdir -p /opt/invest-reasearcher && cd /opt/invest-reasearcher
sudo git clone <YOUR_REPO_URL> .
sudo cp .env.example .env
sudo nano .env   # set LLM keys, APP_SESSION_SECRET (>=16 chars), etc.
sudo chmod 600 .env
sudo docker-compose -f docker-compose.prod.yml up -d --build
```

Verify:

```bash
curl -sS -o /dev/null -w "%{http_code}\n" http://127.0.0.1/
curl -sS -o /dev/null -w "%{http_code}\n" http://127.0.0.1/api/search?q=茅台
```

Open `http://<EIP-or-domain>/` in a browser.

## 5. HTTPS options

- **ALB (recommended for scaling)**: Create an Application Load Balancer with an HTTPS listener and a managed certificate; forward to the ECS instance:80. You can keep the app on HTTP between ALB and ECS.
- **On the ECS host**: Install Certbot with the Nginx plugin **or** mount certificates into a custom Nginx image and publish **443:443** (requires extending [Dockerfile.frontend.prod](Dockerfile.frontend.prod) and Nginx config for `listen 443 ssl`).

Same-origin `/api` via Nginx avoids cross-origin issues; you only need `CORS_ORIGINS` for a **split** frontend/API domain layout.

## 6. Updates and image registry

On the instance:

```bash
cd /opt/invest-reasearcher && sudo git pull
sudo docker-compose -f docker-compose.prod.yml up -d --build
```

For **ACR**: build and push images on CI or a build machine, then on ECS use `image:` tags in a small override file and `docker compose pull && docker compose up -d` (no `--build` on ECS).

## 7. Backups

Persistent data is in named volumes mounted at `/app/data` and `/app/.cache` in the backend container.

Example backup of the SQLite DB (run when the stack is stopped or copy from a consistent snapshot):

```bash
sudo docker-compose -f docker-compose.prod.yml exec backend sh -c 'test -f /app/data/stock_symbols.db && ls -la /app/data/stock_symbols.db'
```

For a cold copy, stop the stack, use `docker run --rm -v invest-reasearcher_app_data:/data -v $(pwd):/backup alpine tar cvf /backup/app_data_backup.tar /data`, then start again.

## 8. Logs

```bash
sudo docker-compose -f docker-compose.prod.yml logs -f nginx
sudo docker-compose -f docker-compose.prod.yml logs -f backend
```

## 9. Outbound access

The backend needs outbound HTTPS to market data providers and your configured LLM API. If the VPC uses a corporate proxy, configure proxy environment variables on the `backend` service as required by your network policy.

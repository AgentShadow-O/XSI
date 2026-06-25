# XSI Cloud Controller Deployment

This deployment targets an Oracle Cloud Free Tier Ubuntu VM.

## Architecture

Vercel SIEM frontend connects over HTTPS and WebSocket to this cloud controller. Desktop and mobile agents connect outbound only, so endpoint networks do not need port forwarding.

## Required Environment

- `DATABASE_URL=postgresql://xsi:xsi-password@postgres:5432/xsi`
- `REDIS_URL=redis://redis:6379/0`
- `JWT_SECRET=<long random secret>`
- `API_KEY=<long random dashboard/mobile api key>`
- `XSI_AGENT_TOKEN=<long random agent enrollment token>`
- `CORS_ORIGINS=https://your-vercel-app.vercel.app`
- `PORT=8000`

## Install

```bash
chmod +x deployment/install.sh
./deployment/install.sh
```

## Production Notes

- Replace all default secrets before exposing the VM.
- Put the VM behind a real DNS name.
- Add TLS certificates to `deployment/certbot/conf` or use your preferred ACME flow.
- The controller runs headless; Windows tray code is not used in cloud mode.
- The frontend should be deployed separately to Vercel with:
  - `VITE_API_URL=https://your-controller-domain`
  - `VITE_WS_URL=wss://your-controller-domain/ws`

## Render Backend

- Root directory: repository root.
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn backend.main:app -k uvicorn.workers.UvicornWorker --workers 2 --bind 0.0.0.0:$PORT`
- Set `ENVIRONMENT=production`, `DATABASE_URL`, `SECRET_KEY`, `API_KEY`, `XSI_AGENT_TOKEN`, `FRONTEND_URL`, `CORS_ORIGINS`, `API_BASE_URL`, and `LOG_LEVEL`.

## Vercel Frontend

- Root directory: `frontend`.
- Build command: `npm run build`.
- Output directory: `dist`.
- Set `VITE_API_URL` to the Render backend URL. `VITE_WS_URL` is optional and is derived from `VITE_API_URL` when omitted.

## Health Checks

```bash
curl https://your-controller-domain/api/health
docker compose -f deployment/docker-compose.yml logs -f controller
```

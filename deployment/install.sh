#!/usr/bin/env bash
set -euo pipefail

if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
fi

if ! docker compose version >/dev/null 2>&1; then
  sudo apt-get update
  sudo apt-get install -y docker-compose-plugin
fi

sudo usermod -aG docker "$USER" || true
mkdir -p deployment/certbot/www deployment/certbot/conf
docker compose -f deployment/docker-compose.yml up -d --build

echo "XSI controller is starting on ports 80/443 and direct port 8000."
echo "Set strong JWT_SECRET, API_KEY, XSI_AGENT_TOKEN, database password, and CORS_ORIGINS before production use."

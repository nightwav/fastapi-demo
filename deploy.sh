#!/bin/bash

set -e

PROJECT_DIR="/opt/fastapi-demo"

cd "$PROJECT_DIR"

echo "[$(date '+%F %T')] Checking compose config..."
docker compose config >/dev/null

echo "[$(date '+%F %T')] Building and starting services..."
docker compose up -d --build

echo "[$(date '+%F %T')] Waiting for service..."
sleep 5

echo "[$(date '+%F %T')] Compose status:"
docker compose ps

echo "[$(date '+%F %T')] Health check:"
curl -f http://localhost/api/health

echo
echo "[$(date '+%F %T')] Deploy completed."

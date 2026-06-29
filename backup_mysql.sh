#!/bin/bash

set -e

PROJECT_DIR="/home/meng/docker-lab/fastapi"
BACKUP_DIR="${PROJECT_DIR}/backups"
DATE=$(date +"%Y%m%d_%H%M%S")
FILE_NAME="appdb_${DATE}.sql"

mkdir -p "$BACKUP_DIR"

docker compose exec -T mysql mysqldump \
  --no-tablespaces \
  -uappuser \
  -papppass \
  appdb > "${BACKUP_DIR}/${FILE_NAME}"

echo "MySQL backup created: ${BACKUP_DIR}/${FILE_NAME}"

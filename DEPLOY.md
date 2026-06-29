# FastAPI + Nginx + MySQL + Redis 单机生产环境部署脚本文档

## 一、目录规划

生产目录统一放在：

```bash
/opt/fastapi-demo
```

项目来源：

```bash
https://github.com/nightwav/fastapi-demo.git
```

服务结构：

```text
外部浏览器 / 局域网用户
        ↓
Nginx :80
        ↓
FastAPI :8000
        ↓
MySQL :3306
Redis :6379
```

初期 MySQL 和 Redis 允许局域网访问，方便 Navicat、Redis 客户端调试。后期上线稳定后，可以关闭它们的对外端口，只允许容器内部访问。

---

# 二、服务器基础准备

## 1. 安装基础工具

```bash
sudo apt update
sudo apt install -y git curl vim nano ufw
```

## 2. 确认 Docker 可用

```bash
docker --version
docker compose version
```

如果 Docker 没有开机自启：

```bash
sudo systemctl enable --now docker
```

---

# 三、克隆 GitHub 仓库

## 1. 创建生产目录

```bash
sudo mkdir -p /opt
sudo chown -R $USER:$USER /opt
```

## 2. 克隆项目

```bash
cd /opt
git clone https://github.com/nightwav/fastapi-demo.git
cd /opt/fastapi-demo
```

## 3. 确认文件

```bash
ls -la
```

至少应包含：

```text
main.py
Dockerfile
requirements.txt
compose.yaml
nginx/
deploy.sh
backup_mysql.sh
.env.example
.gitignore
```

---

# 四、创建生产 .env 配置

`.env` 不上传 GitHub，只在服务器本地保存。

```bash
cd /opt/fastapi-demo
cp .env.example .env
nano .env
```

写入示例：

```env
# MySQL
MYSQL_ROOT_PASSWORD=RootPass_ChangeMe_123
MYSQL_DATABASE=appdb
MYSQL_USER=appuser
MYSQL_PASSWORD=AppPass_ChangeMe_123

# Redis
REDIS_PASSWORD=RedisPass_ChangeMe_123
REDIS_PORT=6379

# API / Nginx
API_PORT=8000
NGINX_PORT=80

# 局域网访问绑定 IP
# 按实际服务器 IP 修改
LAN_IP=192.168.0.40

# MySQL / Redis 局域网调试端口
MYSQL_HOST_PORT=3306
REDIS_HOST_PORT=6379
```

保护 `.env` 权限：

```bash
chmod 600 .env
```

---

# 五、compose.yaml：MySQL / Redis 局域网可访问版本

覆盖 `compose.yaml`：

```bash
cd /opt/fastapi-demo

cat > compose.yaml <<'EOF'
services:
  nginx:
    image: nginx:alpine
    container_name: nginx-gateway
    restart: unless-stopped
    ports:
      - "${NGINX_PORT}:80"
    volumes:
      - ./nginx/conf.d:/etc/nginx/conf.d:ro
      - ./logs/nginx:/var/log/nginx
    depends_on:
      api:
        condition: service_healthy
    logging:
      driver: json-file
      options:
        max-size: "20m"
        max-file: "5"

  api:
    build: .
    image: fastapi-demo:prod
    container_name: fastapi-api
    restart: unless-stopped
    expose:
      - "${API_PORT}"
    environment:
      MYSQL_HOST: mysql
      MYSQL_PORT: 3306
      MYSQL_DATABASE: ${MYSQL_DATABASE}
      MYSQL_USER: ${MYSQL_USER}
      MYSQL_PASSWORD: ${MYSQL_PASSWORD}
      REDIS_HOST: redis
      REDIS_PORT: ${REDIS_PORT}
      REDIS_PASSWORD: ${REDIS_PASSWORD}
    depends_on:
      mysql:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 20s
    logging:
      driver: json-file
      options:
        max-size: "20m"
        max-file: "5"

  mysql:
    image: mysql:8.4
    container_name: mysql-prod
    restart: unless-stopped
    ports:
      - "${LAN_IP}:${MYSQL_HOST_PORT}:3306"
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
      MYSQL_DATABASE: ${MYSQL_DATABASE}
      MYSQL_USER: ${MYSQL_USER}
      MYSQL_PASSWORD: ${MYSQL_PASSWORD}
    volumes:
      - mysql-data:/var/lib/mysql
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost", "-uroot", "-p${MYSQL_ROOT_PASSWORD}"]
      interval: 10s
      timeout: 5s
      retries: 10
    logging:
      driver: json-file
      options:
        max-size: "50m"
        max-file: "5"

  redis:
    image: redis:7-alpine
    container_name: redis-prod
    restart: unless-stopped
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD}
    ports:
      - "${LAN_IP}:${REDIS_HOST_PORT}:6379"
    volumes:
      - redis-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    logging:
      driver: json-file
      options:
        max-size: "20m"
        max-file: "5"

volumes:
  mysql-data:
  redis-data:
EOF
```

检查配置：

```bash
docker compose config
```

---

# 六、Nginx 配置

创建目录：

```bash
mkdir -p nginx/conf.d logs/nginx
```

写入 Nginx 配置：

```bash
cat > nginx/conf.d/default.conf <<'EOF'
server {
    listen 80;
    server_name _;

    client_max_body_size 20m;

    access_log /var/log/nginx/access.log;
    error_log /var/log/nginx/error.log warn;

    location /api/ {
        proxy_pass http://api:8000/;

        proxy_http_version 1.1;

        proxy_connect_timeout 5s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF
```

---

# 七、FastAPI main.py 示例

`main.py` 示例：

```python
import os

import pymysql
import redis
from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def root():
    return {
        "message": "Hello DevOps",
        "service": "fastapi",
    }


@app.get("/health")
def health():
    result = {
        "api": "ok",
        "mysql": "unknown",
        "redis": "unknown",
    }

    try:
        conn = pymysql.connect(
            host=os.getenv("MYSQL_HOST", "mysql"),
            port=int(os.getenv("MYSQL_PORT", "3306")),
            user=os.getenv("MYSQL_USER", "appuser"),
            password=os.getenv("MYSQL_PASSWORD", "apppass"),
            database=os.getenv("MYSQL_DATABASE", "appdb"),
            connect_timeout=3,
        )
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        conn.close()
        result["mysql"] = "ok"
    except Exception as exc:
        result["mysql"] = f"error: {exc}"

    try:
        r = redis.Redis(
            host=os.getenv("REDIS_HOST", "redis"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            password=os.getenv("REDIS_PASSWORD"),
            socket_connect_timeout=3,
        )
        r.ping()
        result["redis"] = "ok"
    except Exception as exc:
        result["redis"] = f"error: {exc}"

    return result
```

---

# 八、requirements.txt

```bash
cat > requirements.txt <<'EOF'
fastapi
uvicorn[standard]
pymysql
redis
EOF
```

---

# 九、Dockerfile

```bash
cat > Dockerfile <<'EOF'
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN python -m pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY main.py .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
EOF
```

---

# 十、deploy.sh 一键部署脚本

```bash
cat > deploy.sh <<'EOF'
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
EOF

chmod +x deploy.sh
```

执行部署：

```bash
./deploy.sh
```

检查：

```bash
docker compose ps
curl http://localhost/api/health
```

局域网访问：

```text
http://192.168.0.40/api/health
```

MySQL 局域网连接：

```text
主机：192.168.0.40
端口：3306
用户：appuser
密码：AppPass_ChangeMe_123
数据库：appdb
```

Redis 局域网连接：

```text
主机：192.168.0.40
端口：6379
密码：RedisPass_ChangeMe_123
```

---

# 十一、备份脚本 backup_mysql.sh

```bash
cat > backup_mysql.sh <<'EOF'
#!/bin/bash

set -e

PROJECT_DIR="/opt/fastapi-demo"
BACKUP_DIR="${PROJECT_DIR}/backups/mysql"
DATE=$(date +"%Y%m%d_%H%M%S")

cd "$PROJECT_DIR"

set -a
source .env
set +a

mkdir -p "$BACKUP_DIR"

FILE_NAME="${MYSQL_DATABASE}_${DATE}.sql.gz"

docker compose exec -T mysql mysqldump \
  --no-tablespaces \
  -u"${MYSQL_USER}" \
  -p"${MYSQL_PASSWORD}" \
  "${MYSQL_DATABASE}" | gzip > "${BACKUP_DIR}/${FILE_NAME}"

echo "MySQL backup created: ${BACKUP_DIR}/${FILE_NAME}"

find "$BACKUP_DIR" -type f -name "*.sql.gz" -mtime +7 -delete
EOF

chmod +x backup_mysql.sh
```

测试备份：

```bash
./backup_mysql.sh
ls -lh backups/mysql
```

---

# 十二、定时备份

编辑 crontab：

```bash
crontab -e
```

加入：

```cron
0 2 * * * /opt/fastapi-demo/backup_mysql.sh >> /opt/fastapi-demo/backups/mysql/backup.log 2>&1
```

查看定时任务：

```bash
crontab -l
```

查看备份日志：

```bash
tail -n 50 /opt/fastapi-demo/backups/mysql/backup.log
```

---

# 十三、防火墙配置

初期允许 SSH、Nginx、MySQL、Redis：

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow from 192.168.0.0/24 to any port 3306 proto tcp
sudo ufw allow from 192.168.0.0/24 to any port 6379 proto tcp
sudo ufw enable
sudo ufw status numbered
```

说明：

```text
80：Nginx 对外服务
3306：MySQL 局域网调试
6379：Redis 局域网调试
```

不建议把 3306 和 6379 暴露到公网。

---

# 十四、后期关闭 MySQL / Redis 局域网访问

上线稳定后，建议关闭 MySQL 和 Redis 的宿主机端口映射。

## 1. 修改 compose.yaml

把 MySQL 里的：

```yaml
    ports:
      - "${LAN_IP}:${MYSQL_HOST_PORT}:3306"
```

删除或注释掉。

把 Redis 里的：

```yaml
    ports:
      - "${LAN_IP}:${REDIS_HOST_PORT}:6379"
```

删除或注释掉。

关闭后 MySQL / Redis 仍然可以被 FastAPI 容器通过服务名访问：

```text
mysql:3306
redis:6379
```

但局域网电脑不能再直接连 MySQL / Redis。

## 2. 重新部署

```bash
cd /opt/fastapi-demo
./deploy.sh
```

## 3. 删除防火墙规则

查看规则编号：

```bash
sudo ufw status numbered
```

删除 3306 / 6379 相关规则，例如：

```bash
sudo ufw delete 编号
```

重新查看：

```bash
sudo ufw status numbered
```

---

# 十五、GitHub 更新后的服务器部署流程

本地或其他机器修改代码后：

```bash
git add .
git commit -m "update app"
git push
```

服务器执行：

```bash
cd /opt/fastapi-demo
git pull
./deploy.sh
```

检查：

```bash
docker compose ps
curl http://localhost/api/health
```

---

# 十六、常用运维命令

查看容器：

```bash
docker compose ps
```

查看日志：

```bash
docker compose logs -f api
docker compose logs -f nginx
docker compose logs -f mysql
docker compose logs -f redis
```

重启 API：

```bash
docker compose up -d --build api
```

重启全部：

```bash
docker compose up -d --build
```

停止服务但保留数据：

```bash
docker compose down
```

危险操作，删除数据卷：

```bash
docker compose down -v
```

查看数据卷：

```bash
docker volume ls
```

查看磁盘：

```bash
df -h
du -sh /opt/fastapi-demo/*
```

查看端口：

```bash
ss -lntp
```

---

# 十七、当前部署检查清单

部署完成后确认：

```bash
cd /opt/fastapi-demo
docker compose ps
curl http://localhost/api/health
```

应该看到：

```json
{
  "api": "ok",
  "mysql": "ok",
  "redis": "ok"
}
```

容器状态应类似：

```text
nginx-gateway   Up
fastapi-api     Up healthy
mysql-prod      Up healthy
redis-prod      Up healthy
```

局域网浏览器访问：

```text
http://192.168.0.40/api/health
```

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
            socket_connect_timeout=3,
        )
        r.ping()
        result["redis"] = "ok"
    except Exception as exc:
        result["redis"] = f"error: {exc}"

    return result

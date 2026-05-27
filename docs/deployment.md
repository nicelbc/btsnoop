# 部署文档

## 1. 环境要求

### 1.1 运行环境

| 组件     | 最低要求                | 推荐配置              |
|----------|------------------------|-----------------------|
| OS       | Linux x86_64 / macOS  | Ubuntu 22.04 LTS     |
| CPU      | 2 核                   | 4 核                  |
| 内存     | 2 GB                   | 8 GB                  |
| 磁盘     | 1 GB                   | 10 GB (含临时文件)    |
| 网络     | -                      | 带宽 ≥ 10Mbps        |

### 1.2 依赖软件

| 软件       | 版本要求 | 用途             |
|------------|----------|------------------|
| Rust       | ≥ 1.75   | 后端编译         |
| Node.js    | ≥ 18 LTS | 前端构建         |
| Docker     | ≥ 24.0  | 容器化部署        |
| Nginx      | ≥ 1.24  | 反向代理 (可选)   |

## 2. 本地开发部署

### 2.1 后端启动

```bash
cd backend/
cp .env.example .env

# 编辑配置
vim .env

# 编译并运行
cargo run --release
```

`.env` 配置项：

```bash
# 服务端口
SERVER_HOST=0.0.0.0
SERVER_PORT=8080

# 会话配置
MAX_SESSIONS=100
SESSION_TIMEOUT_MINUTES=30
MAX_FILE_SIZE_MB=2048
MAX_PACKETS_PER_SESSION=5000000

# 日志级别
RUST_LOG=info

# CORS 允许源
CORS_ORIGINS=http://localhost:3000
```

### 2.2 前端启动

```bash
cd frontend/
npm install
npm run dev
# → http://localhost:3000
```

前端环境变量 (`.env.local`)：

```bash
VITE_API_BASE_URL=http://localhost:8080/api/v1
VITE_WS_URL=ws://localhost:8080/ws
```

## 3. Docker 部署

### 3.1 单容器部署（推荐）

```dockerfile
# Dockerfile
FROM rust:1.75 AS backend-builder
WORKDIR /app/backend
COPY backend/ .
RUN cargo build --release

FROM node:18 AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json .
RUN npm ci
COPY frontend/ .
RUN npm run build

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=backend-builder /app/backend/target/release/btsnoop-web .
COPY --from=frontend-builder /app/frontend/dist ./static/
EXPOSE 8080
CMD ["./btsnoop-web"]
```

### 3.2 构建与运行

```bash
# 构建镜像
docker build -t btsnoop-web:latest .

# 运行
docker run -d \
  --name btsnoop-web \
  -p 8080:8080 \
  -e MAX_SESSIONS=50 \
  -e SESSION_TIMEOUT_MINUTES=30 \
  --memory=4g \
  --cpus=2 \
  btsnoop-web:latest
```

### 3.3 Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  btsnoop-web:
    build: .
    ports:
      - "8080:8080"
    environment:
      - SERVER_HOST=0.0.0.0
      - SERVER_PORT=8080
      - MAX_SESSIONS=100
      - SESSION_TIMEOUT_MINUTES=30
      - MAX_FILE_SIZE_MB=2048
      - RUST_LOG=info
      - CORS_ORIGINS=*
    deploy:
      resources:
        limits:
          memory: 4G
          cpus: '2'
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 5s
      retries: 3
```

```bash
docker compose up -d
```

## 4. 生产环境部署

### 4.1 Nginx 反向代理配置

```nginx
upstream btsnoop_backend {
    server 127.0.0.1:8080;
}

server {
    listen 443 ssl http2;
    server_name btsnoop.example.com;

    ssl_certificate     /etc/ssl/certs/btsnoop.pem;
    ssl_certificate_key /etc/ssl/private/btsnoop.key;

    client_max_body_size 2G;

    # 前端静态文件
    location / {
        proxy_pass http://btsnoop_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # API
    location /api/ {
        proxy_pass http://btsnoop_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 300s;
    }

    # WebSocket
    location /ws/ {
        proxy_pass http://btsnoop_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }

    # 文件上传
    location /api/v1/session/ {
        proxy_pass http://btsnoop_backend;
        proxy_set_header Host $host;
        proxy_request_buffering off;    # 流式转发，不缓存整个文件
        proxy_read_timeout 600s;
    }
}
```

### 4.2 Systemd 服务文件

```ini
# /etc/systemd/system/btsnoop-web.service
[Unit]
Description=Btsnoop Online Parser
After=network.target

[Service]
Type=simple
User=btsnoop
Group=btsnoop
WorkingDirectory=/opt/btsnoop-web
ExecStart=/opt/btsnoop-web/btsnoop-web
Restart=always
RestartSec=5

Environment=SERVER_HOST=127.0.0.1
Environment=SERVER_PORT=8080
Environment=MAX_SESSIONS=100
Environment=SESSION_TIMEOUT_MINUTES=30
Environment=RUST_LOG=info

LimitNOFILE=65536
MemoryMax=4G

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable btsnoop-web
sudo systemctl start btsnoop-web
```

## 5. 监控与日志

### 5.1 健康检查端点

```
GET /health

Response:
{
  "status": "healthy",
  "uptime_seconds": 3600,
  "active_sessions": 5,
  "memory_usage_mb": 512
}
```

### 5.2 Metrics 端点 (Prometheus 格式)

```
GET /metrics

# HELP btsnoop_active_sessions Current active sessions
# TYPE btsnoop_active_sessions gauge
btsnoop_active_sessions 5

# HELP btsnoop_packets_parsed_total Total packets parsed
# TYPE btsnoop_packets_parsed_total counter
btsnoop_packets_parsed_total 1234567

# HELP btsnoop_parse_duration_seconds Packet parse duration
# TYPE btsnoop_parse_duration_seconds histogram
btsnoop_parse_duration_seconds_bucket{le="0.001"} 999000
```

### 5.3 日志格式

结构化 JSON 日志，方便 ELK/Loki 采集：

```json
{
  "timestamp": "2026-05-27T10:00:00.123Z",
  "level": "info",
  "target": "btsnoop_web::session",
  "message": "Session created",
  "session_id": "uuid",
  "mode": "file"
}
```

## 6. 安全加固

### 6.1 生产环境 Checklist

- [ ] 启用 HTTPS (TLS 1.2+)
- [ ] 设置 CORS 白名单（不用 `*`）
- [ ] 限制 `client_max_body_size`
- [ ] 启用 rate limiting
- [ ] 运行在非 root 用户下
- [ ] 设置内存上限 (MemoryMax / --memory)
- [ ] 日志不记录包内容原始数据
- [ ] 定期清理过期会话临时文件

### 6.2 Rate Limiting 配置

```nginx
# Nginx 层限流
limit_req_zone $binary_remote_addr zone=api:10m rate=30r/s;
limit_req_zone $binary_remote_addr zone=upload:10m rate=2r/s;

location /api/ {
    limit_req zone=api burst=50 nodelay;
}

location /api/v1/session/ {
    limit_req zone=upload burst=5 nodelay;
}
```

## 7. 升级与回滚

### 7.1 滚动升级 (Docker)

```bash
# 构建新版本
docker build -t btsnoop-web:v1.1.0 .

# 停止旧版本，启动新版本
docker compose down
docker compose up -d

# 验证
curl http://localhost:8080/health
```

### 7.2 回滚

```bash
# 切回旧镜像
docker compose down
docker tag btsnoop-web:v1.0.0 btsnoop-web:latest
docker compose up -d
```

## 8. 常见问题

| 问题                        | 解决方案                                |
|-----------------------------|-----------------------------------------|
| WebSocket 连接断开          | 检查 Nginx proxy_read_timeout 配置      |
| 大文件上传超时              | 增大 proxy_request_buffering off         |
| 内存占用过高                | 降低 MAX_PACKETS_PER_SESSION            |
| 会话创建失败                | 检查 MAX_SESSIONS 限制和当前活跃会话数  |
| CORS 错误                   | 检查 CORS_ORIGINS 配置和 Nginx headers  |

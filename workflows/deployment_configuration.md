# Deployment Configuration Reference

**Empire v7.2 Document Processing System**

Complete deployment configuration including Docker Compose, environment variables, production setup for Render.com/cloud providers, SSL/TLS, and scaling strategies.

---

## Table of Contents

1. [Docker Compose Configuration](#docker-compose-configuration)
2. [Environment Variables](#environment-variables)
3. [Local Development Setup](#local-development-setup)
4. [Production Deployment](#production-deployment)
5. [Cloud Provider Configurations](#cloud-provider-configurations)
6. [SSL/TLS Setup](#ssltls-setup)
7. [Scaling Configuration](#scaling-configuration)
8. [Backup and Recovery](#backup-and-recovery)

---

## Docker Compose Configuration

### Complete docker-compose.yml

```yaml
version: '3.8'

services:
  # FastAPI Application
  api:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: empire-api
    ports:
      - "8000:8000"
    environment:
      - ENVIRONMENT=${ENVIRONMENT:-development}
      - DATABASE_URL=${DATABASE_URL}
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_KEY=${SUPABASE_KEY}
      - SUPABASE_SERVICE_ROLE_KEY=${SUPABASE_SERVICE_ROLE_KEY}
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/1
      - OLLAMA_BASE_URL=http://ollama:11434
      - B2_APPLICATION_KEY_ID=${B2_APPLICATION_KEY_ID}
      - B2_APPLICATION_KEY=${B2_APPLICATION_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    volumes:
      - ./app:/app/app
      - ./logs:/app/logs
      - ./temp:/app/temp
    depends_on:
      - redis
      - ollama
    restart: unless-stopped
    networks:
      - empire-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  # Celery Worker
  celery-worker:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: empire-celery-worker
    command: celery -A app.celery_worker worker --loglevel=info --concurrency=4
    environment:
      - ENVIRONMENT=${ENVIRONMENT:-development}
      - DATABASE_URL=${DATABASE_URL}
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_KEY=${SUPABASE_KEY}
      - SUPABASE_SERVICE_ROLE_KEY=${SUPABASE_SERVICE_ROLE_KEY}
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/1
      - OLLAMA_BASE_URL=http://ollama:11434
      - B2_APPLICATION_KEY_ID=${B2_APPLICATION_KEY_ID}
      - B2_APPLICATION_KEY=${B2_APPLICATION_KEY}
    volumes:
      - ./app:/app/app
      - ./logs:/app/logs
      - ./temp:/app/temp
    depends_on:
      - redis
      - ollama
    restart: unless-stopped
    networks:
      - empire-network
    healthcheck:
      test: ["CMD", "celery", "-A", "app.celery_worker", "inspect", "ping"]
      interval: 60s
      timeout: 30s
      retries: 3

  # Celery Beat (Scheduled Tasks)
  celery-beat:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: empire-celery-beat
    command: celery -A app.celery_worker beat --loglevel=info
    environment:
      - ENVIRONMENT=${ENVIRONMENT:-development}
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/1
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_KEY=${SUPABASE_KEY}
    volumes:
      - ./app:/app/app
      - ./logs:/app/logs
    depends_on:
      - redis
    restart: unless-stopped
    networks:
      - empire-network

  # Redis
  redis:
    image: redis:7-alpine
    container_name: empire-redis
    ports:
      - "6379:6379"
    command: redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru
    volumes:
      - redis-data:/data
    restart: unless-stopped
    networks:
      - empire-network
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Ollama
  ollama:
    image: ollama/ollama:latest
    container_name: empire-ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama-data:/root/.ollama
    restart: unless-stopped
    networks:
      - empire-network
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:11434/api/tags"]
      interval: 60s
      timeout: 30s
      retries: 3

  # Prometheus (Monitoring)
  prometheus:
    image: prom/prometheus:latest
    container_name: empire-prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus-data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=30d'
    restart: unless-stopped
    networks:
      - empire-network

  # Grafana (Dashboards)
  grafana:
    image: grafana/grafana:latest
    container_name: empire-grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_USER=${GRAFANA_ADMIN_USER:-admin}
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD:-admin}
      - GF_INSTALL_PLUGINS=redis-datasource
    volumes:
      - grafana-data:/var/lib/grafana
      - ./grafana/dashboards:/etc/grafana/provisioning/dashboards
      - ./grafana/datasources:/etc/grafana/provisioning/datasources
    restart: unless-stopped
    networks:
      - empire-network
    depends_on:
      - prometheus

  # Nginx (Reverse Proxy)
  nginx:
    image: nginx:alpine
    container_name: empire-nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
      - ./static:/usr/share/nginx/html/static:ro
    depends_on:
      - api
    restart: unless-stopped
    networks:
      - empire-network

volumes:
  redis-data:
  ollama-data:
  prometheus-data:
  grafana-data:

networks:
  empire-network:
    driver: bridge
```

### Dockerfile

```dockerfile
# Multi-stage build for production
FROM python:3.11-slim as builder

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local

# Copy application code
COPY ./app /app/app
COPY ./alembic /app/alembic
COPY alembic.ini /app/

# Create necessary directories
RUN mkdir -p /app/logs /app/temp

# Make sure scripts are executable
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONPATH=/app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Run application
CMD ["uvicorn", "app.main:app", "--host", "0.0", "--port", "8000"]
```

### .dockerignore

```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
.venv/
ENV/
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# Testing
.pytest_cache/
.coverage
htmlcov/
.tox/

# Logs
logs/
*.log

# Temp files
temp/
tmp/
*.tmp

# Environment
.env
.env.local
.env.*.local

# Git
.git/
.gitignore

# Documentation
docs/
*.md
!README.md

# Docker
docker-compose*.yml
Dockerfile*
.dockerignore
```

---

## Environment Variables

### .env.example (Development)

```bash
# ============================================
# ENVIRONMENT
# ============================================
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=INFO

# ============================================
# APPLICATION
# ============================================
APP_NAME=Empire Document Processing
APP_VERSION=7.2.0
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=http://localhost:3000,http://localhost:8000

# ============================================
# SUPABASE (PostgreSQL + Storage)
# ============================================
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
DATABASE_URL=postgresql://postgres:password@db.your-project.supabase.co:5432/postgres

# ============================================
# REDIS
# ============================================
REDIS_URL=redis://localhost:6379/0
REDIS_MAX_CONNECTIONS=50
REDIS_SOCKET_TIMEOUT=5

# ============================================
# CELERY
# ============================================
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
CELERY_TASK_TRACK_STARTED=true
CELERY_TASK_TIME_LIMIT=3600

# ============================================
# BACKBLAZE B2
# ============================================
B2_APPLICATION_KEY_ID=your-key-id
B2_APPLICATION_KEY=your-application-key
B2_BUCKET_NAME=empire-documents
B2_BUCKET_ID=your-bucket-id

# ============================================
# OLLAMA (Local Embeddings)
# ============================================
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBEDDING_MODEL=bge-m3
OLLAMA_EMBEDDING_DIMENSION=1024
OLLAMA_TIMEOUT=60

# ============================================
# OPENAI (Fallback Embeddings)
# ============================================
OPENAI_API_KEY=sk-your-key
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_EMBEDDING_DIMENSION=1536

# ============================================
# ANTHROPIC CLAUDE
# ============================================
ANTHROPIC_API_KEY=sk-ant-your-key
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
ANTHROPIC_MAX_TOKENS=4096
ANTHROPIC_TEMPERATURE=0.7

# ============================================
# COHERE (Reranking)
# ============================================
COHERE_API_KEY=your-cohere-key
COHERE_RERANK_MODEL=rerank-english-v3.0
COHERE_RERANK_TOP_N=10

# ============================================
# CREWAI
# ============================================
CREWAI_VERBOSE=true
CREWAI_MEMORY=true
CREWAI_CACHE=true
CREWAI_MAX_ITERATIONS=20

# ============================================
# FILE PROCESSING
# ============================================
MAX_FILE_SIZE_MB=50
ALLOWED_FILE_TYPES=.pdf,.docx,.doc,.txt,.md,.xlsx,.xls,.csv
TEMP_FILE_DIR=/app/temp
CHUNK_SIZE=500
CHUNK_OVERLAP=50

# ============================================
# SEARCH & RAG
# ============================================
VECTOR_SEARCH_LIMIT=20
BM25_SEARCH_LIMIT=20
RERANK_TOP_K=10
SEARCH_CACHE_TTL=3600

# ============================================
# MONITORING
# ============================================
PROMETHEUS_PORT=9090
PROMETHEUS_METRICS_PATH=/metrics
HEALTH_CHECK_PATH=/health

# ============================================
# ADMIN
# ============================================
ADMIN_USERNAME=admin
ADMIN_PASSWORD=changeme
ADMIN_JWT_SECRET=your-super-secret-jwt-key
ADMIN_JWT_ALGORITHM=HS256
ADMIN_JWT_EXPIRATION=3600

# ============================================
# RATE LIMITING
# ============================================
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_PER_HOUR=1000

# ============================================
# SECURITY
# ============================================
SECRET_KEY=your-secret-key-change-in-production
ALLOWED_HOSTS=localhost,127.0.0.1
TRUSTED_PROXIES=127.0.0.1

# ============================================
# GRAFANA
# ============================================
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=admin
```

### .env.production (Production Template)

```bash
# ============================================
# ENVIRONMENT
# ============================================
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=WARNING

# ============================================
# APPLICATION
# ============================================
APP_NAME=Empire Document Processing
APP_VERSION=7.2.0
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=https://yourdomain.com,https://api.yourdomain.com

# ============================================
# SUPABASE (Use Production Instance)
# ============================================
SUPABASE_URL=https://prod-project.supabase.co
SUPABASE_KEY=${SUPABASE_KEY_SECRET}
SUPABASE_SERVICE_ROLE_KEY=${SUPABASE_SERVICE_ROLE_SECRET}
DATABASE_URL=${DATABASE_URL_SECRET}

# ============================================
# REDIS (Use Managed Redis)
# ============================================
REDIS_URL=${REDIS_URL_SECRET}
REDIS_MAX_CONNECTIONS=100
REDIS_SOCKET_TIMEOUT=5

# ============================================
# CELERY
# ============================================
CELERY_BROKER_URL=${REDIS_URL_SECRET}
CELERY_RESULT_BACKEND=${REDIS_URL_SECRET}
CELERY_TASK_TRACK_STARTED=true
CELERY_TASK_TIME_LIMIT=3600

# ============================================
# BACKBLAZE B2
# ============================================
B2_APPLICATION_KEY_ID=${B2_KEY_ID_SECRET}
B2_APPLICATION_KEY=${B2_KEY_SECRET}
B2_BUCKET_NAME=empire-documents-prod
B2_BUCKET_ID=${B2_BUCKET_ID_SECRET}

# ============================================
# OLLAMA (Production Server)
# ============================================
OLLAMA_BASE_URL=https://ollama.yourdomain.com
OLLAMA_EMBEDDING_MODEL=bge-m3
OLLAMA_EMBEDDING_DIMENSION=1024
OLLAMA_TIMEOUT=120

# ============================================
# ANTHROPIC CLAUDE
# ============================================
ANTHROPIC_API_KEY=${ANTHROPIC_KEY_SECRET}
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
ANTHROPIC_MAX_TOKENS=4096
ANTHROPIC_TEMPERATURE=0.7

# ============================================
# SECURITY (CRITICAL - CHANGE ALL DEFAULTS)
# ============================================
SECRET_KEY=${SECRET_KEY_SECRET}
ADMIN_JWT_SECRET=${JWT_SECRET}
ALLOWED_HOSTS=yourdomain.com,api.yourdomain.com
TRUSTED_PROXIES=${LOAD_BALANCER_IP}

# ============================================
# RATE LIMITING (Stricter in Production)
# ============================================
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=30
RATE_LIMIT_PER_HOUR=500
```

---

## Local Development Setup

### Quick Start Script

```bash
#!/bin/bash
# setup-dev.sh

set -e

echo "🚀 Setting up Empire development environment..."

# Check prerequisites
command -v docker >/dev/null 2>&1 || { echo "❌ Docker is required"; exit 1; }
command -v docker-compose >/dev/null 2>&1 || { echo "❌ Docker Compose is required"; exit 1; }

# Copy environment template
if [ ! -f .env ]; then
    echo "📝 Creating .env from template..."
    cp .env.example .env
    echo "⚠️  Please update .env with your actual credentials"
fi

# Create directories
echo "📁 Creating directories..."
mkdir -p logs temp static/uploads

# Pull Ollama models
echo "🤖 Pulling Ollama models..."
docker-compose up -d ollama
sleep 10
docker exec empire-ollama ollama pull bge-m3
docker exec empire-ollama ollama pull nomic-embed-text

# Start services
echo "🐳 Starting services..."
docker-compose up -d

# Wait for API to be healthy
echo "⏳ Waiting for API to be ready..."
for i in {1..30}; do
    if curl -f http://localhost:8000/health >/dev/null 2>&1; then
        echo "✅ API is ready!"
        break
    fi
    echo "Waiting... ($i/30)"
    sleep 2
done

# Run database migrations
echo "🗄️  Running database migrations..."
docker-compose exec api alembic upgrade head

# Show status
echo ""
echo "✅ Development environment is ready!"
echo ""
echo "📍 Services:"
echo "   API:        http://localhost:8000"
echo "   API Docs:   http://localhost:8000/docs"
echo "   Prometheus: http://localhost:9090"
echo "   Grafana:    http://localhost:3000 (admin/admin)"
echo "   Redis:      localhost:6379"
echo "   Ollama:     http://localhost:11434"
echo ""
echo "📋 Commands:"
echo "   docker-compose logs -f api        # View API logs"
echo "   docker-compose logs -f celery-worker  # View worker logs"
echo "   docker-compose down               # Stop all services"
echo ""
```

### Development Commands

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f api
docker-compose logs -f celery-worker

# Restart specific service
docker-compose restart api

# Run tests
docker-compose exec api pytest

# Access Python shell
docker-compose exec api python

# Run database migrations
docker-compose exec api alembic upgrade head

# Create new migration
docker-compose exec api alembic revision --autogenerate -m "description"

# Check Celery worker status
docker-compose exec celery-worker celery -A app.celery_worker inspect active

# Purge Celery queue
docker-compose exec celery-worker celery -A app.celery_worker purge

# Redis CLI
docker-compose exec redis redis-cli

# Stop all services
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

---

## Production Deployment

### Production Checklist

- [ ] Change all default passwords and secrets
- [ ] Enable SSL/TLS with valid certificates
- [ ] Configure firewall rules (allow only 80, 443, 22)
- [ ] Set up automated backups for Supabase
- [ ] Enable monitoring alerts
- [ ] Configure log rotation
- [ ] Set up CDN for static assets
- [ ] Enable rate limiting
- [ ] Configure CORS with specific domains
- [ ] Set up health check monitoring
- [ ] Document runbook for common issues
- [ ] Test disaster recovery procedures

### Production docker-compose.yml

```yaml
version: '3.8'

services:
  api:
    image: ghcr.io/yourorg/empire-api:latest
    container_name: empire-api-prod
    restart: always
    ports:
      - "8000:8000"
    environment:
      - ENVIRONMENT=production
    env_file:
      - .env.production
    volumes:
      - ./logs:/app/logs:rw
      - ./temp:/app/temp:rw
    deploy:
      replicas: 3
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          cpus: '1.0'
          memory: 2G
    networks:
      - empire-network
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "5"

  celery-worker:
    image: ghcr.io/yourorg/empire-api:latest
    container_name: empire-celery-prod
    restart: always
    command: celery -A app.celery_worker worker --loglevel=warning --concurrency=8 --max-tasks-per-child=1000
    env_file:
      - .env.production
    volumes:
      - ./logs:/app/logs:rw
      - ./temp:/app/temp:rw
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: '4.0'
          memory: 8G
    networks:
      - empire-network
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "5"

  nginx:
    image: nginx:alpine
    container_name: empire-nginx-prod
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
      - /etc/letsencrypt:/etc/letsencrypt:ro
    depends_on:
      - api
    networks:
      - empire-network
    logging:
      driver: "json-file"
      options:
        max-size: "50m"
        max-file: "3"

networks:
  empire-network:
    driver: bridge
```

### Nginx Configuration (Production)

```nginx
# nginx/nginx.conf

user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 4096;
    use epoll;
    multi_accept on;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    # Logging
    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for" '
                    'rt=$request_time uct="$upstream_connect_time" '
                    'uht="$upstream_header_time" urt="$upstream_response_time"';

    access_log /var/log/nginx/access.log main;

    # Performance
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    client_max_body_size 100M;

    # Gzip
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css text/xml text/javascript
               application/json application/javascript application/xml+rss
               application/rss+xml font/truetype font/opentype
               application/vnd.ms-fontobject image/svg+xml;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=30r/m;
    limit_req_zone $binary_remote_addr zone=upload_limit:10m rate=10r/m;

    # Upstream
    upstream api_backend {
        least_conn;
        server api:8000 max_fails=3 fail_timeout=30s;
        keepalive 32;
    }

    # HTTP -> HTTPS redirect
    server {
        listen 80;
        server_name yourdomain.com www.yourdomain.com;

        location /.well-known/acme-challenge/ {
            root /var/www/certbot;
        }

        location / {
            return 301 https://$server_name$request_uri;
        }
    }

    # HTTPS Server
    server {
        listen 443 ssl http2;
        server_name yourdomain.com www.yourdomain.com;

        # SSL Configuration
        ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;
        ssl_prefer_server_ciphers on;
        ssl_session_cache shared:SSL:10m;
        ssl_session_timeout 10m;

        # Security Headers
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-XSS-Protection "1; mode=block" always;
        add_header Referrer-Policy "no-referrer-when-downgrade" always;

        # API routes
        location /api/ {
            limit_req zone=api_limit burst=10 nodelay;

            proxy_pass http://api_backend;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            proxy_connect_timeout 60s;
            proxy_send_timeout 60s;
            proxy_read_timeout 60s;
            proxy_buffering off;
        }

        # WebSocket for chat
        location /ws/ {
            proxy_pass http://api_backend;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            proxy_read_timeout 3600s;
            proxy_send_timeout 3600s;
        }

        # File uploads
        location /api/documents/upload {
            limit_req zone=upload_limit burst=5 nodelay;
            client_max_body_size 100M;

            proxy_pass http://api_backend;
            proxy_request_buffering off;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # Health check (no rate limiting)
        location /health {
            proxy_pass http://api_backend;
            access_log off;
        }

        # Metrics (restrict to monitoring IPs)
        location /metrics {
            allow 10.0.0.0/8;  # Internal network
            deny all;
            proxy_pass http://api_backend;
        }

        # Static files
        location /static/ {
            alias /usr/share/nginx/html/static/;
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
    }
}
```

---

## Cloud Provider Configurations

### Render.com Deployment

#### render.yaml

```yaml
services:
  # FastAPI Application
  - type: web
    name: empire-api
    env: docker
    dockerfilePath: ./Dockerfile
    region: oregon
    plan: standard
    healthCheckPath: /health
    envVars:
      - key: ENVIRONMENT
        value: production
      - key: SUPABASE_URL
        sync: false
      - key: SUPABASE_KEY
        sync: false
      - key: SUPABASE_SERVICE_ROLE_KEY
        sync: false
      - key: REDIS_URL
        fromService:
          name: empire-redis
          type: redis
          property: connectionString
      - key: ANTHROPIC_API_KEY
        sync: false
      - key: B2_APPLICATION_KEY_ID
        sync: false
      - key: B2_APPLICATION_KEY
        sync: false
    autoDeploy: true
    scaling:
      minInstances: 2
      maxInstances: 10
      targetMemoryPercent: 70
      targetCPUPercent: 70

  # Celery Worker
  - type: worker
    name: empire-celery-worker
    env: docker
    dockerfilePath: ./Dockerfile
    dockerCommand: celery -A app.celery_worker worker --loglevel=warning --concurrency=4
    region: oregon
    plan: standard
    envVars:
      - key: ENVIRONMENT
        value: production
      - key: SUPABASE_URL
        sync: false
      - key: REDIS_URL
        fromService:
          name: empire-redis
          type: redis
          property: connectionString
    autoDeploy: true
    scaling:
      minInstances: 1
      maxInstances: 5

  # Redis
  - type: redis
    name: empire-redis
    region: oregon
    plan: standard
    maxmemoryPolicy: allkeys-lru
    ipAllowList: []  # Render services only

databases:
  # Note: Use Supabase for PostgreSQL
  # Redis managed by Render (defined above)
```

### AWS ECS Deployment

#### task-definition.json

```json
{
  "family": "empire-api",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "2048",
  "memory": "4096",
  "containerDefinitions": [
    {
      "name": "empire-api",
      "image": "yourregistry/empire-api:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "ENVIRONMENT",
          "value": "production"
        }
      ],
      "secrets": [
        {
          "name": "SUPABASE_URL",
          "valueFrom": "arn:aws:secretsmanager:region:account:secret:empire/supabase-url"
        },
        {
          "name": "SUPABASE_KEY",
          "valueFrom": "arn:aws:secretsmanager:region:account:secret:empire/supabase-key"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/empire-api",
          "awslogs-region": "us-west-2",
          "awslogs-stream-prefix": "api"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 60
      }
    }
  ]
}
```

### Digital Ocean App Platform

#### .do/app.yaml

```yaml
name: empire-document-processing
region: nyc
services:
  - name: api
    dockerfile_path: Dockerfile
    github:
      repo: yourorg/empire-api
      branch: main
      deploy_on_push: true
    health_check:
      http_path: /health
      initial_delay_seconds: 30
    http_port: 8000
    instance_count: 2
    instance_size_slug: professional-s
    envs:
      - key: ENVIRONMENT
        value: production
        scope: RUN_TIME
      - key: SUPABASE_URL
        scope: RUN_TIME
        type: SECRET
      - key: SUPABASE_KEY
        scope: RUN_TIME
        type: SECRET
    routes:
      - path: /

  - name: celery-worker
    dockerfile_path: Dockerfile
    run_command: celery -A app.celery_worker worker --loglevel=warning --concurrency=4
    instance_count: 1
    instance_size_slug: professional-m
    envs:
      - key: ENVIRONMENT
        value: production

databases:
  - name: redis
    engine: REDIS
    production: true
    version: "7"
```

---

## SSL/TLS Setup

### Let's Encrypt with Certbot

```bash
#!/bin/bash
# setup-ssl.sh

DOMAIN="yourdomain.com"
EMAIL="admin@yourdomain.com"

# Install certbot
apt-get update
apt-get install -y certbot python3-certbot-nginx

# Stop nginx temporarily
docker-compose stop nginx

# Obtain certificate
certbot certonly --standalone \
    -d $DOMAIN \
    -d www.$DOMAIN \
    --email $EMAIL \
    --agree-tos \
    --non-interactive

# Create renewal hook
cat > /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh <<'EOF'
#!/bin/bash
docker-compose restart nginx
EOF

chmod +x /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh

# Set up auto-renewal
(crontab -l 2>/dev/null; echo "0 3 * * * certbot renew --quiet") | crontab -

# Start nginx
docker-compose start nginx

echo "✅ SSL certificates installed for $DOMAIN"
```

### Nginx SSL Configuration (Self-Signed for Development)

```bash
# Generate self-signed certificate for development
mkdir -p nginx/ssl
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout nginx/ssl/nginx-selfsigned.key \
    -out nginx/ssl/nginx-selfsigned.crt \
    -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"

# Generate DH parameters
openssl dhparam -out nginx/ssl/dhparam.pem 2048
```

---

## Scaling Configuration

### Horizontal Scaling Strategy

#### Load Balancer (HAProxy)

```conf
# haproxy.cfg

global
    maxconn 4096
    log /dev/log local0
    log /dev/log local1 notice

defaults
    log global
    mode http
    option httplog
    option dontlognull
    timeout connect 5000ms
    timeout client 50000ms
    timeout server 50000ms

frontend http_front
    bind *:80
    default_backend api_backend

frontend https_front
    bind *:443 ssl crt /etc/ssl/certs/yourdomain.pem
    default_backend api_backend

backend api_backend
    balance roundrobin
    option httpchk GET /health
    http-check expect status 200

    server api1 api1:8000 check inter 5s fall 3 rise 2
    server api2 api2:8000 check inter 5s fall 3 rise 2
    server api3 api3:8000 check inter 5s fall 3 rise 2
```

### Auto-Scaling with Docker Swarm

```yaml
version: '3.8'

services:
  api:
    image: yourregistry/empire-api:latest
    deploy:
      replicas: 3
      update_config:
        parallelism: 1
        delay: 10s
        failure_action: rollback
      rollback_config:
        parallelism: 1
        delay: 10s
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          cpus: '1.0'
          memory: 2G
    networks:
      - empire-swarm
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

networks:
  empire-swarm:
    driver: overlay
```

### Kubernetes Deployment

```yaml
# k8s-deployment.yaml

apiVersion: apps/v1
kind: Deployment
metadata:
  name: empire-api
  labels:
    app: empire-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: empire-api
  template:
    metadata:
      labels:
        app: empire-api
    spec:
      containers:
      - name: api
        image: yourregistry/empire-api:latest
        ports:
        - containerPort: 8000
        env:
        - name: ENVIRONMENT
          value: "production"
        - name: SUPABASE_URL
          valueFrom:
            secretKeyRef:
              name: empire-secrets
              key: supabase-url
        resources:
          requests:
            memory: "2Gi"
            cpu: "1000m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5

---
apiVersion: v1
kind: Service
metadata:
  name: empire-api-service
spec:
  type: LoadBalancer
  selector:
    app: empire-api
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000

---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: empire-api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: empire-api
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

---

## Backup and Recovery

### Backup Script

```bash
#!/bin/bash
# backup.sh

set -e

BACKUP_DIR="/backups"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=30

echo "🔄 Starting backup at $(date)"

# Create backup directory
mkdir -p "$BACKUP_DIR/$DATE"

# Backup Supabase (PostgreSQL dump via API or direct connection)
echo "📦 Backing up Supabase database..."
pg_dump "$DATABASE_URL" | gzip > "$BACKUP_DIR/$DATE/supabase_$DATE.sql.gz"

# Backup Redis data
echo "📦 Backing up Redis..."
docker-compose exec -T redis redis-cli BGSAVE
sleep 5
docker cp empire-redis:/data/dump.rdb "$BACKUP_DIR/$DATE/redis_$DATE.rdb"

# Backup Ollama models
echo "📦 Backing up Ollama models..."
tar -czf "$BACKUP_DIR/$DATE/ollama_$DATE.tar.gz" -C "$(docker volume inspect empire_ollama-data --format '{{.Mountpoint}}')" .

# Backup configuration files
echo "📦 Backing up configuration..."
tar -czf "$BACKUP_DIR/$DATE/config_$DATE.tar.gz" .env* docker-compose*.yml nginx/

# Upload to B2 (optional)
if [ ! -z "$B2_BUCKET" ]; then
    echo "☁️  Uploading to Backblaze B2..."
    b2 sync "$BACKUP_DIR/$DATE" "b2://$B2_BUCKET/backups/$DATE/"
fi

# Clean up old backups
echo "🧹 Cleaning up old backups..."
find "$BACKUP_DIR" -type d -mtime +$RETENTION_DAYS -exec rm -rf {} +

echo "✅ Backup completed at $(date)"
```

### Restore Script

```bash
#!/bin/bash
# restore.sh

set -e

if [ -z "$1" ]; then
    echo "Usage: $0 <backup_date>"
    echo "Available backups:"
    ls -1 /backups/
    exit 1
fi

BACKUP_DATE=$1
BACKUP_DIR="/backups/$BACKUP_DATE"

if [ ! -d "$BACKUP_DIR" ]; then
    echo "❌ Backup not found: $BACKUP_DIR"
    exit 1
fi

echo "⚠️  This will restore from backup: $BACKUP_DATE"
read -p "Are you sure? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Restore cancelled"
    exit 0
fi

echo "🔄 Starting restore..."

# Stop services
echo "🛑 Stopping services..."
docker-compose down

# Restore Supabase
echo "📥 Restoring Supabase database..."
gunzip < "$BACKUP_DIR/supabase_$BACKUP_DATE.sql.gz" | psql "$DATABASE_URL"

# Restore Redis
echo "📥 Restoring Redis..."
docker-compose up -d redis
sleep 5
docker cp "$BACKUP_DIR/redis_$BACKUP_DATE.rdb" empire-redis:/data/dump.rdb
docker-compose restart redis

# Restore Ollama
echo "📥 Restoring Ollama models..."
tar -xzf "$BACKUP_DIR/ollama_$BACKUP_DATE.tar.gz" -C "$(docker volume inspect empire_ollama-data --format '{{.Mountpoint}}')"

# Start services
echo "🚀 Starting services..."
docker-compose up -d

echo "✅ Restore completed!"
```

### Automated Backup with Cron

```bash
# Add to crontab
crontab -e

# Backup every day at 2 AM
0 2 * * * /path/to/backup.sh >> /var/log/empire-backup.log 2>&1

# Weekly full backup to B2
0 3 * * 0 B2_BUCKET=empire-backups /path/to/backup.sh >> /var/log/empire-backup.log 2>&1
```

---

## Summary

### Key Files Created

- **docker-compose.yml** - Complete orchestration with all services
- **Dockerfile** - Multi-stage production build
- **.env.example** - Comprehensive environment variables
- **nginx.conf** - Production-ready reverse proxy with SSL
- **render.yaml** - Render.com deployment configuration
- **k8s-deployment.yaml** - Kubernetes deployment with auto-scaling

### Deployment Options

1. **Local Development**: Docker Compose with hot reload
2. **Render.com**: Managed PaaS with auto-scaling
3. **AWS ECS**: Container orchestration with Fargate
4. **Digital Ocean**: App Platform deployment
5. **Kubernetes**: Full cluster deployment with HPA

### Production Checklist

✅ SSL/TLS certificates configured
✅ Environment variables secured
✅ Rate limiting enabled
✅ Monitoring and alerts set up
✅ Backup and recovery procedures documented
✅ Health checks implemented
✅ Log rotation configured
✅ Auto-scaling configured
✅ Security headers enabled
✅ Firewall rules defined

---

**Next Reference File**: `testing_validation.md` - Comprehensive testing strategy with pytest examples

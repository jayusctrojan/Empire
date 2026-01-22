## 10.10 Deployment and Production Configuration

### 10.10.1 Docker Configuration for n8n

```dockerfile
FROM n8nio/n8n:latest

USER root

# Install additional dependencies
RUN apk add --no-cache \
    python3 \
    py3-pip \
    git \
    build-base \
    postgresql-client \
    redis \
    curl \
    jq

# Install Python packages for custom nodes
RUN pip3 install --no-cache-dir \
    requests \
    pandas \
    numpy \
    PyPDF2 \
    python-docx \
    openpyxl \
    beautifulsoup4 \
    lxml \
    redis \
    psycopg2-binary \
    anthropic \
    openai \
    cohere \
    tiktoken

# Create directories
RUN mkdir -p /home/node/.n8n/custom \
    && mkdir -p /home/node/.n8n/workflows \
    && mkdir -p /home/node/.n8n/credentials

# Copy custom nodes
COPY ./custom-nodes /home/node/.n8n/custom/

# Copy workflow templates
COPY ./workflows /home/node/.n8n/workflows/

# Set environment variables
ENV N8N_BASIC_AUTH_ACTIVE=true \
    N8N_BASIC_AUTH_USER=admin \
    N8N_BASIC_AUTH_PASSWORD=changeme \
    N8N_HOST=0.0.0.0 \
    N8N_PORT=5678 \
    N8N_PROTOCOL=https \
    N8N_WEBHOOK_BASE_URL=https://n8n.yourdomain.com \
    N8N_METRICS=true \
    N8N_METRICS_INCLUDE_DEFAULT=true \
    N8N_METRICS_INCLUDE_API_ENDPOINTS=true \
    N8N_LOG_LEVEL=info \
    N8N_LOG_OUTPUT=console \
    EXECUTIONS_DATA_SAVE_ON_ERROR=all \
    EXECUTIONS_DATA_SAVE_ON_SUCCESS=all \
    EXECUTIONS_DATA_SAVE_ON_PROGRESS=true \
    EXECUTIONS_DATA_SAVE_MANUAL_EXECUTIONS=true \
    GENERIC_TIMEZONE=America/New_York

# Set permissions
RUN chown -R node:node /home/node/.n8n

USER node

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:5678/healthz || exit 1

EXPOSE 5678

CMD ["n8n"]
```

### 10.10.2 Render.com Deployment Configuration

```yaml
# render.yaml
services:
  - type: web
    name: n8n-orchestration
    runtime: docker
    dockerfilePath: ./Dockerfile
    dockerContext: .
    envVars:
      - key: DATABASE_TYPE
        value: postgresdb
      - key: DATABASE_POSTGRESDB_DATABASE
        value: n8n
      - key: DATABASE_POSTGRESDB_HOST
        fromDatabase:
          name: n8n-db
          property: host
      - key: DATABASE_POSTGRESDB_PORT
        fromDatabase:
          name: n8n-db
          property: port
      - key: DATABASE_POSTGRESDB_USER
        fromDatabase:
          name: n8n-db
          property: user
      - key: DATABASE_POSTGRESDB_PASSWORD
        fromDatabase:
          name: n8n-db
          property: password
      - key: N8N_WEBHOOK_BASE_URL
        value: https://n8n-orchestration.onrender.com
      - key: N8N_BASIC_AUTH_ACTIVE
        value: true
      - key: N8N_BASIC_AUTH_USER
        sync: false
      - key: N8N_BASIC_AUTH_PASSWORD
        sync: false
      - key: ANTHROPIC_API_KEY
        sync: false
      - key: OPENAI_API_KEY
        sync: false
      - key: COHERE_API_KEY
        sync: false
      - key: SUPABASE_URL
        sync: false
      - key: SUPABASE_ANON_KEY
        sync: false
      - key: B2_ACCESS_KEY_ID
        sync: false
      - key: B2_SECRET_ACCESS_KEY
        sync: false
      - key: LIGHTRAG_API_KEY
        sync: false
      - key: CREWAI_API_KEY
        sync: false
      - key: MISTRAL_API_KEY
        sync: false
      - key: SONIOX_API_KEY
        sync: false
    healthCheckPath: /healthz
    autoDeploy: true
    plan: starter # $15/month

databases:
  - name: n8n-db
    databaseName: n8n
    user: n8n_user
    plan: starter # $7/month

  - name: redis-cache
    plan: starter # $7/month
    type: redis
    ipAllowList: []
    maxmemoryPolicy: allkeys-lru
```

### 10.10.3 Environment Variables Configuration

```bash
# .env.production
# n8n Core Configuration
N8N_BASIC_AUTH_ACTIVE=true
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=your_secure_password_here
N8N_HOST=0.0.0.0
N8N_PORT=5678
N8N_PROTOCOL=https
N8N_WEBHOOK_BASE_URL=https://your-n8n-instance.onrender.com

# Database Configuration
DATABASE_TYPE=postgresdb
DATABASE_POSTGRESDB_DATABASE=n8n
DATABASE_POSTGRESDB_HOST=your-db-host.supabase.co
DATABASE_POSTGRESDB_PORT=5432
DATABASE_POSTGRESDB_USER=n8n_user
DATABASE_POSTGRESDB_PASSWORD=your_db_password_here
DATABASE_POSTGRESDB_SCHEMA=public

***REMOVED*** Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your_anon_key_here
SUPABASE_SERVICE_KEY=your_service_key_here

# AI Services
ANTHROPIC_API_KEY=sk-ant-api-key-here
OPENAI_API_KEY=sk-openai-key-here
COHERE_API_KEY=cohere-key-here

# Storage
B2_ACCESS_KEY_ID=your_b2_key_id
B2_SECRET_ACCESS_KEY=your_b2_secret_key
B2_ENDPOINT=https://s3.us-west-001.backblazeb2.com

# External Services
LIGHTRAG_API_KEY=lightrag-key-here
LIGHTRAG_API_URL=https://lightrag-api.example.com
CREWAI_API_KEY=crewai-key-here
CREWAI_API_URL=https://crewai-api.example.com
MISTRAL_API_KEY=mistral-key-here
SONIOX_API_KEY=soniox-key-here

# Redis Cache
REDIS_HOST=redis-cache.render.com
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password_here

# Monitoring
PROMETHEUS_ENABLED=true
GRAFANA_ENABLED=true
SENTRY_DSN=your_sentry_dsn_here

# Logging
N8N_LOG_LEVEL=info
N8N_LOG_OUTPUT=console,file
N8N_LOG_FILE_LOCATION=/data/logs/n8n.log

# Executions
EXECUTIONS_DATA_SAVE_ON_ERROR=all
EXECUTIONS_DATA_SAVE_ON_SUCCESS=all
EXECUTIONS_DATA_SAVE_ON_PROGRESS=true
EXECUTIONS_DATA_SAVE_MANUAL_EXECUTIONS=true
EXECUTIONS_DATA_MAX_AGE=336
EXECUTIONS_DATA_PRUNE=true
EXECUTIONS_DATA_PRUNE_MAX_AGE=336

# Security
N8N_ENCRYPTION_KEY=your_encryption_key_here
N8N_JWT_AUTH_ACTIVE=true
N8N_JWT_AUTH_HEADER=Authorization
N8N_JWT_AUTH_HEADER_PREFIX=Bearer

# Performance
N8N_CONCURRENCY_PRODUCTION_LIMIT=10
N8N_CONCURRENCY_WEBHOOK_LIMIT=100
N8N_PAYLOAD_SIZE_MAX=100
EXECUTIONS_TIMEOUT=3600
EXECUTIONS_TIMEOUT_MAX=7200

# Features
N8N_TEMPLATES_ENABLED=true
N8N_COMMUNITY_PACKAGES_ENABLED=false
N8N_METRICS=true
N8N_METRICS_INCLUDE_DEFAULT=true
N8N_METRICS_INCLUDE_API_ENDPOINTS=true
```

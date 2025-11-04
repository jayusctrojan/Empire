# Empire v7.3 - Render Deployment Guide

## 📋 Summary

**Your Setup:**
- ✅ Redis 7 Alpine running in Docker on Mac Studio (port 6379)
- ✅ Neo4j Community running in Docker on Mac Studio (port 7687)
- ✅ Tailscale configured with IP: **100.119.86.6**
- ✅ Supabase database fully configured (33 tables)
- ✅ Code pushed to GitHub: `jayusctrojan/Empire`

**What We're Deploying:**
1. FastAPI Web Service → `empire-api`
2. Celery Worker Service → `empire-celery-worker`

---

## 🚀 Quick Deploy (Via Render Dashboard)

### Step 1: Deploy FastAPI Web Service

1. Go to https://dashboard.render.com/
2. Click **"New +"** → **"Web Service"**
3. Connect repository: **`jayusctrojan/Empire`**

**Service Settings:**
- **Name**: `empire-api`
- **Region**: Oregon (US West)
- **Branch**: `main`
- **Runtime**: Python 3
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Plan**: Starter ($7/month)
- **Health Check Path**: `/health`

**Environment Variables:**

⚠️ **SECURITY**: Copy/paste actual values from your local `.env.render` file (NOT committed to git).

```bash
PYTHON_VERSION=3.11
ENVIRONMENT=production
SUPABASE_URL=<from .env.render>
SUPABASE_SERVICE_KEY=<from .env.render>
NEO4J_URI=bolt+ssc://100.119.86.6:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=<from .env.render>
REDIS_URL=redis://red-d44og3n5r7bs73b2ctbg
ANTHROPIC_API_KEY=<from .env.render>
LLAMA_CLOUD_API_KEY=<from .env.render>
LLAMAINDEX_SERVICE_URL=https://jb-llamaindex.onrender.com
CREWAI_SERVICE_URL=https://jb-crewai.onrender.com
CREWAI_API_KEY=<from .env.render>
B2_APPLICATION_KEY_ID=<from .env.render>
B2_APPLICATION_KEY=<from .env.render>
B2_BUCKET_NAME=JB-Course-KB
SONIOX_API_KEY=<from .env.render>
MISTRAL_API_KEY=<from .env.render>
LANGEXTRACT_API_KEY=<from .env.render>
CORS_ORIGINS=*
LOG_LEVEL=INFO
```

4. Click **"Create Web Service"**
5. Wait 5-10 minutes for deployment

---

### Step 2: Deploy Celery Worker Service

1. Click **"New +"** → **"Background Worker"**
2. Connect repository: **`jayusctrojan/Empire`**

**Service Settings:**
- **Name**: `empire-celery-worker`
- **Region**: Oregon (US West)
- **Branch**: `main`
- **Runtime**: Python 3
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `celery -A app.celery_app worker --loglevel=info --concurrency=2`
- **Plan**: Starter ($7/month)

**Environment Variables:**

Same as FastAPI service above, **PLUS**:

```bash
CELERY_BROKER_URL=redis://100.119.86.6:6379/0
CELERY_RESULT_BACKEND=redis://100.119.86.6:6379/1
```

4. Click **"Create Background Worker"**
5. Wait 5-10 minutes for deployment

---

## ✅ Verify Deployment

### 1. Check FastAPI Health

```bash
# Replace with your actual Render URL after deployment
curl https://empire-api.onrender.com/health

# Expected:
{
  "status": "healthy",
  "version": "7.3.0",
  "service": "Empire FastAPI"
}
```

### 2. Check Detailed Health

```bash
curl https://empire-api.onrender.com/health/detailed
```

Should show all services healthy:
- ✅ Supabase
- ✅ Neo4j (via Tailscale 100.119.86.6)
- ✅ Redis (via Tailscale 100.119.86.6)
- ✅ LlamaIndex
- ✅ CrewAI

### 3. View API Docs

```bash
open https://empire-api.onrender.com/docs
```

### 4. Check Celery Worker Logs

1. Go to Render Dashboard
2. Click `empire-celery-worker`
3. View "Logs" tab
4. Should see worker started with task queues ready

---

## 🔧 Important: Tailscale Requirements

Since Redis and Neo4j are running **locally** on your Mac Studio, Render needs to access them via **Tailscale IP: 100.119.86.6**.

**Ensure:**

1. ✅ **Tailscale is running** on Mac Studio:
   ```bash
   tailscale status
   ```

2. ✅ **Mac Studio stays powered on** (Render needs continuous access)

3. ✅ **Docker containers are running**:
   ```bash
   docker ps | grep -E "redis|neo4j"
   ```

4. ✅ **Services bound to 0.0.0.0** (not just 127.0.0.1):
   - Redis: Already confirmed on 0.0.0.0:6379 ✅
   - Neo4j: Should be on 0.0.0.0:7687

---

## 📊 Service URLs (After Deployment)

- **API**: https://empire-api.onrender.com
- **Docs**: https://empire-api.onrender.com/docs
- **Health**: https://empire-api.onrender.com/health
- **Metrics**: https://empire-api.onrender.com/monitoring/metrics

---

## 💰 Cost

- FastAPI: $7/month
- Celery Worker: $7/month
- **Total**: $14/month for backend infrastructure

Plus existing:
- Supabase: $25/month
- LlamaIndex: Already deployed
- CrewAI: Already deployed

**Grand Total**: ~$39/month

---

## 📁 Files Created

- ✅ `app/main.py` - FastAPI application
- ✅ `app/celery_app.py` - Celery configuration
- ✅ `app/core/database.py` - Database connections
- ✅ `app/tasks/*.py` - Celery tasks (documents, embeddings, graph, crewai)
- ✅ `requirements.txt` - Dependencies
- ✅ `render.yaml` - Deployment config
- ✅ `.env.render` - **Environment variables for Render**
- ✅ `RENDER_DEPLOYMENT.md` - **This file**

---

## 🎯 Next Steps

After deployment completes:

1. ✅ Mark Task 1.1 as complete in TaskMaster
2. ⏭️ Task 1.5: TLS 1.3 configuration (Render provides automatically)
3. ⏭️ Task 1.6: Integration testing and validation

---

**File Locations:**
- Deployment Guide: `/Users/jaybajaj/Library/Mobile Documents/com~apple~CloudDocs/Documents/ai/Empire/RENDER_DEPLOYMENT.md`
- Environment Variables: `/Users/jaybajaj/Library/Mobile Documents/com~apple~CloudDocs/Documents/ai/Empire/.env.render`

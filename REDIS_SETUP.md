# Redis Setup Guide for Empire v7.2

## Quick Setup (2 minutes)

Redis is now configured in your `docker-compose.yml` alongside Neo4j.

### Step 1: Start Redis (with Neo4j)

```bash
# Navigate to Empire directory
cd ~/Library/Mobile\ Documents/com~apple~CloudDocs/Documents/ai/Empire

# Start both Neo4j and Redis
docker-compose up -d

# Or restart if Neo4j is already running
docker-compose restart
```

### Step 2: Verify Redis is Running

```bash
# Check container status
docker ps | grep empire-redis

# Should show:
# CONTAINER ID   IMAGE           STATUS          PORTS                    NAMES
# xxxx           redis:7-alpine  Up 10 seconds   0.0.0.0:6379->6379/tcp   empire-redis

# Test Redis connection
docker exec empire-redis redis-cli ping

# Should return: PONG
```

### Step 3: Test Redis Operations

```bash
# Set a test key
docker exec empire-redis redis-cli SET test "Hello Empire"

# Get the value
docker exec empire-redis redis-cli GET test

# Should return: "Hello Empire"

# Check Redis info
docker exec empire-redis redis-cli INFO server | head -10
```

---

## Redis Configuration

### Settings in docker-compose.yml

```yaml
redis:
  image: redis:7-alpine          # Lightweight Redis 7.x
  container_name: empire-redis
  restart: unless-stopped        # Auto-restart on crash
  ports:
    - "6379:6379"               # Standard Redis port
  command: redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru
  volumes:
    - ./redis/data:/data        # Persistent storage
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
    interval: 10s
    timeout: 3s
    retries: 3
```

### What Each Setting Does:

- **`--appendonly yes`**: Enables persistence (AOF - Append Only File)
- **`--maxmemory 512mb`**: Limits Redis memory to 512MB (cache only)
- **`--maxmemory-policy allkeys-lru`**: Evicts least recently used keys when full
- **Healthcheck**: Automatically checks Redis is responding every 10s

---

## Python Integration

### Install Redis Client

```bash
# Activate your venv first
source venv/bin/activate

# Install redis-py
pip install redis
```

### Basic Usage

```python
import redis
import os
from dotenv import load_dotenv

load_dotenv()

# Connect to Redis
redis_client = redis.from_url(
    os.getenv("REDIS_URL", "redis://localhost:6379"),
    decode_responses=True
)

# Test connection
redis_client.ping()  # Returns True

# Basic operations
redis_client.set("key", "value")
redis_client.get("key")  # Returns "value"

# Set with expiration (1 hour)
redis_client.setex("temp_key", 3600, "temporary value")

# Check if key exists
redis_client.exists("key")  # Returns 1 (True) or 0 (False)

# Delete key
redis_client.delete("key")
```

---

## Semantic Caching Implementation

### Cache Structure for Empire

```python
import redis
import hashlib
import json
import numpy as np
from typing import Optional, Dict, Any

class SemanticCache:
    """Tiered semantic cache for Empire RAG queries"""

    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url, decode_responses=False)
        self.ttl = 3600  # 1 hour default TTL

    def _generate_key(self, query_embedding: list[float]) -> str:
        """Generate cache key from embedding"""
        # Use first 100 dimensions for key (faster)
        key_data = json.dumps(query_embedding[:100])
        return f"cache:{hashlib.sha256(key_data.encode()).hexdigest()}"

    def _calculate_similarity(self, emb1: list[float], emb2: list[float]) -> float:
        """Calculate cosine similarity between embeddings"""
        a = np.array(emb1)
        b = np.array(emb2)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

    def get(self, query_embedding: list[float]) -> Optional[Dict[str, Any]]:
        """
        Get cached result with tiered similarity matching:
        - 0.98+: Direct hit (exact match)
        - 0.93-0.97: Similar query (return with flag)
        - 0.88-0.92: Suggestion (return as suggestion)
        - <0.88: Cache miss
        """
        key = self._generate_key(query_embedding)

        # Try exact match first
        cached = self.redis.get(key)
        if cached:
            data = json.loads(cached)
            similarity = self._calculate_similarity(
                query_embedding,
                data["embedding"]
            )

            if similarity >= 0.98:
                return {
                    "result": data["result"],
                    "cache_hit": "exact",
                    "similarity": similarity
                }
            elif similarity >= 0.93:
                return {
                    "result": data["result"],
                    "cache_hit": "similar",
                    "similarity": similarity
                }
            elif similarity >= 0.88:
                return {
                    "result": data["result"],
                    "cache_hit": "suggestion",
                    "similarity": similarity
                }

        # Check similar queries (scan last 100 cached queries)
        cursor = 0
        pattern = "cache:*"
        best_match = None
        best_similarity = 0.0

        # Scan through cache
        while True:
            cursor, keys = self.redis.scan(cursor, match=pattern, count=100)

            for key in keys:
                cached = self.redis.get(key)
                if cached:
                    data = json.loads(cached)
                    similarity = self._calculate_similarity(
                        query_embedding,
                        data["embedding"]
                    )

                    if similarity > best_similarity:
                        best_similarity = similarity
                        best_match = data

            if cursor == 0:
                break

        # Return best match if above threshold
        if best_match and best_similarity >= 0.88:
            cache_type = (
                "exact" if best_similarity >= 0.98
                else "similar" if best_similarity >= 0.93
                else "suggestion"
            )
            return {
                "result": best_match["result"],
                "cache_hit": cache_type,
                "similarity": best_similarity
            }

        return None

    def set(self, query_embedding: list[float], result: Any, ttl: Optional[int] = None):
        """Store query result in cache"""
        key = self._generate_key(query_embedding)
        data = {
            "embedding": query_embedding,
            "result": result,
            "timestamp": time.time()
        }

        ttl = ttl or self.ttl
        self.redis.setex(key, ttl, json.dumps(data))

    def clear(self):
        """Clear all cache entries"""
        cursor = 0
        pattern = "cache:*"

        while True:
            cursor, keys = self.redis.scan(cursor, match=pattern, count=1000)
            if keys:
                self.redis.delete(*keys)
            if cursor == 0:
                break

# Usage in FastAPI
from fastapi import FastAPI

app = FastAPI()
cache = SemanticCache("redis://localhost:6379")

@app.post("/query")
async def query(query: str):
    # Generate embedding
    embedding = generate_embeddings(query)  # Your BGE-M3 function

    # Check cache
    cached_result = cache.get(embedding)
    if cached_result:
        return {
            "answer": cached_result["result"],
            "cached": True,
            "cache_type": cached_result["cache_hit"],
            "similarity": cached_result["similarity"]
        }

    # Not in cache - perform full RAG search
    result = perform_rag_search(query)

    # Cache the result
    cache.set(embedding, result)

    return {
        "answer": result,
        "cached": False
    }
```

---

## Monitoring Redis

### Check Memory Usage

```bash
# Get memory stats
docker exec empire-redis redis-cli INFO memory

# Key metrics to watch:
# - used_memory_human: Current memory usage
# - maxmemory_human: Memory limit (512MB)
# - mem_fragmentation_ratio: Should be close to 1.0
```

### Check Cache Hit Rate

```bash
# Get stats
docker exec empire-redis redis-cli INFO stats | grep keyspace

# Calculate hit rate:
# hit_rate = keyspace_hits / (keyspace_hits + keyspace_misses)
```

### View All Keys

```bash
# Count keys
docker exec empire-redis redis-cli DBSIZE

# List all keys (careful in production)
docker exec empire-redis redis-cli KEYS "cache:*"

# Get key info
docker exec empire-redis redis-cli TTL "cache:xxxx"
```

---

## Performance Tuning

### Increase Memory Limit (if needed)

Edit `docker-compose.yml`:

```yaml
redis:
  command: redis-server --appendonly yes --maxmemory 1gb --maxmemory-policy allkeys-lru
```

Then restart:

```bash
docker-compose restart redis
```

### Common Eviction Policies

- **`allkeys-lru`**: (Recommended) Evict least recently used keys
- **`allkeys-lfu`**: Evict least frequently used keys
- **`volatile-lru`**: Only evict keys with TTL set
- **`noeviction`**: Never evict (return errors when full)

---

## Troubleshooting

### Issue: Redis not starting

```bash
# Check logs
docker logs empire-redis

# Common issues:
# 1. Port 6379 already in use
#    Solution: Change port in docker-compose.yml to 6380
# 2. Permission issues
#    Solution: sudo chown -R 999:999 ./redis/data
```

### Issue: Connection refused

```bash
# Check Redis is running
docker ps | grep redis

# Test connection
docker exec empire-redis redis-cli ping

# If not running, start it
docker-compose up -d redis
```

### Issue: Memory errors

```bash
# Check current memory
docker exec empire-redis redis-cli INFO memory | grep used_memory_human

# If near limit (512MB), increase maxmemory in docker-compose.yml
```

---

## Backup and Restore

### Backup Redis Data

```bash
# Redis automatically saves to ./redis/data/appendonly.aof
# To create a manual backup:
cp -r ./redis/data ./redis/backup-$(date +%Y%m%d)

# Or use Redis SAVE command
docker exec empire-redis redis-cli SAVE
```

### Restore from Backup

```bash
# Stop Redis
docker-compose stop redis

# Restore data directory
rm -rf ./redis/data/*
cp -r ./redis/backup-20250101/* ./redis/data/

# Start Redis
docker-compose start redis
```

---

## Summary

✅ **What you have now:**
- Redis 7.x running in Docker
- 512MB memory limit with LRU eviction
- Persistent storage (AOF enabled)
- Auto-restart on failure
- Health checks every 10s
- Running on `localhost:6379`

✅ **Ready for:**
- Semantic caching (3-tier similarity matching)
- Session storage
- Rate limiting
- Temporary data storage
- Query result caching

✅ **Memory footprint:**
- Redis container: ~10-20MB base
- Cache data: Up to 512MB
- Total: ~500-550MB max

Your `.env` already has `REDIS_URL=redis://localhost:6379` configured! 🎉

---

## Next Steps

1. ✅ Redis is running: `docker ps | grep redis`
2. Test connection: `docker exec empire-redis redis-cli ping`
3. Implement semantic caching in FastAPI
4. Monitor cache hit rates
5. Tune memory settings as needed

---

**Last Updated**: 2025-01-01
**Empire Version**: v7.2
**Redis Version**: 7.x (Alpine)

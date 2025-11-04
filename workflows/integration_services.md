# External Service Integration Configuration

**Purpose**: Configuration and integration patterns for all external services used in the Empire system.

---

## Table of Contents

1. [Supabase Integration](#1-supabase-integration)
2. [Ollama Integration](#2-ollama-integration)
3. [OpenAI Integration](#3-openai-integration)
4. [Backblaze B2 Integration](#4-backblaze-b2-integration)
5. [Redis Integration](#5-redis-integration)
6. [Celery Integration](#6-celery-integration)
7. [CrewAI Integration](#7-crewai-integration)
8. [Cohere Integration](#8-cohere-integration)
9. [Anthropic Claude Integration](#9-anthropic-claude-integration)

---

## 1. Supabase Integration

### 1.1 Configuration

```python
# app/config.py

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    supabase_url: str  # https://your-project.supabase.co
    supabase_key: str  # Your anon/service key
    supabase_service_role_key: str  # Optional: for admin operations

    class Config:
        env_file = ".env"
```

### 1.2 Client Setup

```python
# app/integrations/supabase_client.py

from supabase import create_client, Client
from functools import lru_cache
from app.config import Settings

@lru_cache()
def get_supabase_client() -> Client:
    """
    Get cached Supabase client instance.
    Uses connection pooling automatically.
    """
    settings = Settings()
    return create_client(settings.supabase_url, settings.supabase_key)

# Usage
from app.integrations.supabase_client import get_supabase_client

db = get_supabase_client()
result = db.table('documents').select('*').execute()
```

### 1.3 RPC Function Calls

```python
# Call stored procedures
result = db.rpc('vector_search', {
    'query_embedding': embedding_vector,
    'match_threshold': 0.7,
    'match_count': 10
}).execute()

# Call with error handling
try:
    result = db.rpc('hybrid_search', params).execute()
    return result.data
except Exception as e:
    logger.error(f"Supabase RPC failed: {e}")
    raise
```

### 1.4 Environment Variables

```bash
# .env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_anon_key_here
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key_here  # Optional
```

---

## 2. Ollama Integration

### 2.1 Configuration

```python
# app/integrations/ollama_client.py

import httpx
from typing import List, Dict
import logging
from app.config import Settings

logger = logging.getLogger(__name__)

class OllamaClient:
    """Client for Ollama API"""

    def __init__(self):
        self.settings = Settings()
        self.base_url = self.settings.ollama_api_url
        self.timeout = 60.0

    async def generate_embedding(
        self,
        text: str,
        model: str = "bge-m3"
    ) -> List[float]:
        """
        Generate embeddings using Ollama.

        Args:
            text: Text to embed
            model: Model name (bge-m3, nomic-embed-text)

        Returns:
            Embedding vector (1024-dim for bge-m3, 768-dim for nomic)
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/embeddings",
                json={
                    "model": model,
                    "prompt": text
                }
            )
            response.raise_for_status()
            result = response.json()
            return result['embedding']

    async def generate_embeddings_batch(
        self,
        texts: List[str],
        model: str = "bge-m3"
    ) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        import asyncio

        tasks = [
            self.generate_embedding(text, model)
            for text in texts
        ]
        return await asyncio.gather(*tasks)

    async def list_models(self) -> List[Dict]:
        """List available models"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            return response.json()['models']

    async def pull_model(self, model: str):
        """Pull a model (blocking operation)"""
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{self.base_url}/api/pull",
                json={"name": model}
            )
            response.raise_for_status()
            return response.json()
```

### 2.2 Model Configuration

```yaml
# Recommended models and dimensions
models:
  bge-m3:
    dimensions: 1024
    languages: 100+
    use_case: "Multilingual, best quality"
    cost: Free (local)

  nomic-embed-text:
    dimensions: 768
    languages: English
    use_case: "Fast, good quality"
    cost: Free (local)

  mxbai-embed-large:
    dimensions: 1024
    languages: English
    use_case: "High performance"
    cost: Free (local)
```

### 2.3 Environment Variables

```bash
# .env
OLLAMA_API_URL=http://localhost:11434
OLLAMA_DEFAULT_MODEL=bge-m3
OLLAMA_EMBEDDING_DIMENSIONS=1024
```

### 2.4 Docker Setup for Ollama

```yaml
# docker-compose.yml
services:
  ollama:
    image: ollama/ollama:latest
    container_name: empire_ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama_models:/root/.ollama
    command: serve

volumes:
  ollama_models:
```

```bash
# Pull models after container starts
docker exec empire_ollama ollama pull bge-m3
docker exec empire_ollama ollama pull nomic-embed-text
```

---

## 3. OpenAI Integration

### 3.1 Configuration

```python
# app/integrations/openai_client.py

import openai
from typing import List
from app.config import Settings

class OpenAIClient:
    """Client for OpenAI API (fallback for embeddings)"""

    def __init__(self):
        settings = Settings()
        openai.api_key = settings.openai_api_key

    async def generate_embedding(
        self,
        text: str,
        model: str = "text-embedding-ada-002"
    ) -> List[float]:
        """
        Generate embedding using OpenAI.

        Args:
            text: Text to embed
            model: Model name

        Returns:
            Embedding vector (1536-dim for ada-002)
        """
        response = await openai.Embedding.acreate(
            model=model,
            input=text
        )
        return response['data'][0]['embedding']

    async def generate_embeddings_batch(
        self,
        texts: List[str],
        model: str = "text-embedding-ada-002"
    ) -> List[List[float]]:
        """Batch embedding generation (up to 2048 texts)"""
        response = await openai.Embedding.acreate(
            model=model,
            input=texts
        )
        return [item['embedding'] for item in response['data']]
```

### 3.2 Cost Tracking

```python
# Track OpenAI usage
class OpenAIUsageTracker:
    COST_PER_1K_TOKENS = {
        'text-embedding-ada-002': 0.0001,
        'gpt-3.5-turbo': 0.0015,
        'gpt-4': 0.03,
    }

    def calculate_cost(self, model: str, tokens: int) -> float:
        cost_per_token = self.COST_PER_1K_TOKENS.get(model, 0) / 1000
        return tokens * cost_per_token
```

### 3.3 Environment Variables

```bash
# .env
OPENAI_API_KEY=sk-your-key-here
OPENAI_EMBEDDING_MODEL=text-embedding-ada-002
OPENAI_FALLBACK_ENABLED=true
```

---

## 4. Backblaze B2 Integration

### 4.1 Configuration

```python
# app/integrations/b2_client.py

from b2sdk.v2 import B2Api, InMemoryAccountInfo
from typing import BinaryIO, Dict
import logging
from app.config import Settings

logger = logging.getLogger(__name__)

class B2Client:
    """Client for Backblaze B2 storage"""

    def __init__(self):
        settings = Settings()
        self.info = InMemoryAccountInfo()
        self.api = B2Api(self.info)

        # Authorize
        self.api.authorize_account(
            "production",
            settings.b2_application_key_id,
            settings.b2_application_key
        )

        self.bucket_name = settings.b2_bucket_name
        self.bucket = self.api.get_bucket_by_name(self.bucket_name)

    def upload_file(
        self,
        file_data: BinaryIO,
        file_name: str,
        content_type: str = "application/octet-stream",
        metadata: Dict[str, str] = None
    ) -> Dict:
        """
        Upload file to B2.

        Args:
            file_data: File binary data
            file_name: Remote file name
            content_type: MIME type
            metadata: Custom metadata dict

        Returns:
            File info dict with file_id and url
        """
        try:
            file_info = self.bucket.upload_bytes(
                data_bytes=file_data.read(),
                file_name=file_name,
                content_type=content_type,
                file_infos=metadata or {}
            )

            logger.info(f"Uploaded to B2: {file_name}")

            return {
                'file_id': file_info.id_,
                'file_name': file_info.file_name,
                'content_type': file_info.content_type,
                'size': file_info.size,
                'upload_timestamp': file_info.upload_timestamp,
                'url': self.get_download_url(file_info.file_name)
            }

        except Exception as e:
            logger.error(f"B2 upload failed: {e}")
            raise

    def download_file(self, file_name: str) -> bytes:
        """Download file from B2"""
        downloaded_file = self.bucket.download_file_by_name(file_name)
        return downloaded_file.save_to_bytes()

    def delete_file(self, file_name: str, file_id: str):
        """Delete file from B2"""
        self.api.delete_file_version(file_id, file_name)
        logger.info(f"Deleted from B2: {file_name}")

    def get_download_url(self, file_name: str) -> str:
        """Get public download URL"""
        return f"https://f002.backblazeb2.com/file/{self.bucket_name}/{file_name}"

    def list_files(self, prefix: str = None, limit: int = 100) -> List[Dict]:
        """List files in bucket"""
        files = []
        for file_version, _ in self.bucket.ls(
            folder_to_list=prefix or "",
            recursive=True,
            fetch_count=limit
        ):
            files.append({
                'file_id': file_version.id_,
                'file_name': file_version.file_name,
                'size': file_version.size,
                'upload_timestamp': file_version.upload_timestamp
            })
        return files
```

### 4.2 Environment Variables

```bash
# .env
B2_APPLICATION_KEY_ID=your_key_id_here
B2_APPLICATION_KEY=your_application_key_here
B2_BUCKET_NAME=empire-documents
```

### 4.3 Bucket Structure

```
empire-documents/
├── documents/
│   ├── {document_id}.{ext}
│   └── ...
├── processed/
│   ├── {document_id}_processed.json
│   └── ...
└── exports/
    ├── {export_id}.zip
    └── ...
```

---

## 5. Redis Integration

### 5.1 Configuration

```python
# app/integrations/redis_client.py

from redis import Redis
from redis.asyncio import Redis as AsyncRedis
from typing import Optional, Any
import json
from app.config import Settings

class RedisClient:
    """Sync Redis client for caching"""

    def __init__(self):
        settings = Settings()
        self.client = Redis.from_url(
            settings.redis_url,
            decode_responses=True
        )

    def get(self, key: str) -> Optional[str]:
        """Get value by key"""
        return self.client.get(key)

    def set(
        self,
        key: str,
        value: Any,
        ttl: int = 3600
    ):
        """Set value with TTL (seconds)"""
        if not isinstance(value, str):
            value = json.dumps(value)
        self.client.setex(key, ttl, value)

    def delete(self, key: str):
        """Delete key"""
        self.client.delete(key)

    def exists(self, key: str) -> bool:
        """Check if key exists"""
        return self.client.exists(key) > 0

class AsyncRedisClient:
    """Async Redis client"""

    def __init__(self):
        settings = Settings()
        self.client = AsyncRedis.from_url(
            settings.redis_url,
            decode_responses=True
        )

    async def get(self, key: str) -> Optional[str]:
        return await self.client.get(key)

    async def set(self, key: str, value: Any, ttl: int = 3600):
        if not isinstance(value, str):
            value = json.dumps(value)
        await self.client.setex(key, ttl, value)

    async def delete(self, key: str):
        await self.client.delete(key)
```

### 5.2 Caching Patterns

```python
# Search result caching
from app.integrations.redis_client import RedisClient
import hashlib

class SearchCache:
    def __init__(self):
        self.redis = RedisClient()
        self.ttl = 3600  # 1 hour

    def generate_cache_key(self, query: str, filters: dict) -> str:
        """Generate cache key from query and filters"""
        cache_string = f"{query}:{json.dumps(filters, sort_keys=True)}"
        return f"search:{hashlib.md5(cache_string.encode()).hexdigest()}"

    def get(self, query: str, filters: dict) -> Optional[dict]:
        """Get cached search results"""
        key = self.generate_cache_key(query, filters)
        cached = self.redis.get(key)
        return json.loads(cached) if cached else None

    def set(self, query: str, filters: dict, results: dict):
        """Cache search results"""
        key = self.generate_cache_key(query, filters)
        self.redis.set(key, results, ttl=self.ttl)
```

### 5.3 Environment Variables

```bash
# .env
REDIS_URL=redis://localhost:6379/0
REDIS_MAX_CONNECTIONS=50
REDIS_CACHE_TTL=3600
```

---

## 6. Celery Integration

### 6.1 Configuration

```python
# app/celery_app.py

from celery import Celery
from app.config import Settings

settings = Settings()

celery_app = Celery(
    'empire',
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=['app.tasks.celery_tasks']
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=1800,  # 30 minutes
    task_soft_time_limit=1500,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)
```

### 6.2 Task Definitions

```python
# app/tasks/celery_tasks.py

from app.celery_app import celery_app
from app.services.document_processing_service import DocumentProcessingService
import logging

logger = logging.getLogger(__name__)

@celery_app.task(name='process_document', bind=True, max_retries=3)
def process_document_task(self, document_id: str):
    """
    Process document: extract text, chunk, generate embeddings.

    Args:
        document_id: Document identifier

    Returns:
        Processing results dict
    """
    try:
        service = DocumentProcessingService()
        result = service.process_document_sync(document_id)
        logger.info(f"Document {document_id} processed successfully")
        return result

    except Exception as e:
        logger.error(f"Document processing failed: {e}")
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=2 ** self.request.retries)

@celery_app.task(name='generate_embeddings')
def generate_embeddings_task(document_id: str, chunks: list):
    """Generate embeddings for document chunks"""
    from app.services.embedding_service import EmbeddingService

    service = EmbeddingService()
    return service.generate_embeddings_batch_sync(chunks)

# Periodic tasks
@celery_app.task(name='cleanup_old_files')
def cleanup_old_files():
    """Cleanup old temporary files (runs daily)"""
    from app.services.cleanup_service import CleanupService

    service = CleanupService()
    service.cleanup_temp_files(days_old=7)
```

### 6.3 Environment Variables

```bash
# .env
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
CELERY_TASK_TRACK_STARTED=true
CELERY_TASK_TIME_LIMIT=1800
```

### 6.4 Running Workers

```bash
# Start Celery worker
celery -A app.celery_app worker --loglevel=info

# Start with multiple workers
celery -A app.celery_app worker --loglevel=info --concurrency=4

# Start beat scheduler (for periodic tasks)
celery -A app.celery_app beat --loglevel=info
```

---

## 7. CrewAI Integration

### 7.1 Configuration

```python
# app/integrations/crewai_client.py

from crewai import Agent, Task, Crew, Process
from app.config import Settings

class CrewAIClient:
    """Client for CrewAI multi-agent workflows"""

    def __init__(self):
        settings = Settings()
        self.api_key = settings.anthropic_api_key
        self.default_model = settings.agent_llm_model

    def create_agent(
        self,
        role: str,
        goal: str,
        backstory: str,
        tools: list = None,
        llm_config: dict = None
    ) -> Agent:
        """Create a CrewAI agent"""
        config = llm_config or {
            'model': self.default_model,
            'temperature': 0.7,
            'api_key': self.api_key
        }

        return Agent(
            role=role,
            goal=goal,
            backstory=backstory,
            tools=tools or [],
            verbose=True,
            allow_delegation=True,
            llm_config=config
        )

    def create_crew(
        self,
        agents: list,
        tasks: list,
        process: str = 'sequential',
        memory: bool = True
    ) -> Crew:
        """Create a crew with agents and tasks"""
        process_type = Process.sequential if process == 'sequential' else Process.hierarchical

        return Crew(
            agents=agents,
            tasks=tasks,
            process=process_type,
            memory=memory,
            verbose=True
        )
```

### 7.2 Environment Variables

```bash
# .env
CREWAI_ENABLED=true
AGENT_LLM_MODEL=claude-sonnet-4-5-20250929
AGENT_LLM_MAX_TOKENS=4096
CREWAI_MAX_ITERATIONS=5
```

---

## 8. BGE-Reranker-v2 Integration (Local Mac Studio)

### 8.1 Overview

**BGE-Reranker-v2** runs locally on Mac Studio via Ollama (accessed via Tailscale from Render services).
- **Cost**: $0 (local, replaces Cohere which costs $30-50/month)
- **Performance**: 10-20ms latency per batch, 25-35% better result ordering
- **Model**: 299M parameters, ~1.5GB RAM
- **Access**: Via Tailscale secure connection from production services

### 8.2 Configuration

```python
# app/integrations/bge_reranker_client.py

import httpx
from typing import List, Dict
from app.config import Settings

class BGERerankerClient:
    """Client for BGE-Reranker-v2 via Ollama (local Mac Studio)"""

    def __init__(self):
        settings = Settings()
        # Access via Tailscale from Render to Mac Studio
        self.base_url = settings.ollama_reranker_url  # e.g., http://100.x.x.x:11434
        self.model = "bge-reranker-v2-m3"
        self.timeout = 30.0

    async def rerank(
        self,
        query: str,
        documents: List[str],
        top_n: int = 10
    ) -> List[Dict]:
        """
        Rerank search results using BGE-Reranker-v2 (local).

        Args:
            query: Search query
            documents: List of document texts
            top_n: Number of top results to return

        Returns:
            Reranked results with scores
        """
        # Score each document
        scores = []
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for idx, doc in enumerate(documents):
                # Format as query-document pair for reranker
                prompt = f"query: {query}\ndoc: {doc}"

                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False
                    }
                )

                result = response.json()
                # Extract relevance score from model output
                score = self._parse_relevance_score(result.get('response', ''))

                scores.append({
                    'index': idx,
                    'text': doc,
                    'relevance_score': score
                })

        # Sort by relevance score (descending) and return top_n
        ranked_results = sorted(scores, key=lambda x: x['relevance_score'], reverse=True)
        return ranked_results[:top_n]

    def _parse_relevance_score(self, response: str) -> float:
        """Parse relevance score from BGE-Reranker-v2 output"""
        try:
            # BGE-Reranker-v2 outputs a score, parse it
            # Implementation depends on exact model output format
            return float(response.strip())
        except:
            return 0.0
```

### 8.3 Environment Variables

```bash
# .env
# BGE-Reranker-v2 (Local Mac Studio via Tailscale)
OLLAMA_RERANKER_URL=http://100.x.x.x:11434  # Tailscale IP
BGE_RERANKER_MODEL=bge-reranker-v2-m3
BGE_RERANKER_ENABLED=true
BGE_RERANKER_TIMEOUT=30
```

### 8.4 Mac Studio Setup (via Tailscale)

**On Mac Studio:**
```bash
# Install Ollama
brew install ollama

# Start Ollama service
brew services start ollama

# Pull BGE-Reranker-v2 model
ollama pull bge-reranker-v2-m3

# Install Tailscale for secure access
brew install tailscale
sudo tailscale up

# Get Tailscale IP
tailscale ip -4
# Example output: 100.x.x.x
```

**On Render (Production Services):**
```bash
# Add Tailscale to your Render service
# Set environment variable with Tailscale IP
OLLAMA_RERANKER_URL=http://100.x.x.x:11434
```

### 8.5 Benefits vs Cohere

| Feature | BGE-Reranker-v2 (Local) | Cohere |
|---------|-------------------------|---------|
| **Cost** | $0/month | $30-50/month |
| **Latency** | 10-20ms | 100-200ms |
| **Quality** | 25-35% improvement | 40% improvement |
| **Privacy** | Data stays local | Sent to API |
| **Reliability** | Local control | API dependency |
| **Scalability** | Mac Studio capacity | API limits |

---

## 9. Anthropic Claude Integration

### 9.1 Configuration

```python
# app/integrations/anthropic_client.py

import anthropic
from typing import List, Dict, AsyncGenerator
from app.config import Settings

class AnthropicClient:
    """Client for Anthropic Claude API"""

    def __init__(self):
        settings = Settings()
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.default_model = "claude-sonnet-4-5-20250929"

    async def generate_completion(
        self,
        messages: List[Dict],
        system: str = None,
        model: str = None,
        max_tokens: int = 2048,
        temperature: float = 0.7
    ) -> Dict:
        """Generate completion"""
        response = self.client.messages.create(
            model=model or self.default_model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=messages
        )

        return {
            'content': response.content[0].text,
            'model': response.model,
            'usage': {
                'input_tokens': response.usage.input_tokens,
                'output_tokens': response.usage.output_tokens
            }
        }

    async def stream_completion(
        self,
        messages: List[Dict],
        system: str = None,
        model: str = None,
        max_tokens: int = 2048,
        temperature: float = 0.7
    ) -> AsyncGenerator[str, None]:
        """Stream completion tokens"""
        with self.client.messages.stream(
            model=model or self.default_model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=messages
        ) as stream:
            for text in stream.text_stream:
                yield text
```

### 9.2 Environment Variables

```bash
# .env
ANTHROPIC_API_KEY=sk-ant-your-key-here
ANTHROPIC_DEFAULT_MODEL=claude-sonnet-4-5-20250929
ANTHROPIC_MAX_TOKENS=4096
ANTHROPIC_TEMPERATURE=0.7
```

---

## 10. Neo4j Integration (Production Graph Database)

### 10.1 Overview

**Neo4j** is used in production as part of the dual-interface architecture:
- **Deployment**: Mac Studio Docker (Community Edition, FREE)
- **Purpose**: Knowledge graphs, entity relationships, graph traversal queries
- **Access Methods**:
  1. Direct Cypher queries from FastAPI services
  2. Neo4j MCP for natural language → Cypher translation (Claude Desktop/Code)
- **Integration**: Bi-directional sync with Supabase PostgreSQL

### 10.2 Configuration

```python
# app/integrations/neo4j_client.py

from neo4j import GraphDatabase
from typing import List, Dict, Optional
from app.config import Settings

class Neo4jClient:
    """Client for Neo4j graph database"""

    def __init__(self):
        settings = Settings()
        self.driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_username, settings.neo4j_password)
        )

    def close(self):
        """Close database connection"""
        self.driver.close()

    def execute_query(
        self,
        query: str,
        parameters: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Execute Cypher query and return results.

        Args:
            query: Cypher query string
            parameters: Query parameters

        Returns:
            List of result dictionaries
        """
        with self.driver.session() as session:
            result = session.run(query, parameters or {})
            return [record.data() for record in result]

    async def get_related_documents(
        self,
        entity_name: str,
        max_depth: int = 2
    ) -> List[Dict]:
        """
        Find documents related to an entity via graph traversal.

        Args:
            entity_name: Entity to search from
            max_depth: Maximum graph traversal depth

        Returns:
            Related documents with relationship paths
        """
        query = """
        MATCH path = (e:Entity {name: $entity_name})-[*1..$max_depth]-(d:Document)
        RETURN d.id as doc_id, d.title as title,
               length(path) as distance,
               [r in relationships(path) | type(r)] as relationship_types
        ORDER BY distance ASC
        LIMIT 20
        """

        return self.execute_query(
            query,
            {"entity_name": entity_name, "max_depth": max_depth}
        )

    async def get_entity_relationships(
        self,
        entity_id: str
    ) -> List[Dict]:
        """
        Get all relationships for a specific entity.

        Args:
            entity_id: Entity UUID

        Returns:
            List of related entities with relationship types
        """
        query = """
        MATCH (e:Entity {id: $entity_id})-[r]-(related:Entity)
        RETURN related.id as entity_id,
               related.name as entity_name,
               type(r) as relationship_type,
               r.strength as strength
        ORDER BY r.strength DESC
        """

        return self.execute_query(query, {"entity_id": entity_id})

    async def hybrid_search(
        self,
        query_text: str,
        vector_results: List[Dict],
        max_graph_depth: int = 2
    ) -> List[Dict]:
        """
        Enhance vector search results with graph traversal.

        Args:
            query_text: Original search query
            vector_results: Results from Supabase vector search
            max_graph_depth: Maximum graph traversal depth

        Returns:
            Enhanced results with graph-based related documents
        """
        # Extract document IDs from vector results
        doc_ids = [r['id'] for r in vector_results]

        # Find related documents via graph
        query = """
        MATCH (d:Document)
        WHERE d.id IN $doc_ids
        MATCH path = (d)-[*1..$max_depth]-(related:Document)
        WHERE NOT related.id IN $doc_ids
        RETURN DISTINCT related.id as doc_id,
               related.title as title,
               min(length(path)) as distance
        ORDER BY distance ASC
        LIMIT 10
        """

        graph_results = self.execute_query(
            query,
            {"doc_ids": doc_ids, "max_depth": max_graph_depth}
        )

        return {
            "vector_results": vector_results,
            "graph_related": graph_results
        }
```

### 10.3 Environment Variables

```bash
# .env
# Neo4j Configuration (Production)
NEO4J_URI=bolt+ssc://localhost:7687  # TLS enabled, or bolt+ssc://TAILSCALE_IP:7687 if remote
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=<your-secure-password>  # See .env file
NEO4J_DATABASE=neo4j
NEO4J_MAX_CONNECTION_POOL_SIZE=50
```

### 10.4 Docker Setup (Mac Studio)

```yaml
# docker-compose.yml (on Mac Studio)
version: '3.8'
services:
  neo4j:
    image: neo4j:5-community
    container_name: empire-neo4j
    ports:
      - "7474:7474"  # HTTP
      - "7687:7687"  # Bolt
    volumes:
      - ./neo4j/data:/data
      - ./neo4j/logs:/logs
      - ./neo4j/import:/import
      - ./neo4j/plugins:/plugins
    environment:
      - NEO4J_AUTH=neo4j/<your-secure-password>
      - NEO4J_PLUGINS=["apoc", "graph-data-science"]
      - NEO4J_dbms_memory_heap_initial__size=2g
      - NEO4J_dbms_memory_heap_max__size=4g
      # TLS Configuration
      - NEO4J_dbms_ssl_policy_bolt_enabled=true
      - NEO4J_dbms_ssl_policy_bolt_base__directory=/certificates/bolt
      - NEO4J_dbms_connector_bolt_tls__level=OPTIONAL
    restart: unless-stopped
```

### 10.5 Bi-directional Sync with Supabase

**Sync Strategy:**
- **Frequency**: 5-minute intervals via FastAPI background task
- **Direction**: Bi-directional (Supabase ↔ Neo4j)
- **Conflict Resolution**: Supabase as source of truth
- **Sync Data**: Entities, relationships, document metadata

```python
# app/services/graph_sync_service.py

from app.integrations.neo4j_client import Neo4jClient
from app.integrations.supabase_client import SupabaseClient

async def sync_entities_to_neo4j():
    """Sync entities from Supabase to Neo4j"""
    supabase = SupabaseClient()
    neo4j = Neo4jClient()

    # Get new/updated entities from Supabase
    entities = supabase.get_entities_for_sync()

    for entity in entities:
        # Create or update entity node in Neo4j
        neo4j.execute_query(
            """
            MERGE (e:Entity {id: $id})
            SET e.name = $name,
                e.type = $type,
                e.description = $description,
                e.updated_at = datetime()
            """,
            entity
        )

    neo4j.close()
```

### 10.6 Neo4j MCP for Natural Language Queries

**Purpose**: Enable Claude Desktop/Code to query Neo4j using natural language

**Example Queries:**
- "Show me all documents related to RAG optimization"
- "Find entities connected to the Empire project"
- "What documents mention both embeddings and reranking?"

**Setup**: See `claude.md` Section 2.3 for MCP configuration

---

## Summary Table

| Service | Purpose | Local/Cloud | Cost | Required |
|---------|---------|-------------|------|----------|
| Supabase | Database, Vector Storage | Cloud | Paid | ✅ Yes |
| Neo4j | Graph Database, Knowledge Graphs | Local (Mac Studio) | Free | ✅ Yes (Production) |
| Ollama | Embeddings (BGE-M3) | Local | Free | ✅ Yes |
| OpenAI | Embeddings (fallback) | Cloud | Paid | ⚠️ Optional |
| Backblaze B2 | Object Storage | Cloud | Paid | ✅ Yes |
| Redis | Caching, Queue | Local/Cloud | Free/Paid | ✅ Yes |
| Celery | Task Queue | - | Free | ✅ Yes |
| CrewAI | Multi-Agent | - | Free | ✅ Yes |
| BGE-Reranker-v2 | Reranking | Local (Mac Studio) | Free | ✅ Yes (Replaces Cohere) |
| Anthropic | LLM (Chat, Agents) | Cloud | Paid | ✅ Yes |

**Cost Optimization Strategy**: Use Ollama (free) for embeddings, Supabase (affordable) for database, B2 (cheapest) for storage.

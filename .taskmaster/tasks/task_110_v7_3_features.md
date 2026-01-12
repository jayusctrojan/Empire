# Task ID: 110

**Title:** Implement Redis Caching for Graph Queries

**Status:** pending

**Dependencies:** 104, 105, 106

**Priority:** medium

**Description:** Implement a caching layer using Redis to improve performance of graph queries by storing frequently accessed results.

**Details:**

Create a GraphQueryCache class in app/services/graph_query_cache.py that provides caching for graph query results:

```python
from typing import Dict, Any, Optional, List
import json
import hashlib
from redis import Redis

class GraphQueryCache:
    def __init__(self, redis_client: Redis, ttl: int = 3600):
        self.redis = redis_client
        self.default_ttl = ttl  # Default TTL in seconds
    
    async def get(self, query_type: str, query_key: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        # Generate cache key from query type and parameters
        cache_key = self._generate_cache_key(query_type, query_key)
        
        # Try to get from cache
        cached_result = self.redis.get(cache_key)
        if cached_result:
            return json.loads(cached_result)
        
        return None
    
    async def set(self, query_type: str, query_key: Dict[str, Any], 
                result: Dict[str, Any], ttl: Optional[int] = None) -> None:
        # Generate cache key and store result
        cache_key = self._generate_cache_key(query_type, query_key)
        self.redis.set(
            cache_key,
            json.dumps(result),
            ex=ttl or self.default_ttl
        )
    
    async def invalidate(self, query_type: str, query_key: Dict[str, Any]) -> None:
        # Invalidate specific cache entry
        cache_key = self._generate_cache_key(query_type, query_key)
        self.redis.delete(cache_key)
    
    async def invalidate_by_prefix(self, prefix: str) -> None:
        # Invalidate all cache entries with given prefix
        keys = self.redis.keys(f"{prefix}:*")
        if keys:
            self.redis.delete(*keys)
    
    def _generate_cache_key(self, query_type: str, query_key: Dict[str, Any]) -> str:
        # Generate deterministic cache key from query type and parameters
        key_str = json.dumps(query_key, sort_keys=True)
        hashed = hashlib.md5(key_str.encode()).hexdigest()
        return f"graph:{query_type}:{hashed}"
```

Integrate this cache with the graph agent services (Customer360Service, DocumentStructureService, GraphEnhancedRAGService) to cache query results. Implement cache invalidation strategies for data updates.

**Test Strategy:**

1. Unit tests for cache key generation
2. Test cache hit/miss scenarios
3. Test cache invalidation
4. Integration tests with graph services
5. Performance tests to measure cache impact
6. Test with concurrent access patterns
7. Test cache size growth over time

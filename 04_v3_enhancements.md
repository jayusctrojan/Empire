# 4. Version 3.0 Enhancements (Enhanced for v5.0 Mac Studio)

## IMPORTANT: Version 7.2 Supersedes This Document

**Version 7.2** represents a revolutionary architectural evolution that supersedes v3.0 enhancements with:

### v7.2 NEW - Dual-Interface Architecture
- **Neo4j Graph Database:** FREE on Mac Studio Docker (10-100x faster relationship queries)
- **Neo4j MCP Server:** Direct Claude Desktop/Code integration with natural language → Cypher
- **Chat UI Interface:** Gradio/Streamlit for end-user access (Render deployment)
- **Bi-directional Sync:** Automatic Supabase ↔ Neo4j synchronization
- **Graph Traversal:** Multi-hop pathfinding, community detection, centrality analysis
- **Semantic Entity Resolution:** ML-based deduplication

### v7.1 MAINTAINED - State-of-the-Art RAG
- **BGE-M3 Embeddings:** 1024-dim vectors with built-in sparse (3-5% quality improvement)
- **Query Expansion:** Claude Haiku generates 4-5 variations (15-30% better recall)
- **BGE-Reranker-v2:** Local reranking on Mac Studio replacing Cohere ($30-50/month savings)
- **Adaptive Chunking:** Document-type-aware (15-25% better precision)
- **Tiered Caching:** 0.98+ direct hit, 0.93-0.97 similar answer thresholds
- **Performance:** 40-60% better retrieval quality with hybrid vector + graph search
- **Cost:** $350-500/month (includes both Chat UI and Neo4j MCP, Neo4j free)

For current implementation guidance, refer to **Section 3 (Specific Requirements)** and **Sections 7-10** for v7.2 details.

---

## 4.1 Parallel Processing Engine

### 4.1.1 Architecture Overview

The parallel processing engine enables simultaneous processing of multiple documents, significantly reducing overall processing time and improving system throughput.

**Core Components:**
- **Worker Pool Manager:** Manages concurrent processing workers (10 in v5.0, up from 5)
- **Task Queue:** Priority-based queue for document processing with intelligent routing
- **Load Balancer:** Distributes work based on document complexity and resource availability
- **Resource Monitor:** Tracks CPU (28-core), memory (96GB), GPU (60-core), and API usage
- **Orchestration Layer:** n8n workflows coordinate between local and cloud resources

### 4.1.2 Parallel Processing Requirements (Enhanced v5.0)

**PFR-001:** The system SHALL process up to 10 concurrent workflows

*Priority: Essential*
*Note: v5.0 - Increased from 5 to 10 with Mac Studio M3 Ultra (96GB)*
*Verification: Load Testing*
*Status: Enhanced - v5.0*

**PFR-002:** The system SHALL implement intelligent queue management with priority levels:
- Critical: Immediate processing (bypass queue)
- High: Process within 5 minutes
- Normal: Process within 15 minutes
- Low: Process when resources available

*Priority: Essential*
*Note: Queue managed by n8n orchestration*
*Status: Active - All Versions*

**PFR-003:** The system SHALL dynamically allocate resources based on document complexity scores

*Priority: High*
*Note: v5.0 - Allocation considers local vs cloud processing*
*Status: Active - All Versions*

**PFR-004:** The system SHALL provide real-time progress tracking for all parallel jobs via WebSocket

*Priority: High*
*Status: Active - All Versions*

**PFR-005:** The system SHALL implement load balancing across n8n workflow nodes

*Priority: Essential*
*Note: v5.0 - n8n nodes distribute work across local and cloud resources*
*Algorithm: Weighted distribution based on resource availability*
*Status: Updated - v5.0*

**PFR-006:** The system SHALL detect and handle resource contention:
- CPU threshold: 60% (Mac Studio has 28 cores)
- Memory threshold: 70% (65GB for models, 31GB buffer)
- GPU threshold: 70% (60-core GPU monitoring)
- Disk I/O threshold: 80%
- Network throughput: 50% of available bandwidth

*Priority: Essential*
*Note: v5.0 - Thresholds optimized for Mac Studio resources*
*Status: Enhanced - v5.0*

### 4.1.3 Performance Metrics

**Target Performance Improvements:**
- **Throughput Improvement:** 3-5x for batch processing
- **Latency Reduction:** 50% for average document
- **Resource Efficiency:** 80% CPU utilization target
- **Queue Time:** <10 seconds for priority documents
- **Concurrent Processing:** 10 workflows (v5.0, up from 5)
- **Local Processing Ratio:** 98% (v5.0 target)

### 4.1.4 Implementation Architecture (v5.0)

```javascript
// Enhanced Parallel Processing Configuration for Mac Studio
const parallelConfig = {
  maxWorkflows: 10,  // Increased from 5
  
  // Worker Pool Components
  workerPool: {
    manager: 'n8n-orchestrator',
    workers: 10,
    taskQueue: 'priority-based',
    loadBalancer: 'complexity-weighted',
    resourceMonitor: 'prometheus-metrics'
  },
  
  // n8n orchestration nodes
  orchestrationNodes: {
    documentProcessor: { maxConcurrent: 5 },
    llmInference: { maxConcurrent: 3 },  // Llama 70B intensive
    visionProcessing: { maxConcurrent: 2 },  // Qwen-VL intensive
    embeddingGeneration: { maxConcurrent: 10 },  // nomic-embed lightweight
    webScraping: { maxConcurrent: 5 }  // Firecrawl cloud-based
  },
  
  queuePriorities: {
    critical: { weight: 1000, timeout: 0 },
    high: { weight: 100, timeout: 300 },
    normal: { weight: 10, timeout: 900 },
    low: { weight: 1, timeout: null }
  },
  
  // Mac Studio specific thresholds
  resourceThresholds: {
    cpu: 0.60,  // 28-core CPU
    memory: 0.70,  // 96GB total, 65GB models, 31GB available
    gpu: 0.70,  // 60-core GPU
    diskIO: 0.80,
    networkBandwidth: 0.50  // 10Gb Ethernet
  },
  
  loadBalancing: {
    algorithm: 'intelligent_routing',
    localFirst: true,  // Prioritize Mac Studio processing
    cloudFallback: 'hyperbolic.ai',  // Edge cases only
    healthCheckInterval: 30000
  }
};
```

### 4.1.5 GPU Utilization Monitoring (NEW v5.0)

**GPU-001:** The system SHALL monitor Mac Studio GPU utilization

*Priority: Essential*
*Hardware: 60-core GPU, 32-core Neural Engine*
*Metrics: Usage %, temperature, memory bandwidth*
*Status: New - v5.0*

**GPU-002:** The system SHALL optimize GPU scheduling for AI workloads:
- LLM inference: Priority 1 (Llama 70B)
- Vision processing: Priority 2 (Qwen-VL)
- Embedding generation: Priority 3 (nomic-embed)

*Priority: High*
*Status: New - v5.0*

**GPU-003:** The system SHALL leverage Metal Performance Shaders for optimization

*Priority: High*
*Purpose: Maximize inference speed on Apple Silicon*
*Status: New - v5.0*

## 4.2 Semantic Chunking System (Enhanced v5.0)

### 4.2.1 Intelligent Segmentation

The semantic chunking system creates context-aware document segments that preserve meaning and improve retrieval accuracy.

**Core Features:**
- **Context Preservation:** Maintains semantic boundaries
- **Overlap Management:** Configurable overlap between chunks (10-30%)
- **Size Optimization:** Dynamic chunk sizing (512-2048 tokens)
- **Quality Scoring:** Coherence and completeness metrics (0-100 scale)

### 4.2.2 Chunking Strategies

**QFR-001: Sentence-Level Chunking**
- Respect sentence boundaries
- Maintain paragraph context
- Preserve list structures
- Handle code blocks specially

*Priority: Essential*
*Status: Active - All Versions*

**QFR-002: Topic-Based Chunking**
- Identify topic transitions using Llama 70B (v5.0)
- Group related content semantically
- Maintain heading hierarchy
- Preserve section integrity

*Priority: High*
*Note: v5.0 - Enhanced with local LLM analysis*
*Status: Enhanced - v5.0*

**QFR-003: Hybrid Chunking**
- Combine sentence and topic strategies
- Adapt based on document type
- Optimize for retrieval performance
- Balance chunk size and coherence

*Priority: High*
*Status: Active - All Versions*

### 4.2.3 Semantic Chunking Requirements

**PFR-007:** The system SHALL implement semantic boundary detection using:
- Sentence completion analysis
- Paragraph coherence scoring
- Topic shift detection
- Header hierarchy respect
- Local Llama 70B for boundary validation (v5.0)

*Priority: Essential*
*Note: v5.0 - Enhanced with local LLM for better boundary detection*
*Status: Enhanced - v5.0*

**PFR-008:** The system SHALL dynamically adjust chunk size based on content type:
- Technical documentation: 1500-2000 tokens
- Narrative content: 800-1200 tokens
- Tabular data: 2000-2500 tokens
- Mixed content: 1000-1500 tokens
- Code blocks: Preserve complete functions/classes (v5.0)

*Priority: High*
*Note: v5.0 - Added code-aware chunking*
*Status: Enhanced - v5.0*

**PFR-009:** The system SHALL calculate semantic density scores for each chunk:

```json
{
  "chunk_id": "uuid",
  "semantic_density": 0.85,
  "information_entropy": 0.72,
  "keyword_concentration": 0.68,
  "readability_score": 0.90,
  "coherence_score": 0.88,  // Semantic unity measure
  "completeness_score": 0.92,  // Information preservation
  "relevance_score": 0.87,  // Alignment with document theme
  "size_score": 0.90,  // Optimization for embedding model
  "llm_coherence_score": 0.93,  // v5.0 - Llama 70B assessment
  "processing_location": "mac_studio"  // v5.0 - Track where processed
}
```

*Priority: Medium*
*Status: Enhanced - v5.0*

**PFR-010:** The system SHALL optimize chunk overlap to preserve context:
- Minimum overlap: 10% of chunk size
- Maximum overlap: 30% of chunk size
- Semantic similarity threshold: 0.7
- LLM-validated boundaries (v5.0)

*Priority: High*
*Status: Enhanced - v5.0*

## 4.3 Quality Monitoring Framework

### 4.3.1 Real-Time Monitoring

**MFR-001: Processing Metrics**
- Document processing rate (docs/hour)
- Error rate by document type (%)
- Average processing time (seconds)
- Queue depth and wait time (count/seconds)
- Token generation speed (tok/s) - v5.0

*Priority: Essential*
*Status: Enhanced - v5.0*

**MFR-002: Quality Metrics**
- Extraction accuracy scores (0-100)
- Chunking quality metrics (0-100)
- Embedding quality indicators
- Retrieval relevance scores
- LLM validation scores (v5.0)

*Priority: Essential*
*Status: Enhanced - v5.0*

**MFR-003: System Metrics**
- CPU and memory utilization (%)
- GPU utilization (%) - v5.0
- API call rates and costs ($)
- Storage consumption (GB)
- Network bandwidth usage (Mbps)
- Local vs cloud processing ratio (%) - v5.0

*Priority: Essential*
*Status: Enhanced - v5.0*

### 4.3.2 Progressive Quality Improvement

**MFR-004: Feedback Loop**
- Collect quality metrics continuously
- Identify patterns in failures
- Adjust processing parameters
- Retrain quality models
- Optimize local processing paths (v5.0)

*Priority: High*
*Status: Enhanced - v5.0*

**MFR-005: A/B Testing Framework**
- Test processing variations
- Measure quality improvements
- Automatic winner selection (statistical significance)
- Gradual rollout of improvements (10% → 50% → 100%)
- Compare local vs cloud processing quality (v5.0)

*Priority: Medium*
*Note: Valuable for continuous improvement*
*Status: New - v5.0*

### 4.3.3 Quality Monitoring Requirements

**QFR-001:** The system SHALL calculate quality scores for all processed content:

```json
{
  "overall_quality": 0.92,
  "extraction_completeness": 0.95,
  "format_preservation": 0.89,
  "metadata_accuracy": 0.94,
  "chunking_quality": 0.91,
  "llm_validation_score": 0.96,  // v5.0 - Llama 70B validation
  "local_processing_ratio": 0.98  // v5.0 - % processed locally
}
```

*Priority: Essential*
*Status: Enhanced - v5.0*

**QFR-002:** The system SHALL implement automated quality gates:
- Minimum quality score: 0.75
- Action on failure: Reprocess with alternative method
- Maximum reprocess attempts: 3
- Local reprocessing preferred (v5.0)

*Priority: High*
*Status: Enhanced - v5.0*

**QFR-003:** The system SHALL detect processing anomalies:
- Processing time deviation > 50%
- Error rate > 5%
- Quality score < 0.70
- Memory usage spike > 30%
- Token generation speed < 25 tok/s (v5.0 - Llama 70B monitoring)
- GPU utilization spike > 90% (v5.0)

*Priority: High*
*Status: Enhanced - v5.0*

**QFR-004:** The system SHALL generate quality trend reports:
- Daily quality summary
- Weekly trend analysis
- Monthly performance report
- Quarterly optimization recommendations
- Local vs cloud processing analytics (v5.0)

*Priority: Medium*
*Status: Enhanced - v5.0*

## 4.4 Advanced Caching Architecture (Redesigned v5.0)

### 4.4.1 Three-Tier Cache System

**Tier 1: Memory Cache (Mac Studio)**
- **Size:** 31GB dedicated (from 96GB total)
- **TTL:** 1 hour default (adaptive based on usage)
- **Content:** Hot data and frequent queries
- **Performance:** <10ms access time
- **Hit Rate Target:** >90% for frequent operations

**Tier 2: SSD Cache (Mac Studio)**
- **Size:** 100GB allocated
- **TTL:** 24 hours default
- **Content:** Recent documents and embeddings
- **Performance:** <50ms access time
- **Compression:** 3:1 ratio for efficiency

**Tier 3: Disk Cache & Course Organization (Backblaze B2 - v7.2 Enhanced)**
- **Size:** Unlimited with versioning
- **TTL:** Permanent with lifecycle rules
- **Content:** All processed documents, results, and organized courses
- **Performance:** <500ms access time
- **Encryption:** Client-side AES-256
- **NEW v7.2 Features:**
  - 10-department taxonomy with AI-powered classification
  - Dual upload architecture (Mountain Duck + Web UI)
  - Intelligent filename generation with module/lesson structure
  - CrewAI summaries and suggestions folders

### 4.4.2 Cache Management

**PFR-011:** The system SHALL implement three-tier caching:
- L1 Cache (Mac Studio Memory): 31GB available, TTL: adaptive
- L2 Cache (Mac Studio SSD): 100GB, TTL: 24 hours
- L3 Cache (Backblaze B2): Unlimited, TTL: permanent with versioning
  - v7.2 Enhanced: Includes 10-dept course organization, AI classification, dual upload

*Priority: Essential*
*Note: v5.0 - Optimized for Mac Studio architecture*
*Status: Redesigned - v5.0*

**PFR-012:** The system SHALL implement intelligent cache invalidation:

```javascript
{
  "invalidation_triggers": [
    "document_update",
    "hash_change",
    "ttl_expiry",
    "manual_purge",
    "model_update"  // v5.0 - When Llama/Qwen models updated
  ],
  "cascade_invalidation": true,
  "preserve_hot_cache": true,
  "local_cache_priority": true  // v5.0 - Keep frequently used local
}
```

*Priority: High*
*Status: Enhanced - v5.0*

**PFR-013:** The system SHALL preemptively warm cache for:
- Frequently accessed documents (>10 accesses/day)
- Recently modified documents (<24 hours)
- High-priority user documents
- Memory-related content (v5.0 - mem-agent integration)

*Priority: Medium*
*Status: Enhanced - v5.0*

**PFR-014:** The system SHALL maintain minimum 80% cache hit rate

*Priority: High*
*Note: v5.0 - Increased from 60% due to 31GB local cache*
*Status: Enhanced - v5.0*

### 4.4.3 Cache Optimization

**PFR-015: Cache Coordination**
- Hierarchical cache lookup (L1 → L2 → L3)
- Write-through for critical data
- Write-back for bulk operations
- Cache invalidation protocols

*Priority: Essential*
*Status: Active - All Versions*

**PFR-016: Cache Optimization Features**
- LRU eviction policy with priority weighting
- Predictive prefetching based on usage patterns
- Compression for large objects (3:1 ratio)
- Deduplication across tiers
- Local-first caching strategy (v5.0)

*Priority: High*
*Status: Enhanced - v5.0*

### 4.4.4 Performance Impact

- **Cache Hit Rate:** >80% for frequent operations
- **Latency Reduction:** 90% for cached content
- **API Cost Savings:** 40% reduction (increased to 95% in v5.0)
- **Storage Efficiency:** 3:1 compression ratio
- **Local Cache Benefit:** <10ms access for 31GB hot data (v5.0)

## 4.5 Token Generation Speed Tracking (NEW v5.0)

**TGS-001:** The system SHALL monitor LLM token generation speed

*Priority: Essential*
*Target: 32 tokens/second for Llama 70B*
*Alert: If speed drops below 25 tok/s*
*Status: New - v5.0*

**TGS-002:** The system SHALL track token usage by model:
- Llama 3.3 70B: Primary reasoning (track tok/s, total tokens)
- Qwen2.5-VL: Vision tasks (track image processing time)
- nomic-embed: Embeddings (track vectors/second)

*Priority: High*
*Status: New - v5.0*

**TGS-003:** The system SHALL optimize token throughput:
- Batch similar requests
- Preload frequently used prompts
- Cache common responses
- Adaptive temperature settings

*Priority: Medium*
*Status: New - v5.0*

## 4.6 Enhanced Monitoring Requirements (v5.0)

### 4.6.1 Comprehensive Metrics Collection

**MFR-001:** The system SHALL collect real-time metrics:

```yaml
metrics:
  processing:
    - documents_processed_total
    - processing_duration_seconds
    - processing_errors_total
    - concurrent_workflows_count  # v5.0 - Up to 10
    - n8n_node_execution_time  # v5.0 - Per node metrics
    
  performance:
    - cpu_usage_percent  # 28-core monitoring
    - memory_usage_bytes  # 96GB total
    - gpu_usage_percent  # 60-core GPU
    - neural_engine_usage  # 32-core Neural Engine
    - disk_io_operations
    - network_throughput_bytes
    
  ai_models:  # v5.0 NEW
    - llama_tokens_per_second
    - llama_total_tokens_generated
    - qwen_images_processed
    - qwen_processing_time_seconds
    - nomic_embeddings_generated
    - bge_reranking_operations
    
  quality:
    - quality_score_average
    - chunks_created_total
    - embeddings_generated_total
    - cache_hit_ratio  # Target: 80%+
    - local_processing_ratio  # Target: 98%+
    
  cost:  # v5.0 NEW
    - cloud_api_calls_count
    - cloud_api_cost_dollars
    - local_inference_count
    - estimated_savings_dollars
```

*Priority: Essential*
*Note: Prometheus compatible metrics*
*Status: Enhanced - v5.0*

**MFR-002:** The system SHALL implement alerting rules:
- Critical: System down, data loss risk, Mac Studio offline
- High: Performance degradation >30%, Token speed <20 tok/s
- Medium: Quality scores declining, Cache hit rate <70%
- Low: Maintenance reminders, Model updates available

*Priority: Essential*
*Status: Enhanced - v5.0*

**MFR-003:** The system SHALL provide real-time dashboards via Grafana:
- System health overview
- Mac Studio resource utilization
- LLM performance metrics (tok/s, queue depth)
- n8n workflow status
- Processing pipeline visualization
- Quality metrics display
- Performance trends
- Error analysis
- Cost savings tracker (v5.0)

*Priority: High*
*Note: Grafana stack to be evaluated for Mac-specific metrics*
*Status: Enhanced - v5.0*

**MFR-004:** The system SHALL log all operations with correlation IDs for distributed tracing

*Priority: Essential*
*Note: Trace across Mac Studio and cloud services*
*Status: Active - All Versions*

### 4.6.2 Model Management Monitoring (NEW v5.0)

**MMM-001:** The system SHALL monitor Ollama model status:
- Model loading time
- Model memory usage
- Model switching frequency
- Available model list

*Priority: High*
*Status: New - v5.0*

**MMM-002:** The system SHALL track model performance by task:
- Reasoning tasks → Llama 70B performance
- Vision tasks → Qwen-VL performance
- Embedding tasks → nomic-embed performance

*Priority: Medium*
*Status: New - v5.0*

**MMM-003:** The system SHALL alert on model issues:
- Model load failure
- Performance degradation
- Memory pressure
- Context window overflow

*Priority: High*
*Status: New - v5.0*

## 4.7 Enhanced Error Recovery Requirements

### 4.7.1 Error Recovery Mechanisms

**PFR-017:** The system SHALL implement exponential backoff retry:

```javascript
{
  "initial_delay": 1000,
  "multiplier": 2,
  "max_delay": 30000,
  "max_attempts": 5,
  "jitter": true,
  "local_retry_first": true  // v5.0 - Try local before cloud
}
```

*Priority: Essential*
*Status: Enhanced - v5.0*

**PFR-018:** The system SHALL implement circuit breaker pattern:
- Failure threshold: 5 failures in 60 seconds
- Circuit open duration: 30 seconds
- Half-open test interval: 10 seconds
- Separate circuits for local and cloud services (v5.0)

*Priority: High*
*Status: Enhanced - v5.0*

**PFR-019:** The system SHALL maintain dead letter queue for failed messages:
- Maximum retention: 30 days
- Manual inspection interface
- Replay capability
- Batch retry option
- Local storage on Mac Studio (v5.0)

*Priority: High*
*Status: Enhanced - v5.0*

**PFR-020:** The system SHALL automatically fallback to alternative processors:
- Primary (Local Llama 70B) → Secondary (Hyperbolic.ai)
- Primary (Local Qwen-VL) → Secondary (Cloud vision API)
- Primary (Local embed) → Secondary (Cloud embeddings)
- All failures → Manual review queue

*Priority: Essential*
*Note: v5.0 - Local processing primary, cloud as fallback*
*Status: Enhanced - v5.0*

## 4.8 Local Processing Optimization (NEW v5.0)

### 4.8.1 Local-First Processing Strategy

**LPO-001:** The system SHALL prioritize local processing:
- Sensitive documents: 100% local mandatory
- Complex reasoning: Local Llama 70B preferred
- Vision tasks: Local Qwen2.5-VL preferred
- Embeddings: Local nomic-embed always
- Reranking: Local BGE-reranker primary

*Priority: Essential*
*Target: 98% local processing ratio*
*Status: New - v5.0*

**LPO-002:** The system SHALL monitor local processing efficiency:
- Local inference percentage: Target 98%
- Cloud API calls: Target <2% of operations
- Fallback frequency: Track and minimize
- Cost tracking: Target <$10/month cloud LLM

*Priority: High*
*Status: New - v5.0*

**LPO-003:** The system SHALL implement intelligent model switching:

```javascript
{
  "model_selection": {
    "reasoning": {
      "primary": "llama-3.3:70b",
      "fallback": "hyperbolic-deepseek-v3",
      "switch_conditions": ["local_unavailable", "timeout", "memory_pressure"]
    },
    "vision": {
      "primary": "qwen2.5-vl:7b",
      "fallback": "hyperbolic-qwen-vl",
      "switch_conditions": ["gpu_overload", "batch_size_exceeded"]
    },
    "embeddings": {
      "primary": "nomic-embed-text",
      "fallback": null,  // Always local
      "switch_conditions": []
    }
  },
  "switch_threshold": {
    "latency": 5000,  // ms
    "error_rate": 0.05,
    "queue_depth": 10
  }
}
```

*Priority: High*
*Status: New - v5.0*

**LPO-004:** The system SHALL optimize Mac Studio resource usage:
- Memory allocation: Reserve 65GB for models, 31GB for operations
- CPU scheduling: Balance across 28 cores
- GPU scheduling: Prioritize inference tasks
- SSD caching: Hot data on fastest storage

*Priority: Essential*
*Status: New - v5.0*

## 4.9 Performance Targets Summary (v5.0)

| Metric | v3.0 Target | v5.0 Target | Improvement |
|--------|-------------|-------------|-------------|
| Concurrent Processing | 5 documents | 10 workflows | 2x increase |
| Cache Hit Rate | 60% | 80% | 33% improvement |
| Local Processing | N/A | 98% | New capability |
| LLM Speed | Variable (API) | 32 tok/s | Consistent local |
| Quality Score | 0.75 minimum | 0.75 minimum | Maintained |
| Error Recovery | 3 attempts | 5 attempts | More resilient |
| Cache Size (L1) | 1GB | 31GB | 31x increase |
| GPU Monitoring | None | Full metrics | New capability |
| Cost Optimization | None | <$10/mo cloud | 95% reduction |
| Throughput | 2x batch | 3-5x batch | 50-150% improvement |
| Latency Reduction | 30% | 50% | 67% improvement |
| Queue Time | <30s | <10s priority | 3x faster |

## 4.10 Implementation Notes

1. **Prometheus/Grafana Stack:** To be evaluated for Mac-specific metrics integration
2. **n8n Orchestration:** Workflow nodes handle distribution instead of traditional workers
3. **Local Priority:** All enhancements prioritize Mac Studio local processing
4. **Backward Compatibility:** v3.0 features maintained while adding v5.0 optimizations
5. **A/B Testing:** Framework enables continuous improvement through data-driven decisions
6. **Worker Pool:** Managed by n8n with intelligent task distribution based on complexity
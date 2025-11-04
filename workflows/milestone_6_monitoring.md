# Milestone 6: Monitoring and Observability

**Purpose**: Implement comprehensive monitoring, health checks, logging, and alerting for the Empire document processing system.

**Key Technologies**:
- Prometheus for metrics collection
- Grafana for visualization
- Python `logging` module with structured logging
- FastAPI health check endpoints
- Custom metrics for document processing pipeline
- Redis for metrics aggregation

**Architecture**:
- Prometheus metrics exposure via `/metrics` endpoint
- Health checks for all dependencies (Supabase, Redis, Ollama, B2)
- Structured JSON logging to files and stdout
- Performance metrics for all processing stages
- Alert rules for critical failures

---

## 6.1 Supabase Schema - Monitoring Tables

```sql
-- ============================================================================
-- Milestone 6: Monitoring Schema
-- ============================================================================

-- System metrics table
CREATE TABLE IF NOT EXISTS public.system_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    metric_name VARCHAR(100) NOT NULL,
    metric_value DECIMAL(15, 4) NOT NULL,
    metric_type VARCHAR(50) NOT NULL, -- 'counter', 'gauge', 'histogram'
    labels JSONB DEFAULT '{}',
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for system_metrics
CREATE INDEX IF NOT EXISTS idx_system_metrics_name ON public.system_metrics(metric_name);
CREATE INDEX IF NOT EXISTS idx_system_metrics_timestamp ON public.system_metrics(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_system_metrics_type ON public.system_metrics(metric_type);

-- Processing logs table
CREATE TABLE IF NOT EXISTS public.processing_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    log_level VARCHAR(20) NOT NULL, -- 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
    logger_name VARCHAR(100) NOT NULL,
    message TEXT NOT NULL,
    document_id VARCHAR(64),
    user_id VARCHAR(100),
    session_id VARCHAR(255),
    function_name VARCHAR(100),
    line_number INTEGER,
    exception_type VARCHAR(100),
    exception_message TEXT,
    stack_trace TEXT,
    metadata JSONB DEFAULT '{}',
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for processing_logs
CREATE INDEX IF NOT EXISTS idx_processing_logs_level ON public.processing_logs(log_level);
CREATE INDEX IF NOT EXISTS idx_processing_logs_timestamp ON public.processing_logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_processing_logs_document ON public.processing_logs(document_id);
CREATE INDEX IF NOT EXISTS idx_processing_logs_logger ON public.processing_logs(logger_name);

-- Health check status table
CREATE TABLE IF NOT EXISTS public.health_checks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    service_name VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL, -- 'healthy', 'degraded', 'unhealthy'
    response_time_ms INTEGER,
    error_message TEXT,
    metadata JSONB DEFAULT '{}',
    checked_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for health_checks
CREATE INDEX IF NOT EXISTS idx_health_checks_service ON public.health_checks(service_name);
CREATE INDEX IF NOT EXISTS idx_health_checks_status ON public.health_checks(status);
CREATE INDEX IF NOT EXISTS idx_health_checks_checked_at ON public.health_checks(checked_at DESC);

-- Performance metrics table (for detailed pipeline metrics)
CREATE TABLE IF NOT EXISTS public.performance_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    operation_type VARCHAR(100) NOT NULL, -- 'upload', 'extraction', 'embedding', 'search', 'chat'
    document_id VARCHAR(64),
    duration_ms INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL, -- 'success', 'failure', 'timeout'
    file_size_bytes BIGINT,
    chunk_count INTEGER,
    token_count INTEGER,
    error_message TEXT,
    metadata JSONB DEFAULT '{}',
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for performance_metrics
CREATE INDEX IF NOT EXISTS idx_perf_metrics_operation ON public.performance_metrics(operation_type);
CREATE INDEX IF NOT EXISTS idx_perf_metrics_status ON public.performance_metrics(status);
CREATE INDEX IF NOT EXISTS idx_perf_metrics_started_at ON public.performance_metrics(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_perf_metrics_document ON public.performance_metrics(document_id);

-- Alert rules table
CREATE TABLE IF NOT EXISTS public.alert_rules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    rule_name VARCHAR(100) UNIQUE NOT NULL,
    rule_type VARCHAR(50) NOT NULL, -- 'threshold', 'rate', 'pattern'
    condition JSONB NOT NULL, -- JSON condition definition
    severity VARCHAR(20) NOT NULL, -- 'info', 'warning', 'critical'
    notification_channels JSONB DEFAULT '[]', -- ['email', 'slack', 'webhook']
    is_active BOOLEAN DEFAULT true,
    cooldown_minutes INTEGER DEFAULT 15,
    last_triggered_at TIMESTAMPTZ,
    trigger_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Alert history table
CREATE TABLE IF NOT EXISTS public.alert_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    rule_id UUID NOT NULL REFERENCES alert_rules(id) ON DELETE CASCADE,
    rule_name VARCHAR(100) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    alert_message TEXT NOT NULL,
    context JSONB DEFAULT '{}',
    resolved BOOLEAN DEFAULT false,
    resolved_at TIMESTAMPTZ,
    triggered_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for alert_history
CREATE INDEX IF NOT EXISTS idx_alert_history_rule ON public.alert_history(rule_id);
CREATE INDEX IF NOT EXISTS idx_alert_history_severity ON public.alert_history(severity);
CREATE INDEX IF NOT EXISTS idx_alert_history_triggered ON public.alert_history(triggered_at DESC);
CREATE INDEX IF NOT EXISTS idx_alert_history_resolved ON public.alert_history(resolved) WHERE NOT resolved;

-- ============================================================================
-- Functions for Metrics and Monitoring
-- ============================================================================

-- Function: Get system health summary
CREATE OR REPLACE FUNCTION get_system_health_summary()
RETURNS TABLE (
    service_name VARCHAR(100),
    status VARCHAR(20),
    avg_response_time_ms DECIMAL(10, 2),
    last_check TIMESTAMPTZ,
    uptime_percentage DECIMAL(5, 2)
) AS $$
BEGIN
    RETURN QUERY
    WITH recent_checks AS (
        SELECT
            hc.service_name,
            hc.status,
            hc.response_time_ms,
            hc.checked_at,
            ROW_NUMBER() OVER (PARTITION BY hc.service_name ORDER BY hc.checked_at DESC) AS rn
        FROM health_checks hc
        WHERE hc.checked_at > NOW() - INTERVAL '1 hour'
    ),
    latest_status AS (
        SELECT
            rc.service_name,
            rc.status,
            rc.checked_at
        FROM recent_checks rc
        WHERE rc.rn = 1
    ),
    service_stats AS (
        SELECT
            rc.service_name,
            AVG(rc.response_time_ms)::DECIMAL(10, 2) AS avg_response_time,
            (COUNT(*) FILTER (WHERE rc.status = 'healthy')::DECIMAL / COUNT(*)::DECIMAL * 100)::DECIMAL(5, 2) AS uptime_pct
        FROM recent_checks rc
        GROUP BY rc.service_name
    )
    SELECT
        ls.service_name,
        ls.status,
        COALESCE(ss.avg_response_time, 0) AS avg_response_time_ms,
        ls.checked_at AS last_check,
        COALESCE(ss.uptime_pct, 0) AS uptime_percentage
    FROM latest_status ls
    LEFT JOIN service_stats ss ON ls.service_name = ss.service_name
    ORDER BY ls.service_name;
END;
$$ LANGUAGE plpgsql;

-- Function: Get processing performance stats
CREATE OR REPLACE FUNCTION get_processing_stats(
    p_operation_type VARCHAR(100) DEFAULT NULL,
    p_time_window INTERVAL DEFAULT '1 hour'
)
RETURNS TABLE (
    operation VARCHAR(100),
    total_operations BIGINT,
    success_count BIGINT,
    failure_count BIGINT,
    success_rate DECIMAL(5, 2),
    avg_duration_ms DECIMAL(10, 2),
    p50_duration_ms DECIMAL(10, 2),
    p95_duration_ms DECIMAL(10, 2),
    p99_duration_ms DECIMAL(10, 2)
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        pm.operation_type AS operation,
        COUNT(*)::BIGINT AS total_operations,
        COUNT(*) FILTER (WHERE pm.status = 'success')::BIGINT AS success_count,
        COUNT(*) FILTER (WHERE pm.status = 'failure')::BIGINT AS failure_count,
        (COUNT(*) FILTER (WHERE pm.status = 'success')::DECIMAL / COUNT(*)::DECIMAL * 100)::DECIMAL(5, 2) AS success_rate,
        AVG(pm.duration_ms)::DECIMAL(10, 2) AS avg_duration_ms,
        PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY pm.duration_ms)::DECIMAL(10, 2) AS p50_duration_ms,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY pm.duration_ms)::DECIMAL(10, 2) AS p95_duration_ms,
        PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY pm.duration_ms)::DECIMAL(10, 2) AS p99_duration_ms
    FROM performance_metrics pm
    WHERE
        pm.started_at > NOW() - p_time_window
        AND (p_operation_type IS NULL OR pm.operation_type = p_operation_type)
    GROUP BY pm.operation_type
    ORDER BY total_operations DESC;
END;
$$ LANGUAGE plpgsql;

-- Function: Get error rate by logger
CREATE OR REPLACE FUNCTION get_error_rates(
    p_time_window INTERVAL DEFAULT '1 hour'
)
RETURNS TABLE (
    logger VARCHAR(100),
    total_logs BIGINT,
    error_count BIGINT,
    warning_count BIGINT,
    error_rate DECIMAL(5, 2),
    recent_errors TEXT[]
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        pl.logger_name AS logger,
        COUNT(*)::BIGINT AS total_logs,
        COUNT(*) FILTER (WHERE pl.log_level = 'ERROR')::BIGINT AS error_count,
        COUNT(*) FILTER (WHERE pl.log_level = 'WARNING')::BIGINT AS warning_count,
        (COUNT(*) FILTER (WHERE pl.log_level = 'ERROR')::DECIMAL / NULLIF(COUNT(*)::DECIMAL, 0) * 100)::DECIMAL(5, 2) AS error_rate,
        ARRAY_AGG(
            pl.message
            ORDER BY pl.timestamp DESC
        ) FILTER (WHERE pl.log_level = 'ERROR')[:5] AS recent_errors
    FROM processing_logs pl
    WHERE pl.timestamp > NOW() - p_time_window
    GROUP BY pl.logger_name
    HAVING COUNT(*) FILTER (WHERE pl.log_level = 'ERROR') > 0
    ORDER BY error_count DESC;
END;
$$ LANGUAGE plpgsql;

-- Function: Check and trigger alerts
CREATE OR REPLACE FUNCTION check_alert_conditions()
RETURNS TABLE (
    rule_name VARCHAR(100),
    triggered BOOLEAN,
    alert_message TEXT
) AS $$
DECLARE
    rule RECORD;
    should_trigger BOOLEAN;
    alert_msg TEXT;
BEGIN
    FOR rule IN
        SELECT * FROM alert_rules
        WHERE is_active = true
        AND (last_triggered_at IS NULL OR last_triggered_at < NOW() - INTERVAL '1 minute' * cooldown_minutes)
    LOOP
        should_trigger := false;
        alert_msg := '';

        -- Check threshold rules
        IF rule.rule_type = 'threshold' THEN
            should_trigger := check_threshold_condition(rule.condition);
            IF should_trigger THEN
                alert_msg := format('Threshold exceeded for rule: %s', rule.rule_name);
            END IF;
        END IF;

        -- Check rate rules
        IF rule.rule_type = 'rate' THEN
            should_trigger := check_rate_condition(rule.condition);
            IF should_trigger THEN
                alert_msg := format('Rate limit exceeded for rule: %s', rule.rule_name);
            END IF;
        END IF;

        -- If triggered, log alert and update rule
        IF should_trigger THEN
            INSERT INTO alert_history (rule_id, rule_name, severity, alert_message, context)
            VALUES (rule.id, rule.rule_name, rule.severity, alert_msg, rule.condition);

            UPDATE alert_rules
            SET last_triggered_at = NOW(), trigger_count = trigger_count + 1
            WHERE id = rule.id;
        END IF;

        RETURN QUERY SELECT rule.rule_name, should_trigger, alert_msg;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Helper function for threshold checks (simplified)
CREATE OR REPLACE FUNCTION check_threshold_condition(condition JSONB)
RETURNS BOOLEAN AS $$
DECLARE
    metric_name VARCHAR;
    threshold DECIMAL;
    current_value DECIMAL;
BEGIN
    metric_name := condition->>'metric';
    threshold := (condition->>'threshold')::DECIMAL;

    -- Get current metric value
    SELECT metric_value INTO current_value
    FROM system_metrics
    WHERE system_metrics.metric_name = metric_name
    ORDER BY timestamp DESC
    LIMIT 1;

    RETURN COALESCE(current_value > threshold, false);
END;
$$ LANGUAGE plpgsql;

-- Helper function for rate checks (simplified)
CREATE OR REPLACE FUNCTION check_rate_condition(condition JSONB)
RETURNS BOOLEAN AS $$
DECLARE
    metric_name VARCHAR;
    max_rate DECIMAL;
    time_window INTERVAL;
    current_rate DECIMAL;
BEGIN
    metric_name := condition->>'metric';
    max_rate := (condition->>'max_rate')::DECIMAL;
    time_window := (condition->>'window')::INTERVAL;

    -- Calculate current rate
    SELECT COUNT(*)::DECIMAL / EXTRACT(EPOCH FROM time_window)::DECIMAL INTO current_rate
    FROM system_metrics
    WHERE system_metrics.metric_name = metric_name
    AND timestamp > NOW() - time_window;

    RETURN COALESCE(current_rate > max_rate, false);
END;
$$ LANGUAGE plpgsql;
```

---

## 6.2 Python Services - Monitoring

### 6.2.1 Metrics Service

```python
# app/services/metrics_service.py

from typing import Dict, Optional, List
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from datetime import datetime
import logging
from supabase import create_client, Client
from app.config import Settings

settings = Settings()
logger = logging.getLogger(__name__)

# Define Prometheus metrics
DOCUMENT_UPLOADS = Counter(
    'empire_document_uploads_total',
    'Total number of document uploads',
    ['status', 'file_type']
)

DOCUMENT_PROCESSING_TIME = Histogram(
    'empire_document_processing_seconds',
    'Time spent processing documents',
    ['operation_type'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0]
)

EMBEDDING_GENERATION_TIME = Histogram(
    'empire_embedding_generation_seconds',
    'Time spent generating embeddings',
    ['provider'],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0]
)

SEARCH_QUERIES = Counter(
    'empire_search_queries_total',
    'Total number of search queries',
    ['search_type', 'status']
)

SEARCH_LATENCY = Histogram(
    'empire_search_latency_seconds',
    'Search query latency',
    ['search_type'],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0]
)

CHAT_MESSAGES = Counter(
    'empire_chat_messages_total',
    'Total number of chat messages',
    ['role', 'has_memory']
)

LLM_RESPONSE_TIME = Histogram(
    'empire_llm_response_seconds',
    'LLM response generation time',
    ['model'],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0]
)

ACTIVE_WEBSOCKETS = Gauge(
    'empire_active_websockets',
    'Number of active WebSocket connections'
)

QUEUE_SIZE = Gauge(
    'empire_celery_queue_size',
    'Number of tasks in Celery queue',
    ['queue_name']
)

ERROR_COUNT = Counter(
    'empire_errors_total',
    'Total number of errors',
    ['error_type', 'component']
)

class MetricsService:
    """Service for collecting and exposing metrics"""

    def __init__(self):
        self.supabase: Client = create_client(
            settings.supabase_url,
            settings.supabase_key
        )

    # Document metrics
    def record_document_upload(self, status: str, file_type: str):
        """Record a document upload event"""
        DOCUMENT_UPLOADS.labels(status=status, file_type=file_type).inc()

    def record_document_processing(self, operation_type: str, duration_seconds: float):
        """Record document processing time"""
        DOCUMENT_PROCESSING_TIME.labels(operation_type=operation_type).observe(duration_seconds)

    # Embedding metrics
    def record_embedding_generation(self, provider: str, duration_seconds: float):
        """Record embedding generation time"""
        EMBEDDING_GENERATION_TIME.labels(provider=provider).observe(duration_seconds)

    # Search metrics
    def record_search_query(self, search_type: str, status: str, duration_seconds: float):
        """Record a search query"""
        SEARCH_QUERIES.labels(search_type=search_type, status=status).inc()
        SEARCH_LATENCY.labels(search_type=search_type).observe(duration_seconds)

    # Chat metrics
    def record_chat_message(self, role: str, has_memory: bool):
        """Record a chat message"""
        CHAT_MESSAGES.labels(role=role, has_memory=str(has_memory).lower()).inc()

    def record_llm_response(self, model: str, duration_seconds: float):
        """Record LLM response time"""
        LLM_RESPONSE_TIME.labels(model=model).observe(duration_seconds)

    # WebSocket metrics
    def increment_websocket_connections(self):
        """Increment active WebSocket connections"""
        ACTIVE_WEBSOCKETS.inc()

    def decrement_websocket_connections(self):
        """Decrement active WebSocket connections"""
        ACTIVE_WEBSOCKETS.dec()

    # Queue metrics
    def update_queue_size(self, queue_name: str, size: int):
        """Update Celery queue size"""
        QUEUE_SIZE.labels(queue_name=queue_name).set(size)

    # Error metrics
    def record_error(self, error_type: str, component: str):
        """Record an error occurrence"""
        ERROR_COUNT.labels(error_type=error_type, component=component).inc()

    # Persist detailed metrics to database
    async def log_performance_metric(
        self,
        operation_type: str,
        duration_ms: int,
        status: str,
        document_id: Optional[str] = None,
        file_size_bytes: Optional[int] = None,
        chunk_count: Optional[int] = None,
        token_count: Optional[int] = None,
        error_message: Optional[str] = None,
        metadata: Optional[Dict] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None
    ):
        """Log detailed performance metrics to database"""
        try:
            metric_data = {
                'operation_type': operation_type,
                'document_id': document_id,
                'duration_ms': duration_ms,
                'status': status,
                'file_size_bytes': file_size_bytes,
                'chunk_count': chunk_count,
                'token_count': token_count,
                'error_message': error_message,
                'metadata': metadata or {},
                'started_at': (started_at or datetime.now()).isoformat(),
                'completed_at': (completed_at or datetime.now()).isoformat()
            }

            self.supabase.table('performance_metrics').insert(metric_data).execute()
        except Exception as e:
            logger.error(f"Failed to log performance metric: {e}")

    async def get_processing_stats(
        self,
        operation_type: Optional[str] = None,
        time_window: str = '1 hour'
    ) -> List[Dict]:
        """Get processing statistics"""
        result = self.supabase.rpc(
            'get_processing_stats',
            {
                'p_operation_type': operation_type,
                'p_time_window': time_window
            }
        ).execute()

        return result.data if result.data else []

# Global metrics instance
metrics_service = MetricsService()
```

### 6.2.2 Health Check Service

```python
# app/services/health_service.py

from typing import Dict, List
import httpx
import asyncio
from datetime import datetime
import logging
from supabase import create_client, Client
from redis import Redis
from app.config import Settings

settings = Settings()
logger = logging.getLogger(__name__)

class HealthCheckService:
    """Service for checking health of all dependencies"""

    def __init__(self):
        self.supabase: Client = create_client(
            settings.supabase_url,
            settings.supabase_key
        )
        self.redis = Redis.from_url(settings.redis_url, decode_responses=True)

    async def check_supabase(self) -> Dict:
        """Check Supabase connection"""
        start = datetime.now()
        try:
            # Simple query to test connection
            result = self.supabase.table('documents').select('id').limit(1).execute()
            duration_ms = int((datetime.now() - start).total_seconds() * 1000)

            status = 'healthy' if result else 'degraded'
            return {
                'service': 'supabase',
                'status': status,
                'response_time_ms': duration_ms,
                'error': None
            }
        except Exception as e:
            duration_ms = int((datetime.now() - start).total_seconds() * 1000)
            return {
                'service': 'supabase',
                'status': 'unhealthy',
                'response_time_ms': duration_ms,
                'error': str(e)
            }

    async def check_redis(self) -> Dict:
        """Check Redis connection"""
        start = datetime.now()
        try:
            self.redis.ping()
            duration_ms = int((datetime.now() - start).total_seconds() * 1000)

            return {
                'service': 'redis',
                'status': 'healthy',
                'response_time_ms': duration_ms,
                'error': None
            }
        except Exception as e:
            duration_ms = int((datetime.now() - start).total_seconds() * 1000)
            return {
                'service': 'redis',
                'status': 'unhealthy',
                'response_time_ms': duration_ms,
                'error': str(e)
            }

    async def check_ollama(self) -> Dict:
        """Check Ollama API"""
        start = datetime.now()
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{settings.ollama_api_url}/api/tags")
                duration_ms = int((datetime.now() - start).total_seconds() * 1000)

                status = 'healthy' if response.status_code == 200 else 'degraded'
                return {
                    'service': 'ollama',
                    'status': status,
                    'response_time_ms': duration_ms,
                    'error': None
                }
        except Exception as e:
            duration_ms = int((datetime.now() - start).total_seconds() * 1000)
            return {
                'service': 'ollama',
                'status': 'unhealthy',
                'response_time_ms': duration_ms,
                'error': str(e)
            }

    async def check_b2_storage(self) -> Dict:
        """Check Backblaze B2 connection"""
        start = datetime.now()
        try:
            # Import B2 client
            from b2sdk.v2 import B2Api, InMemoryAccountInfo

            info = InMemoryAccountInfo()
            b2_api = B2Api(info)
            b2_api.authorize_account(
                "production",
                settings.b2_application_key_id,
                settings.b2_application_key
            )

            # List buckets to test connection
            buckets = b2_api.list_buckets()
            duration_ms = int((datetime.now() - start).total_seconds() * 1000)

            return {
                'service': 'b2_storage',
                'status': 'healthy',
                'response_time_ms': duration_ms,
                'error': None
            }
        except Exception as e:
            duration_ms = int((datetime.now() - start).total_seconds() * 1000)
            return {
                'service': 'b2_storage',
                'status': 'unhealthy',
                'response_time_ms': duration_ms,
                'error': str(e)
            }

    async def check_all_services(self) -> Dict:
        """Check all services concurrently"""
        checks = await asyncio.gather(
            self.check_supabase(),
            self.check_redis(),
            self.check_ollama(),
            self.check_b2_storage(),
            return_exceptions=True
        )

        # Filter out exceptions and format results
        results = []
        for check in checks:
            if isinstance(check, Exception):
                results.append({
                    'service': 'unknown',
                    'status': 'unhealthy',
                    'error': str(check)
                })
            else:
                results.append(check)

        # Store health check results in database
        for result in results:
            try:
                self.supabase.table('health_checks').insert({
                    'service_name': result['service'],
                    'status': result['status'],
                    'response_time_ms': result.get('response_time_ms'),
                    'error_message': result.get('error'),
                    'checked_at': datetime.now().isoformat()
                }).execute()
            except Exception as e:
                logger.error(f"Failed to log health check: {e}")

        # Overall system status
        overall_status = 'healthy'
        if any(r['status'] == 'unhealthy' for r in results):
            overall_status = 'unhealthy'
        elif any(r['status'] == 'degraded' for r in results):
            overall_status = 'degraded'

        return {
            'status': overall_status,
            'services': results,
            'timestamp': datetime.now().isoformat()
        }

    async def get_health_summary(self) -> Dict:
        """Get health summary from database"""
        result = self.supabase.rpc('get_system_health_summary').execute()
        return {
            'services': result.data if result.data else [],
            'timestamp': datetime.now().isoformat()
        }

# Global health check instance
health_service = HealthCheckService()
```

### 6.2.3 Structured Logging Configuration

```python
# app/utils/logging_config.py

import logging
import json
from datetime import datetime
from typing import Dict, Any
from supabase import create_client, Client
from app.config import Settings

settings = Settings()

class SupabaseLogHandler(logging.Handler):
    """Custom log handler that writes to Supabase"""

    def __init__(self):
        super().__init__()
        self.supabase: Client = create_client(
            settings.supabase_url,
            settings.supabase_key
        )

    def emit(self, record: logging.LogRecord):
        """Emit a log record to Supabase"""
        try:
            log_entry = {
                'log_level': record.levelname,
                'logger_name': record.name,
                'message': record.getMessage(),
                'function_name': record.funcName,
                'line_number': record.lineno,
                'timestamp': datetime.fromtimestamp(record.created).isoformat()
            }

            # Add exception info if present
            if record.exc_info:
                log_entry['exception_type'] = record.exc_info[0].__name__
                log_entry['exception_message'] = str(record.exc_info[1])
                log_entry['stack_trace'] = self.formatter.formatException(record.exc_info)

            # Add custom fields if present
            if hasattr(record, 'document_id'):
                log_entry['document_id'] = record.document_id
            if hasattr(record, 'user_id'):
                log_entry['user_id'] = record.user_id
            if hasattr(record, 'session_id'):
                log_entry['session_id'] = record.session_id

            # Store metadata
            metadata = {}
            for key, value in record.__dict__.items():
                if key not in ['name', 'msg', 'args', 'created', 'filename', 'funcName',
                               'levelname', 'levelno', 'lineno', 'module', 'msecs',
                               'message', 'pathname', 'process', 'processName', 'relativeCreated',
                               'thread', 'threadName', 'exc_info', 'exc_text', 'stack_info']:
                    metadata[key] = value

            if metadata:
                log_entry['metadata'] = metadata

            # Insert into Supabase
            self.supabase.table('processing_logs').insert(log_entry).execute()

        except Exception as e:
            # Fallback to stderr if Supabase fails
            print(f"Failed to log to Supabase: {e}", file=sys.stderr)

class JSONFormatter(logging.Formatter):
    """Format logs as JSON"""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'function': record.funcName,
            'line': record.lineno
        }

        # Add exception info
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': self.formatException(record.exc_info)
            }

        # Add custom fields
        for key in ['document_id', 'user_id', 'session_id']:
            if hasattr(record, key):
                log_data[key] = getattr(record, key)

        return json.dumps(log_data)

def setup_logging():
    """Configure application logging"""
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Console handler with JSON formatting
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(console_handler)

    # File handler for persistent logs
    file_handler = logging.FileHandler('/var/log/empire/app.log')
    file_handler.setLevel(logging.WARNING)
    file_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(file_handler)

    # Supabase handler for ERROR and above
    if settings.log_to_database:
        db_handler = SupabaseLogHandler()
        db_handler.setLevel(logging.ERROR)
        root_logger.addHandler(db_handler)

    # Set levels for specific loggers
    logging.getLogger('uvicorn').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('supabase').setLevel(logging.WARNING)

    return root_logger
```

---

## 6.3 FastAPI Health and Metrics Endpoints

```python
# app/routers/monitoring.py

from fastapi import APIRouter, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from typing import Dict
import logging

from app.services.health_service import health_service
from app.services.metrics_service import metrics_service

router = APIRouter(prefix="/monitoring", tags=["monitoring"])
logger = logging.getLogger(__name__)

@router.get("/health")
async def health_check() -> Dict:
    """
    Basic health check endpoint.
    Returns 200 if system is operational.
    """
    health_status = await health_service.check_all_services()
    return health_status

@router.get("/health/summary")
async def health_summary() -> Dict:
    """
    Get detailed health summary from database.
    Includes uptime percentages and average response times.
    """
    summary = await health_service.get_health_summary()
    return summary

@router.get("/metrics")
async def metrics() -> Response:
    """
    Prometheus metrics endpoint.
    Exposes all application metrics in Prometheus format.
    """
    metrics_data = generate_latest()
    return Response(content=metrics_data, media_type=CONTENT_TYPE_LATEST)

@router.get("/stats/processing")
async def processing_stats(
    operation_type: str = None,
    time_window: str = "1 hour"
) -> Dict:
    """
    Get processing statistics.

    Args:
        operation_type: Filter by operation (upload, extraction, embedding, search, chat)
        time_window: Time window for stats (e.g., "1 hour", "24 hours", "7 days")
    """
    stats = await metrics_service.get_processing_stats(operation_type, time_window)
    return {
        'stats': stats,
        'operation_type': operation_type,
        'time_window': time_window
    }

@router.get("/ready")
async def readiness_check() -> Dict:
    """
    Kubernetes readiness probe.
    Returns 200 if service is ready to accept traffic.
    """
    # Check critical services
    checks = await health_service.check_all_services()

    if checks['status'] == 'unhealthy':
        return Response(
            content={"status": "not_ready", "services": checks['services']},
            status_code=503
        )

    return {"status": "ready", "services": checks['services']}

@router.get("/live")
async def liveness_check() -> Dict:
    """
    Kubernetes liveness probe.
    Returns 200 if service is alive.
    """
    return {"status": "alive"}
```

---

## 6.4 Prometheus Configuration

```yaml
# prometheus.yml

global:
  scrape_interval: 15s
  evaluation_interval: 15s

alerting:
  alertmanagers:
    - static_configs:
        - targets:
            - alertmanager:9093

rule_files:
  - "alert_rules.yml"

scrape_configs:
  - job_name: 'empire_api'
    static_configs:
      - targets: ['web:8000']
    metrics_path: '/monitoring/metrics'
    scrape_interval: 10s
```

### 6.4.1 Alert Rules

```yaml
# alert_rules.yml

groups:
  - name: empire_alerts
    interval: 30s
    rules:
      # High error rate
      - alert: HighErrorRate
        expr: rate(empire_errors_total[5m]) > 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value }} errors/sec"

      # Slow document processing
      - alert: SlowDocumentProcessing
        expr: histogram_quantile(0.95, empire_document_processing_seconds_bucket) > 30
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Document processing is slow"
          description: "P95 latency is {{ $value }}s"

      # Search latency
      - alert: HighSearchLatency
        expr: histogram_quantile(0.95, empire_search_latency_seconds_bucket) > 2
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Search queries are slow"
          description: "P95 search latency is {{ $value }}s"

      # Service unhealthy
      - alert: ServiceUnhealthy
        expr: up{job="empire_api"} == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Empire API is down"
          description: "The API service has been down for 2 minutes"

      # High queue size
      - alert: HighQueueSize
        expr: empire_celery_queue_size > 100
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Celery queue is backing up"
          description: "Queue size is {{ $value }} tasks"
```

---

## 6.5 Grafana Dashboard Configuration

```json
{
  "dashboard": {
    "title": "Empire Document Processing",
    "panels": [
      {
        "title": "Document Upload Rate",
        "targets": [
          {
            "expr": "rate(empire_document_uploads_total[5m])",
            "legendFormat": "{{status}} - {{file_type}}"
          }
        ],
        "type": "graph"
      },
      {
        "title": "Processing Latency (P95)",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(empire_document_processing_seconds_bucket[5m]))",
            "legendFormat": "{{operation_type}}"
          }
        ],
        "type": "graph"
      },
      {
        "title": "Search Performance",
        "targets": [
          {
            "expr": "rate(empire_search_queries_total[5m])",
            "legendFormat": "{{search_type}} - {{status}}"
          }
        ],
        "type": "graph"
      },
      {
        "title": "Active WebSocket Connections",
        "targets": [
          {
            "expr": "empire_active_websockets"
          }
        ],
        "type": "stat"
      },
      {
        "title": "Error Rate",
        "targets": [
          {
            "expr": "rate(empire_errors_total[5m])",
            "legendFormat": "{{component}} - {{error_type}}"
          }
        ],
        "type": "graph"
      }
    ]
  }
}
```

---

## 6.6 Docker Compose Update

```yaml
# Add to docker-compose.yml

services:
  # ... existing services ...

  prometheus:
    image: prom/prometheus:latest
    container_name: empire_prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - ./monitoring/alert_rules.yml:/etc/prometheus/alert_rules.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
    depends_on:
      - web

  grafana:
    image: grafana/grafana:latest
    container_name: empire_grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_INSTALL_PLUGINS=
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana-dashboards:/etc/grafana/provisioning/dashboards
    depends_on:
      - prometheus

volumes:
  prometheus_data:
  grafana_data:
```

---

## 6.7 Environment Variables

```bash
# Add to .env

# Monitoring
PROMETHEUS_ENABLED=true
METRICS_PORT=8000
LOG_LEVEL=INFO
LOG_TO_DATABASE=true
LOG_FILE_PATH=/var/log/empire/app.log

# Alerting
ALERT_EMAIL=alerts@example.com
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

---

**Performance Targets**:
- Health check response: <100ms
- Metrics collection overhead: <1% CPU
- Log write latency: <10ms (async)
- Prometheus scrape interval: 15 seconds
- Dashboard update frequency: 10 seconds

**Next**: Milestone 7 (Admin Tools) and then CrewAI integration

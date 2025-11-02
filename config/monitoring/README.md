# Empire v7.2 Monitoring Stack

This directory contains the configuration for Empire's comprehensive monitoring and observability stack.

## Components

### 1. **Prometheus** (Port 9090)
- Metrics collection and storage
- Scrapes metrics from all Empire services
- Evaluates alert rules
- Time-series database for metrics

### 2. **Grafana** (Port 3000)
- Visualization dashboards
- Real-time metrics display
- Custom Empire dashboard included
- Default credentials: admin/empiregrafana123

### 3. **Alertmanager** (Port 9093)
- Alert routing and notifications
- Email/Slack/webhook integrations
- Alert grouping and silencing
- Configurable notification channels

### 4. **Redis** (Port 6379)
- Celery task broker
- Result backend storage
- Caching layer
- Session storage

### 5. **Flower** (Port 5555)
- Celery task monitoring
- Real-time worker status
- Task history and statistics
- Default credentials: admin/empireflower123

### 6. **Node Exporter** (Port 9100)
- System-level metrics
- CPU, memory, disk usage
- Network statistics

### 7. **cAdvisor** (Port 8080)
- Container metrics
- Docker resource usage
- Container performance data

## Quick Start

### 1. Start the monitoring stack:
```bash
./start-monitoring.sh
```

### 2. Access the services:
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin/empiregrafana123)
- **Flower**: http://localhost:5555 (admin/empireflower123)
- **Alertmanager**: http://localhost:9093

### 3. View logs:
```bash
docker-compose -f docker-compose.monitoring.yml logs -f [service_name]
```

### 4. Stop the monitoring stack:
```bash
docker-compose -f docker-compose.monitoring.yml down
```

## Configuration Files

### `prometheus.yml`
Main Prometheus configuration:
- Scrape intervals and targets
- Service discovery
- Alert rule references

### `alert_rules.yml`
Alert definitions:
- High error rates
- Slow processing times
- Service health checks
- Resource usage thresholds

### `alertmanager.yml`
Alert routing configuration:
- Notification channels (email, Slack)
- Alert grouping rules
- Silence periods

### `grafana/dashboards/empire-dashboard.json`
Custom Empire dashboard:
- Document upload metrics
- Processing latency graphs
- Search performance
- Error rates
- System resources

## Metrics Available

### Application Metrics
- `empire_document_uploads_total` - Total document uploads
- `empire_document_processing_seconds` - Processing time histogram
- `empire_embedding_generation_seconds` - Embedding generation time
- `empire_search_queries_total` - Total search queries
- `empire_search_latency_seconds` - Search latency histogram
- `empire_chat_messages_total` - Total chat messages
- `empire_llm_response_seconds` - LLM response time
- `empire_active_websockets` - Active WebSocket connections
- `empire_celery_queue_size` - Celery queue size
- `empire_errors_total` - Total errors by type

### System Metrics
- CPU usage
- Memory usage
- Disk I/O
- Network traffic
- Container statistics

## Alert Rules

### Critical Alerts
- Empire API down
- Critical error rate (>5 errors/sec)
- Very slow document processing (>60s P95)
- Critical search latency (>5s P95)
- Redis/Neo4j down
- Critical resource usage (>95%)

### Warning Alerts
- High error rate (>1 error/sec)
- Slow document processing (>30s P95)
- High search latency (>2s P95)
- High LLM response time (>20s P95)
- High queue size (>100 tasks)
- High resource usage (>80%)

## Customization

### Adding New Metrics

1. In your Python code:
```python
from prometheus_client import Counter, Histogram

MY_METRIC = Counter('empire_my_metric_total', 'Description', ['label1', 'label2'])
MY_METRIC.labels(label1='value1', label2='value2').inc()
```

2. The metric will automatically be scraped by Prometheus

### Adding New Alerts

Edit `alert_rules.yml`:
```yaml
- alert: MyNewAlert
  expr: rate(empire_my_metric_total[5m]) > 10
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "My metric is too high"
    description: "Value is {{ $value }}"
```

### Creating New Dashboards

1. Create dashboard in Grafana UI
2. Export as JSON
3. Save to `grafana/dashboards/`
4. Restart Grafana to auto-provision

## Troubleshooting

### Services not starting
```bash
# Check Docker logs
docker-compose -f docker-compose.monitoring.yml logs [service_name]

# Verify ports are available
lsof -i :9090  # Prometheus
lsof -i :3000  # Grafana
lsof -i :6379  # Redis
```

### Metrics not appearing
1. Check Prometheus targets: http://localhost:9090/targets
2. Verify Empire API has `/monitoring/metrics` endpoint
3. Check scrape configuration in `prometheus.yml`

### Alerts not firing
1. Check alert rules syntax: http://localhost:9090/rules
2. Verify Alertmanager is receiving alerts: http://localhost:9093
3. Check notification configuration in `alertmanager.yml`

### High memory usage
```bash
# Reduce retention time in prometheus.yml
--storage.tsdb.retention.time=7d  # Instead of 30d

# Limit Redis memory in docker-compose
command: redis-server --maxmemory 128mb
```

## Integration with Empire

The Empire API automatically exposes metrics at `/monitoring/metrics` when `PROMETHEUS_ENABLED=true` is set in `.env`.

Example integration:
```python
from app.services.metrics_service import metrics_service

# Record a metric
metrics_service.record_document_upload(status="success", file_type="pdf")

# Record processing time
metrics_service.record_document_processing(
    operation_type="extraction",
    duration_seconds=2.5
)
```

## Best Practices

1. **Set appropriate alert thresholds** based on your SLAs
2. **Use labels** to segment metrics by component/operation
3. **Create focused dashboards** for different user roles
4. **Regularly review alerts** to reduce noise
5. **Export important dashboards** as backups
6. **Document custom metrics** in code
7. **Test alert rules** before production
8. **Set up notification channels** early

## Resources

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [Alertmanager Documentation](https://prometheus.io/docs/alerting/latest/alertmanager/)
- [Flower Documentation](https://flower.readthedocs.io/)
- [Redis Documentation](https://redis.io/documentation)
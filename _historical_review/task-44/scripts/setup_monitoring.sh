#!/bin/bash
# Setup Grafana Monitoring Stack for Empire v7.3
# Task 43.3+ Performance Monitoring

set -e

echo "======================================================================"
echo "Empire v7.3 - Grafana Monitoring Stack Setup"
echo "======================================================================"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running"
    echo ""
    echo "Please start Docker Desktop and try again:"
    echo "  1. Open Docker Desktop application"
    echo "  2. Wait for Docker to fully start (whale icon in menu bar)"
    echo "  3. Run this script again"
    exit 1
fi

echo "✅ Docker is running"

# Navigate to docker directory
cd "$(dirname "$0")/../config/docker"

echo ""
echo "Starting monitoring stack..."
echo "  - Prometheus (metrics collection)"
echo "  - Grafana (dashboards)"
echo "  - Alertmanager (alerts)"
echo "  - Node Exporter (system metrics)"
echo "  - cAdvisor (container metrics)"
echo ""

# Start monitoring stack
docker-compose -f docker-compose.monitoring.yml up -d

echo ""
echo "⏳ Waiting for services to start (15 seconds)..."
sleep 15

# Check service status
echo ""
echo "======================================================================"
echo "Service Status"
echo "======================================================================"

services=("prometheus" "grafana" "alertmanager" "node-exporter" "cadvisor")
all_running=true

for service in "${services[@]}"; do
    container_name="empire_${service//-/_}"
    if docker ps --filter "name=$container_name" --filter "status=running" | grep -q "$container_name"; then
        echo "✅ $service - Running"
    else
        echo "❌ $service - Not running"
        all_running=false
    fi
done

echo ""
echo "======================================================================"
echo "Access URLs"
echo "======================================================================"
echo ""
echo "Grafana Dashboard:"
echo "  URL: http://localhost:3001"
echo "  Username: admin"
echo "  Password: empiregrafana123"
echo ""
echo "Prometheus:"
echo "  URL: http://localhost:9090"
echo ""
echo "Alertmanager:"
echo "  URL: http://localhost:9093"
echo ""
echo "Node Exporter:"
echo "  URL: http://localhost:9100"
echo ""
echo "cAdvisor:"
echo "  URL: http://localhost:8080"
echo ""

if [ "$all_running" = true ]; then
    echo "======================================================================"
    echo "Next Steps"
    echo "======================================================================"
    echo ""
    echo "1. Open Grafana: http://localhost:3001"
    echo "   Login with: admin / empiregrafana123"
    echo ""
    echo "2. Import Performance Dashboard:"
    echo "   a. Click '+' → Import"
    echo "   b. Upload: config/monitoring/grafana/dashboards/empire-performance-task43.json"
    echo "   c. Select 'Prometheus' as data source"
    echo "   d. Click 'Import'"
    echo ""
    echo "3. Configure Prometheus to scrape Empire API:"
    echo "   Edit: config/monitoring/prometheus.yml"
    echo "   Add your production URL: https://jb-empire-api.onrender.com"
    echo ""
    echo "4. Restart Prometheus to apply changes:"
    echo "   docker-compose -f docker-compose.monitoring.yml restart prometheus"
    echo ""
    echo "✅ Monitoring stack setup complete!"
else
    echo "⚠️  Some services failed to start. Check logs:"
    echo "   docker-compose -f docker-compose.monitoring.yml logs"
fi

echo ""

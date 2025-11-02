#!/bin/bash

# ==========================================
# EMPIRE v7.2 - MONITORING STACK STARTUP
# ==========================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "  EMPIRE v7.2 - Monitoring Stack"
echo "=========================================="
echo ""

# Navigate to project root
cd "$(dirname "$0")/../.." || exit 1

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${RED}Error: .env file not found!${NC}"
    echo "Please create .env file with monitoring configurations."
    exit 1
fi

# Load environment variables
source .env

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    echo -e "${RED}Error: Docker is not running!${NC}"
    echo "Please start Docker Desktop first."
    exit 1
fi

# Create necessary directories
echo -e "${YELLOW}Creating monitoring directories...${NC}"
mkdir -p config/monitoring/prometheus
mkdir -p config/monitoring/grafana/provisioning/datasources
mkdir -p config/monitoring/grafana/provisioning/dashboards
mkdir -p config/monitoring/grafana/dashboards

# Check if monitoring config files exist
if [ ! -f config/monitoring/prometheus.yml ]; then
    echo -e "${RED}Error: config/monitoring/prometheus.yml not found!${NC}"
    echo "Please create Prometheus configuration file."
    exit 1
fi

if [ ! -f config/monitoring/alert_rules.yml ]; then
    echo -e "${RED}Error: config/monitoring/alert_rules.yml not found!${NC}"
    echo "Please create alert rules configuration file."
    exit 1
fi

# Start monitoring stack
echo -e "${YELLOW}Starting monitoring services...${NC}"
docker-compose -f config/docker/docker-compose.monitoring.yml up -d

# Wait for services to be ready
echo -e "${YELLOW}Waiting for services to start...${NC}"
sleep 10

# Check service health
echo -e "${YELLOW}Checking service health...${NC}"
echo ""

# Check Prometheus
if curl -s -o /dev/null -w "%{http_code}" http://localhost:9090/-/healthy | grep -q "200"; then
    echo -e "${GREEN}✓ Prometheus is running at http://localhost:9090${NC}"
else
    echo -e "${RED}✗ Prometheus failed to start${NC}"
fi

# Check Grafana
if curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/api/health | grep -q "200"; then
    echo -e "${GREEN}✓ Grafana is running at http://localhost:3000${NC}"
    echo "  Username: ${GRAFANA_ADMIN_USER:-admin}"
    echo "  Password: ${GRAFANA_ADMIN_PASSWORD:-empiregrafana123}"
else
    echo -e "${RED}✗ Grafana failed to start${NC}"
fi

# Check Redis
if docker exec empire_redis redis-cli ping | grep -q "PONG"; then
    echo -e "${GREEN}✓ Redis is running at localhost:6379${NC}"
else
    echo -e "${RED}✗ Redis failed to start${NC}"
fi

# Check Flower
if curl -s -o /dev/null -w "%{http_code}" http://admin:empireflower123@localhost:5555/api/workers | grep -q "200"; then
    echo -e "${GREEN}✓ Flower (Celery monitoring) is running at http://localhost:5555${NC}"
    echo "  Username: admin"
    echo "  Password: empireflower123"
else
    echo -e "${RED}✗ Flower failed to start${NC}"
fi

# Check Alertmanager
if curl -s -o /dev/null -w "%{http_code}" http://localhost:9093/-/healthy | grep -q "200"; then
    echo -e "${GREEN}✓ Alertmanager is running at http://localhost:9093${NC}"
else
    echo -e "${RED}✗ Alertmanager failed to start${NC}"
fi

echo ""
echo "=========================================="
echo "  Monitoring Stack Status"
echo "=========================================="
echo ""
echo "Services URLs:"
echo "  • Prometheus:    http://localhost:9090"
echo "  • Grafana:       http://localhost:3000"
echo "  • Flower:        http://localhost:5555"
echo "  • Alertmanager:  http://localhost:9093"
echo "  • Redis:         localhost:6379"
echo ""
echo "To view logs:"
echo "  docker-compose -f config/docker/docker-compose.monitoring.yml logs -f [service_name]"
echo ""
echo "To stop monitoring:"
echo "  docker-compose -f config/docker/docker-compose.monitoring.yml down"
echo ""
echo -e "${GREEN}Monitoring stack started successfully!${NC}"
#!/bin/bash
# Empire v7.3 - Monitoring Stack Startup Script
# Starts Prometheus, Grafana, Alertmanager, and Node Exporter

set -e  # Exit on any error

echo "========================================"
echo "Empire v7.3 - Monitoring Stack Startup"
echo "========================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}❌ Error: Docker is not running${NC}"
    echo "Please start Docker Desktop and try again"
    exit 1
fi

# Check if .env file exists and has SMTP_PASSWORD
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  Warning: .env file not found${NC}"
    echo "Creating .env file from template..."
    echo ""
    echo "# Empire Monitoring - SMTP Configuration" > .env
    echo "# For Gmail: Create an App Password at https://myaccount.google.com/apppasswords" >> .env
    echo "SMTP_PASSWORD=YOUR_APP_PASSWORD_HERE" >> .env
    echo ""
    echo -e "${YELLOW}📝 Please edit .env and set your SMTP_PASSWORD${NC}"
    echo "   For Gmail: https://myaccount.google.com/apppasswords"
    echo ""
    read -p "Press Enter when you've updated .env file..."
fi

# Check if SMTP_PASSWORD is set
if grep -q "YOUR_APP_PASSWORD_HERE" .env 2>/dev/null || ! grep -q "SMTP_PASSWORD" .env 2>/dev/null; then
    echo -e "${YELLOW}⚠️  SMTP_PASSWORD not configured in .env file${NC}"
    echo "Email alerts will not work until you set this."
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "Starting monitoring stack..."
echo ""

# Stop any existing containers
echo "Stopping existing containers..."
docker-compose -f docker-compose.monitoring.yml down 2>/dev/null || true

# Start the monitoring stack
echo "Starting Prometheus, Grafana, Alertmanager, and Node Exporter..."
docker-compose -f docker-compose.monitoring.yml up -d

# Wait for services to be healthy
echo ""
echo "Waiting for services to start..."
sleep 5

# Check service health
PROMETHEUS_HEALTHY=false
GRAFANA_HEALTHY=false
ALERTMANAGER_HEALTHY=false

for i in {1..30}; do
    if curl -sf http://localhost:9090/-/healthy > /dev/null 2>&1; then
        PROMETHEUS_HEALTHY=true
    fi
    if curl -sf http://localhost:3000/api/health > /dev/null 2>&1; then
        GRAFANA_HEALTHY=true
    fi
    if curl -sf http://localhost:9093/-/healthy > /dev/null 2>&1; then
        ALERTMANAGER_HEALTHY=true
    fi

    if $PROMETHEUS_HEALTHY && $GRAFANA_HEALTHY && $ALERTMANAGER_HEALTHY; then
        break
    fi
    sleep 2
done

echo ""
echo "========================================"
echo "Monitoring Stack Status"
echo "========================================"
echo ""

if $PROMETHEUS_HEALTHY; then
    echo -e "${GREEN}✅ Prometheus${NC}    → http://localhost:9090"
else
    echo -e "${RED}❌ Prometheus${NC}    → Failed to start"
fi

if $GRAFANA_HEALTHY; then
    echo -e "${GREEN}✅ Grafana${NC}       → http://localhost:3000"
    echo "   (admin/empiregrafana123)"
else
    echo -e "${RED}❌ Grafana${NC}       → Failed to start"
fi

if $ALERTMANAGER_HEALTHY; then
    echo -e "${GREEN}✅ Alertmanager${NC}  → http://localhost:9093"
else
    echo -e "${RED}❌ Alertmanager${NC}  → Failed to start"
fi

echo -e "${GREEN}✅ Node Exporter${NC} → http://localhost:9100"

echo ""
echo "========================================"
echo "Quick Access"
echo "========================================"
echo ""
echo "View Metrics:     http://localhost:9090"
echo "View Dashboards:  http://localhost:3000"
echo "View Alerts:      http://localhost:9090/alerts"
echo "Manage Alerts:    http://localhost:9093"
echo ""
echo "To test email alerts:"
echo "  ./test-alert.sh"
echo ""
echo "To view logs:"
echo "  docker-compose -f docker-compose.monitoring.yml logs -f"
echo ""
echo "To stop monitoring:"
echo "  docker-compose -f docker-compose.monitoring.yml down"
echo ""
echo -e "${GREEN}✅ Monitoring stack is running!${NC}"
echo ""

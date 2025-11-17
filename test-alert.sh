#!/bin/bash
# Empire v7.3 - Test Alert Notification Script
# Sends a test alert to verify email notifications are working

set -e

echo "=========================================="
echo "Empire v7.3 - Test Alert Notification"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check if Alertmanager is running
if ! curl -sf http://localhost:9093/-/healthy > /dev/null 2>&1; then
    echo "❌ Error: Alertmanager is not running"
    echo "Start the monitoring stack first: ./start-monitoring.sh"
    exit 1
fi

echo "Sending test alert to Alertmanager..."
echo ""

# Send a test alert via Alertmanager API
curl -XPOST http://localhost:9093/api/v1/alerts -H "Content-Type: application/json" -d '[
  {
    "labels": {
      "alertname": "TestAlert",
      "severity": "info",
      "component": "monitoring"
    },
    "annotations": {
      "summary": "Test alert from Empire v7.3",
      "description": "This is a test alert to verify email notifications are working correctly. If you receive this email, your monitoring alerts are properly configured!",
      "runbook": "This is a test alert triggered manually via test-alert.sh"
    },
    "startsAt": "'$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)'",
    "endsAt": "'$(date -u -v+1M +%Y-%m-%dT%H:%M:%S.%3NZ)'"
  }
]'

echo ""
echo ""
echo -e "${GREEN}✅ Test alert sent successfully!${NC}"
echo ""
echo "Check your email (jbajaj08@gmail.com) for the test alert."
echo "It may take up to 5 minutes to arrive due to grouping settings."
echo ""
echo "To view the alert in Alertmanager:"
echo "  http://localhost:9093/#/alerts"
echo ""
echo "To view alert history in Prometheus:"
echo "  http://localhost:9090/alerts"
echo ""
echo -e "${YELLOW}Note:${NC} If you don't receive the email:"
echo "  1. Check that SMTP_PASSWORD is set in .env"
echo "  2. For Gmail, use an App Password: https://myaccount.google.com/apppasswords"
echo "  3. Check Alertmanager logs: docker logs empire-alertmanager"
echo ""

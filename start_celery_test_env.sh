#!/bin/bash

# Empire v7.3 - Start Celery Test Environment
# Starts Redis and Celery workers for priority queue testing

echo "=========================================="
echo "Starting Celery Test Environment"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Redis is running
echo -e "\n${YELLOW}1. Checking Redis...${NC}"
if lsof -Pi :6379 -sTCP:LISTEN -t >/dev/null ; then
    echo -e "${GREEN}✅ Redis is already running on port 6379${NC}"
else
    echo -e "${YELLOW}⚠️  Redis is not running. Starting Redis...${NC}"

    # Check if Redis is installed
    if command -v redis-server &> /dev/null; then
        redis-server --daemonize yes
        sleep 2
        echo -e "${GREEN}✅ Redis started${NC}"
    else
        echo -e "${RED}❌ Redis is not installed. Please install Redis:${NC}"
        echo "   brew install redis  # macOS"
        echo "   sudo apt install redis-server  # Ubuntu"
        exit 1
    fi
fi

# Check if Celery workers are running
echo -e "\n${YELLOW}2. Checking Celery workers...${NC}"
if pgrep -f "celery.*worker" > /dev/null; then
    echo -e "${GREEN}✅ Celery workers already running${NC}"
    echo -e "${YELLOW}   Stopping existing workers to ensure clean state...${NC}"
    pkill -f "celery.*worker"
    sleep 2
fi

# Start Celery worker in background
echo -e "${YELLOW}   Starting Celery worker...${NC}"
celery -A app.celery_app worker --loglevel=info --logfile=logs/celery_worker.log --detach

sleep 3

# Verify worker is running
if pgrep -f "celery.*worker" > /dev/null; then
    echo -e "${GREEN}✅ Celery worker started successfully${NC}"
    echo -e "   Log file: logs/celery_worker.log"
else
    echo -e "${RED}❌ Failed to start Celery worker${NC}"
    exit 1
fi

# Start Flower for monitoring (optional)
echo -e "\n${YELLOW}3. Starting Flower (Celery monitoring)...${NC}"
if lsof -Pi :5555 -sTCP:LISTEN -t >/dev/null ; then
    echo -e "${YELLOW}⚠️  Flower already running on port 5555${NC}"
else
    celery -A app.celery_app flower --port=5555 --logfile=logs/flower.log &
    sleep 2
    echo -e "${GREEN}✅ Flower started on http://localhost:5555${NC}"
fi

# Summary
echo -e "\n=========================================="
echo -e "${GREEN}✅ Celery Test Environment Ready${NC}"
echo "=========================================="
echo ""
echo "Services running:"
echo "  • Redis: localhost:6379"
echo "  • Celery Worker: Running (see logs/celery_worker.log)"
echo "  • Flower UI: http://localhost:5555"
echo ""
echo "To run tests:"
echo "  python3 test_celery_priority_queue.py"
echo ""
echo "To stop services:"
echo "  ./stop_celery_test_env.sh"
echo ""
echo "To monitor tasks in real-time:"
echo "  tail -f logs/celery_worker.log"
echo ""

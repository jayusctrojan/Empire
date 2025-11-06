#!/bin/bash

# Empire v7.3 - Stop Celery Test Environment

echo "=========================================="
echo "Stopping Celery Test Environment"
echo "=========================================="

# Colors
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m'

# Stop Celery workers
echo -e "\n${YELLOW}Stopping Celery workers...${NC}"
pkill -f "celery.*worker"
sleep 1
echo -e "${GREEN}✅ Celery workers stopped${NC}"

# Stop Flower
echo -e "\n${YELLOW}Stopping Flower...${NC}"
pkill -f "celery.*flower"
sleep 1
echo -e "${GREEN}✅ Flower stopped${NC}"

# Note about Redis (don't stop it as it might be used by other services)
echo -e "\n${YELLOW}ℹ️  Note: Redis is still running (may be used by other services)${NC}"
echo "   To stop Redis manually: redis-cli shutdown"

echo -e "\n${GREEN}✅ Celery Test Environment Stopped${NC}"
echo "=========================================="

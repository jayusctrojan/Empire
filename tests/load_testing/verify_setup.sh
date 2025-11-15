#!/bin/bash
# Verify Load Testing Setup for Empire v7.3
# Task 43.1 - Load Testing Infrastructure

echo "======================================================================"
echo "Empire v7.3 - Load Testing Setup Verification"
echo "======================================================================"
echo ""

# Check Python version
echo "1. Checking Python version..."
python3 --version
if [ $? -eq 0 ]; then
    echo "   ✅ Python 3 is installed"
else
    echo "   ❌ Python 3 is not installed"
    exit 1
fi
echo ""

# Check if locust is installed
echo "2. Checking if Locust is installed..."
if command -v locust &> /dev/null; then
    locust --version
    echo "   ✅ Locust is installed"
else
    echo "   ⚠️  Locust is not installed"
    echo "   Installing dependencies..."
    pip install -r requirements.txt
fi
echo ""

# Check directory structure
echo "3. Checking directory structure..."
if [ -f "locustfile.py" ]; then
    echo "   ✅ locustfile.py exists"
else
    echo "   ❌ locustfile.py not found"
    exit 1
fi

if [ -d "reports" ]; then
    echo "   ✅ reports/ directory exists"
else
    echo "   ❌ reports/ directory not found"
    exit 1
fi

for config in locust_light.conf locust_moderate.conf locust_heavy.conf locust_production.conf; do
    if [ -f "$config" ]; then
        echo "   ✅ $config exists"
    else
        echo "   ❌ $config not found"
    fi
done
echo ""

# Check if FastAPI is running
echo "4. Checking if FastAPI is running..."
response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health 2>/dev/null)
if [ "$response" = "200" ]; then
    echo "   ✅ FastAPI is running at http://localhost:8000"
else
    echo "   ⚠️  FastAPI is not running at http://localhost:8000"
    echo "   Start FastAPI with: uvicorn app.main:app --reload --port 8000"
fi
echo ""

# Validate locustfile syntax
echo "5. Validating locustfile.py syntax..."
python3 -m py_compile locustfile.py
if [ $? -eq 0 ]; then
    echo "   ✅ locustfile.py syntax is valid"
else
    echo "   ❌ locustfile.py has syntax errors"
    exit 1
fi
echo ""

# Test dry run
echo "6. Testing Locust dry run..."
timeout 5s locust -f locustfile.py --host=http://localhost:8000 --users=1 --spawn-rate=1 --run-time=1s --headless 2>&1 | head -20
if [ ${PIPESTATUS[0]} -eq 124 ] || [ ${PIPESTATUS[0]} -eq 0 ]; then
    echo "   ✅ Locust can start successfully"
else
    echo "   ⚠️  Locust encountered issues"
fi
echo ""

echo "======================================================================"
echo "Setup Verification Complete"
echo "======================================================================"
echo ""
echo "Next Steps:"
echo "  1. Install dependencies: pip install -r requirements.txt"
echo "  2. Start FastAPI: uvicorn app.main:app --reload --port 8000"
echo "  3. Run light load test: locust -f locustfile.py --config=locust_light.conf"
echo "  4. View results in: reports/load_test_light_report.html"
echo ""
echo "For more information, see: README.md"
echo ""

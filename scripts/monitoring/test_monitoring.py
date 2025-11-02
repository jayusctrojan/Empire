#!/usr/bin/env python3
"""
Test script to verify monitoring integration is working
Run this after starting the monitoring stack and your FastAPI app
"""

import requests
import time
import sys
from colorama import Fore, Style, init

# Initialize colorama for colored output
init(autoreset=True)

def test_service(name, url, expected_content=None, auth=None):
    """Test if a service is accessible"""
    try:
        if auth:
            response = requests.get(url, auth=auth, timeout=5)
        else:
            response = requests.get(url, timeout=5)

        if response.status_code == 200:
            if expected_content and expected_content not in response.text:
                print(f"{Fore.YELLOW}⚠ {name} is running but returned unexpected content")
                return False
            print(f"{Fore.GREEN}✓ {name} is running at {url}")
            return True
        else:
            print(f"{Fore.RED}✗ {name} returned status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"{Fore.RED}✗ {name} is not accessible at {url}")
        return False
    except Exception as e:
        print(f"{Fore.RED}✗ {name} error: {e}")
        return False

def main():
    print("=" * 60)
    print("EMPIRE v7.2 - Monitoring Integration Test")
    print("=" * 60)
    print()

    all_passed = True

    # Test monitoring services
    print(f"{Fore.CYAN}Testing Monitoring Services:")
    print("-" * 40)

    services = [
        ("Prometheus", "http://localhost:9090/-/healthy", None, None),
        ("Grafana", "http://localhost:3000/api/health", "ok", None),
        ("Alertmanager", "http://localhost:9093/-/healthy", None, None),
        ("Flower", "http://localhost:5555/api/workers", None, ("admin", "empireflower123")),
    ]

    for service in services:
        if not test_service(*service):
            all_passed = False

    print()

    # Test Empire API endpoints
    print(f"{Fore.CYAN}Testing Empire API Endpoints:")
    print("-" * 40)

    api_endpoints = [
        ("Empire Health", "http://localhost:8000/monitoring/health", "healthy", None),
        ("Empire Metrics", "http://localhost:8000/monitoring/metrics", "empire_", None),
        ("Empire Ready", "http://localhost:8000/monitoring/ready", "ready", None),
        ("Empire Live", "http://localhost:8000/monitoring/live", "alive", None),
    ]

    for endpoint in api_endpoints:
        if not test_service(*endpoint):
            all_passed = False
            if "Metrics" in endpoint[0]:
                print(f"  {Fore.YELLOW}→ Make sure you added the metrics endpoint to your FastAPI app")

    print()

    # Test Prometheus targets
    print(f"{Fore.CYAN}Testing Prometheus Targets:")
    print("-" * 40)

    try:
        response = requests.get("http://localhost:9090/api/v1/targets")
        targets = response.json()['data']['activeTargets']

        empire_target_found = False
        for target in targets:
            if 'empire_api' in target.get('job', ''):
                empire_target_found = True
                if target['health'] == 'up':
                    print(f"{Fore.GREEN}✓ Empire API target is UP in Prometheus")
                else:
                    print(f"{Fore.RED}✗ Empire API target is DOWN in Prometheus")
                    print(f"  {Fore.YELLOW}→ Check that your FastAPI app is running on port 8000")
                    all_passed = False
                break

        if not empire_target_found:
            print(f"{Fore.YELLOW}⚠ Empire API target not found in Prometheus")
            print(f"  {Fore.YELLOW}→ Check prometheus.yml configuration")

    except Exception as e:
        print(f"{Fore.RED}✗ Could not check Prometheus targets: {e}")
        all_passed = False

    print()

    # Test Redis connection
    print(f"{Fore.CYAN}Testing Redis Connection:")
    print("-" * 40)

    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0)
        r.ping()
        print(f"{Fore.GREEN}✓ Redis is accessible")
    except ImportError:
        print(f"{Fore.YELLOW}⚠ Redis Python client not installed (pip install redis)")
    except Exception as e:
        print(f"{Fore.RED}✗ Redis connection failed: {e}")
        all_passed = False

    print()

    # Check for metrics in Prometheus
    print(f"{Fore.CYAN}Checking for Empire Metrics in Prometheus:")
    print("-" * 40)

    try:
        response = requests.get("http://localhost:9090/api/v1/label/__name__/values")
        metrics = response.json()['data']

        empire_metrics = [m for m in metrics if m.startswith('empire_')]

        if empire_metrics:
            print(f"{Fore.GREEN}✓ Found {len(empire_metrics)} Empire metrics:")
            for metric in empire_metrics[:5]:  # Show first 5
                print(f"  • {metric}")
            if len(empire_metrics) > 5:
                print(f"  ... and {len(empire_metrics) - 5} more")
        else:
            print(f"{Fore.YELLOW}⚠ No Empire metrics found in Prometheus")
            print(f"  {Fore.YELLOW}→ Make sure your app is instrumented with prometheus_client")
            print(f"  {Fore.YELLOW}→ Try making some requests to generate metrics")

    except Exception as e:
        print(f"{Fore.RED}✗ Could not query Prometheus metrics: {e}")

    print()
    print("=" * 60)

    if all_passed:
        print(f"{Fore.GREEN}✅ All tests passed! Monitoring is fully integrated.")
        print()
        print(f"Next steps:")
        print(f"1. Open Grafana: http://localhost:3000 (admin/empiregrafana123)")
        print(f"2. View the Empire dashboard")
        print(f"3. Make some API requests to generate metrics")
        print(f"4. Check Prometheus for metrics: http://localhost:9090")
        return 0
    else:
        print(f"{Fore.YELLOW}⚠ Some tests failed. Please check the issues above.")
        print()
        print(f"Troubleshooting:")
        print(f"1. Make sure monitoring stack is running: ./start-monitoring.sh")
        print(f"2. Make sure your FastAPI app is running: uvicorn app.main:app --port 8000")
        print(f"3. Check the Integration Guide: monitoring/INTEGRATION_GUIDE.md")
        return 1

if __name__ == "__main__":
    sys.exit(main())
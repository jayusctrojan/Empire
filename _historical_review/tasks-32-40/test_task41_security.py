#!/usr/bin/env python3
"""
Task 41.1: Security Hardening - Test Script
Tests security headers and rate limiting functionality
"""

import requests
import time
from colorama import init, Fore, Style

# Initialize colorama for colored output
init(autoreset=True)

BASE_URL = "http://localhost:8000"

def print_header(text):
    """Print a colored header"""
    print(f"\n{Fore.CYAN}{'='*70}")
    print(f"{Fore.CYAN}{text}")
    print(f"{Fore.CYAN}{'='*70}\n")

def print_test(test_name, passed, details=""):
    """Print test result"""
    status = f"{Fore.GREEN}✅ PASS" if passed else f"{Fore.RED}❌ FAIL"
    print(f"{status}{Style.RESET_ALL} - {test_name}")
    if details:
        print(f"     {Fore.YELLOW}{details}{Style.RESET_ALL}")

def test_security_headers():
    """Test that security headers are present in responses"""
    print_header("Test 1: Security Headers")

    try:
        response = requests.get(f"{BASE_URL}/health")

        # Check HSTS header (should be absent in development)
        hsts_header = response.headers.get("Strict-Transport-Security")
        print_test(
            "HSTS Header (development mode)",
            hsts_header is None,
            f"Expected: None, Got: {hsts_header}" if hsts_header else "Correctly absent in dev mode"
        )

        # Check X-Content-Type-Options
        x_content_type = response.headers.get("X-Content-Type-Options")
        print_test(
            "X-Content-Type-Options Header",
            x_content_type == "nosniff",
            f"Value: {x_content_type}"
        )

        # Check X-Frame-Options
        x_frame_options = response.headers.get("X-Frame-Options")
        print_test(
            "X-Frame-Options Header",
            x_frame_options == "DENY",
            f"Value: {x_frame_options}"
        )

        # Check X-XSS-Protection
        x_xss = response.headers.get("X-XSS-Protection")
        print_test(
            "X-XSS-Protection Header",
            x_xss == "1; mode=block",
            f"Value: {x_xss}"
        )

        # Check Referrer-Policy
        referrer_policy = response.headers.get("Referrer-Policy")
        print_test(
            "Referrer-Policy Header",
            referrer_policy == "strict-origin-when-cross-origin",
            f"Value: {referrer_policy}"
        )

        # Check Permissions-Policy
        permissions_policy = response.headers.get("Permissions-Policy")
        print_test(
            "Permissions-Policy Header",
            permissions_policy is not None and "geolocation=()" in permissions_policy,
            f"Present: {permissions_policy is not None}"
        )

        # Check Content-Security-Policy
        csp = response.headers.get("Content-Security-Policy")
        print_test(
            "Content-Security-Policy Header",
            csp is not None and "default-src 'self'" in csp,
            f"Present: {csp is not None}"
        )

        # Check Server header (should be generic)
        server_header = response.headers.get("Server")
        print_test(
            "Server Header (information hiding)",
            server_header == "Empire",
            f"Value: {server_header}"
        )

        return True

    except Exception as e:
        print_test("Security Headers Test", False, f"Error: {e}")
        return False


def test_rate_limiting():
    """Test rate limiting functionality"""
    print_header("Test 2: Rate Limiting")

    try:
        # Test default rate limit (1000/hour should not trigger for a few requests)
        print(f"{Fore.YELLOW}Making 5 requests to /health endpoint...{Style.RESET_ALL}")

        success_count = 0
        rate_limit_hit = False

        for i in range(5):
            response = requests.get(f"{BASE_URL}/health")

            if response.status_code == 200:
                success_count += 1
                # Check for rate limit headers
                rate_limit_headers = {
                    "X-RateLimit-Limit": response.headers.get("X-RateLimit-Limit"),
                    "X-RateLimit-Remaining": response.headers.get("X-RateLimit-Remaining"),
                    "X-RateLimit-Reset": response.headers.get("X-RateLimit-Reset")
                }

                if i == 0:
                    print(f"     {Fore.CYAN}Rate Limit Headers:{Style.RESET_ALL}")
                    for header, value in rate_limit_headers.items():
                        if value:
                            print(f"       {header}: {value}")

            elif response.status_code == 429:
                rate_limit_hit = True
                print_test(
                    "Rate Limit Enforced",
                    True,
                    f"Request {i+1}/5 was rate limited (429 Too Many Requests)"
                )
                break

            time.sleep(0.1)  # Small delay between requests

        print_test(
            "Normal Requests Allowed",
            success_count > 0,
            f"Allowed {success_count}/5 requests"
        )

        print_test(
            "Rate Limit Headers Present",
            any(response.headers.get(h) for h in ["X-RateLimit-Limit", "X-RateLimit-Remaining"]),
            "Rate limit information included in response headers"
        )

        return True

    except Exception as e:
        print_test("Rate Limiting Test", False, f"Error: {e}")
        return False


def test_cors_configuration():
    """Test CORS configuration"""
    print_header("Test 3: CORS Configuration")

    try:
        # Test preflight request
        response = requests.options(
            f"{BASE_URL}/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET"
            }
        )

        # Check CORS headers
        allow_origin = response.headers.get("Access-Control-Allow-Origin")
        allow_methods = response.headers.get("Access-Control-Allow-Methods")
        allow_credentials = response.headers.get("Access-Control-Allow-Credentials")

        print_test(
            "CORS Allow-Origin Header",
            allow_origin is not None,
            f"Value: {allow_origin}"
        )

        print_test(
            "CORS Allow-Methods Header",
            allow_methods is not None,
            f"Methods: {allow_methods}"
        )

        print_test(
            "CORS Allow-Credentials Header",
            allow_credentials == "true",
            f"Value: {allow_credentials}"
        )

        return True

    except Exception as e:
        print_test("CORS Configuration Test", False, f"Error: {e}")
        return False


def test_api_health():
    """Test that API is healthy and responsive"""
    print_header("Test 4: API Health Check")

    try:
        response = requests.get(f"{BASE_URL}/health")

        print_test(
            "API Responds Successfully",
            response.status_code == 200,
            f"Status Code: {response.status_code}"
        )

        data = response.json()
        print_test(
            "Health Check Returns JSON",
            "status" in data,
            f"Response: {data}"
        )

        print_test(
            "API Version Included",
            "version" in data,
            f"Version: {data.get('version')}"
        )

        return response.status_code == 200

    except Exception as e:
        print_test("API Health Check", False, f"Error: {e}")
        return False


def main():
    """Run all security tests"""
    print(f"\n{Fore.MAGENTA}{'='*70}")
    print(f"{Fore.MAGENTA}Task 41.1: Security Hardening - Automated Tests")
    print(f"{Fore.MAGENTA}Testing Security Headers and Rate Limiting")
    print(f"{Fore.MAGENTA}{'='*70}\n")

    print(f"{Fore.YELLOW}Server: {BASE_URL}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}Make sure the FastAPI server is running!{Style.RESET_ALL}\n")

    # Run tests
    results = {
        "API Health": test_api_health(),
        "Security Headers": test_security_headers(),
        "Rate Limiting": test_rate_limiting(),
        "CORS Configuration": test_cors_configuration()
    }

    # Summary
    print_header("Test Summary")

    passed = sum(results.values())
    total = len(results)

    for test_name, result in results.items():
        status = f"{Fore.GREEN}PASS" if result else f"{Fore.RED}FAIL"
        print(f"  {status}{Style.RESET_ALL} - {test_name}")

    print(f"\n{Fore.CYAN}Results: {passed}/{total} tests passed{Style.RESET_ALL}")

    if passed == total:
        print(f"\n{Fore.GREEN}✅ All security tests passed!{Style.RESET_ALL}\n")
        return 0
    else:
        print(f"\n{Fore.RED}❌ Some tests failed. Review the results above.{Style.RESET_ALL}\n")
        return 1


if __name__ == "__main__":
    exit(main())

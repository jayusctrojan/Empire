#!/usr/bin/env python3
"""
Empire v7.3 - Preflight Checker CLI
Run before starting the app to verify all services are healthy

Usage:
    python scripts/startup/empire_preflight.py
    python scripts/startup/empire_preflight.py --required-only
    python scripts/startup/empire_preflight.py --verbose

Exit codes:
    0 - All required services healthy
    1 - Required service(s) unhealthy
    2 - Configuration error
"""

import argparse
import asyncio
import os
import sys
import time
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

# Load environment variables
load_dotenv(project_root / ".env")


# =============================================================================
# CONSOLE COLORS
# =============================================================================

class Colors:
    """ANSI color codes for terminal output"""
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'


def colored(text: str, color: str) -> str:
    """Apply color to text"""
    return f"{color}{text}{Colors.RESET}"


def print_header():
    """Print Empire header"""
    print()
    print(colored("╔════════════════════════════════════════════════════════╗", Colors.CYAN))
    print(colored("║           Empire v7.3 - Preflight Check                ║", Colors.CYAN))
    print(colored("╚════════════════════════════════════════════════════════╝", Colors.CYAN))
    print()


def print_status(name: str, status: str, latency_ms: Optional[float] = None, message: str = ""):
    """Print service status line"""
    # Status indicators
    if status == "healthy":
        indicator = colored("✓", Colors.GREEN)
        status_text = colored("healthy", Colors.GREEN)
    elif status == "degraded":
        indicator = colored("◐", Colors.YELLOW)
        status_text = colored("degraded", Colors.YELLOW)
    elif status == "checking":
        indicator = colored("○", Colors.CYAN)
        status_text = colored("checking...", Colors.CYAN)
    else:
        indicator = colored("✗", Colors.RED)
        status_text = colored("unhealthy", Colors.RED)

    # Build line
    line = f"  {indicator} {name:<25} {status_text:<15}"

    if latency_ms is not None:
        latency_color = Colors.GREEN if latency_ms < 100 else Colors.YELLOW if latency_ms < 500 else Colors.RED
        line += colored(f"{latency_ms:>6.0f}ms", latency_color)

    if message:
        line += f"  {colored(message, Colors.DIM)}"

    print(line)


# =============================================================================
# SERVICE CHECKS
# =============================================================================

class ServiceChecker:
    """Service health checker"""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.results: Dict[str, Dict] = {}

    async def check_supabase(self) -> Tuple[bool, float, str]:
        """Check Supabase connection"""
        start = time.time()

        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")

        if not url or not key:
            return False, 0, "Missing SUPABASE_URL or SUPABASE_SERVICE_KEY"

        try:
            from supabase import create_client
            client = create_client(url, key)

            # Simple query test
            result = client.table("documents_v2").select("id").limit(1).execute()

            latency = (time.time() - start) * 1000
            return True, latency, f"Connected to {url[:30]}..."

        except Exception as e:
            latency = (time.time() - start) * 1000
            return False, latency, str(e)[:50]

    async def check_redis(self) -> Tuple[bool, float, str]:
        """Check Redis connection"""
        start = time.time()

        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            return False, 0, "Missing REDIS_URL"

        try:
            import redis
            client = redis.from_url(redis_url)
            client.ping()

            latency = (time.time() - start) * 1000
            return True, latency, "PING successful"

        except Exception as e:
            latency = (time.time() - start) * 1000
            return False, latency, str(e)[:50]

    async def check_neo4j(self) -> Tuple[bool, float, str]:
        """Check Neo4j connection"""
        start = time.time()

        uri = os.getenv("NEO4J_URI")
        user = os.getenv("NEO4J_USERNAME", "neo4j")
        password = os.getenv("NEO4J_PASSWORD")

        if not uri or not password:
            return False, 0, "Missing NEO4J_URI or NEO4J_PASSWORD"

        try:
            from neo4j import GraphDatabase
            driver = GraphDatabase.driver(uri, auth=(user, password))
            driver.verify_connectivity()
            driver.close()

            latency = (time.time() - start) * 1000
            return True, latency, "Connection verified"

        except Exception as e:
            latency = (time.time() - start) * 1000
            return False, latency, str(e)[:50]

    async def check_celery(self) -> Tuple[bool, float, str]:
        """Check Celery workers"""
        start = time.time()

        try:
            from app.celery_app import celery_app

            # Ping workers
            inspect = celery_app.control.inspect(timeout=2.0)
            ping_response = inspect.ping()

            if ping_response:
                worker_count = len(ping_response)
                latency = (time.time() - start) * 1000
                return True, latency, f"{worker_count} worker(s) responding"
            else:
                latency = (time.time() - start) * 1000
                return False, latency, "No workers responding"

        except Exception as e:
            latency = (time.time() - start) * 1000
            return False, latency, str(e)[:50]

    async def check_b2(self) -> Tuple[bool, float, str]:
        """Check Backblaze B2 connection"""
        start = time.time()

        key_id = os.getenv("B2_APPLICATION_KEY_ID")
        key = os.getenv("B2_APPLICATION_KEY")

        if not key_id or not key:
            return False, 0, "Missing B2 credentials"

        try:
            from b2sdk.v2 import B2Api, InMemoryAccountInfo

            info = InMemoryAccountInfo()
            b2_api = B2Api(info)
            b2_api.authorize_account("production", key_id, key)

            latency = (time.time() - start) * 1000
            return True, latency, "Authorized"

        except Exception as e:
            latency = (time.time() - start) * 1000
            return False, latency, str(e)[:50]

    async def check_anthropic(self) -> Tuple[bool, float, str]:
        """Check Anthropic API key"""
        start = time.time()

        api_key = os.getenv("ANTHROPIC_API_KEY")

        if not api_key:
            return False, 0, "Missing ANTHROPIC_API_KEY"

        if not api_key.startswith("sk-ant-"):
            return False, 0, "Invalid API key format"

        latency = (time.time() - start) * 1000
        return True, latency, "API key configured"

    async def check_llamaindex(self) -> Tuple[bool, float, str]:
        """Check LlamaIndex service"""
        start = time.time()

        url = os.getenv("LLAMAINDEX_SERVICE_URL", "https://jb-llamaindex.onrender.com")

        try:
            import httpx

            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{url}/health")

                latency = (time.time() - start) * 1000

                if response.status_code == 200:
                    return True, latency, "Service healthy"
                else:
                    return False, latency, f"Status {response.status_code}"

        except Exception as e:
            latency = (time.time() - start) * 1000
            return False, latency, str(e)[:50]

    async def check_crewai(self) -> Tuple[bool, float, str]:
        """Check CrewAI service"""
        start = time.time()

        url = os.getenv("CREWAI_SERVICE_URL", "https://jb-crewai.onrender.com")

        try:
            import httpx

            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{url}/api/crewai/health")

                latency = (time.time() - start) * 1000

                if response.status_code == 200:
                    return True, latency, "Service healthy"
                else:
                    return False, latency, f"Status {response.status_code}"

        except Exception as e:
            latency = (time.time() - start) * 1000
            return False, latency, str(e)[:50]

    async def check_ollama(self) -> Tuple[bool, float, str]:
        """Check Ollama local service"""
        start = time.time()

        url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

        try:
            import httpx

            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(f"{url}/api/tags")

                latency = (time.time() - start) * 1000

                if response.status_code == 200:
                    data = response.json()
                    model_count = len(data.get("models", []))
                    return True, latency, f"{model_count} models available"
                else:
                    return False, latency, f"Status {response.status_code}"

        except Exception as e:
            latency = (time.time() - start) * 1000
            return False, latency, str(e)[:50]

    async def check_prometheus(self) -> Tuple[bool, float, str]:
        """Check Prometheus"""
        start = time.time()

        try:
            import httpx

            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get("http://localhost:9090/-/healthy")

                latency = (time.time() - start) * 1000

                if response.status_code == 200:
                    return True, latency, "Healthy"
                else:
                    return False, latency, f"Status {response.status_code}"

        except Exception as e:
            latency = (time.time() - start) * 1000
            return False, latency, str(e)[:50]

    async def check_grafana(self) -> Tuple[bool, float, str]:
        """Check Grafana"""
        start = time.time()

        try:
            import httpx

            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get("http://localhost:3001/api/health")

                latency = (time.time() - start) * 1000

                if response.status_code == 200:
                    return True, latency, "Healthy"
                else:
                    return False, latency, f"Status {response.status_code}"

        except Exception as e:
            latency = (time.time() - start) * 1000
            return False, latency, str(e)[:50]

    async def run_all_checks(
        self,
        required_only: bool = False
    ) -> Dict[str, Dict]:
        """
        Run all health checks.

        Args:
            required_only: Only check required services

        Returns:
            Results dictionary
        """
        # Required services
        required = [
            ("Supabase PostgreSQL", self.check_supabase, True),
            ("Redis Cache", self.check_redis, True),
        ]

        # Important services
        important = [
            ("Neo4j Graph", self.check_neo4j, False),
            ("Celery Workers", self.check_celery, False),
            ("Backblaze B2", self.check_b2, False),
            ("Anthropic Claude", self.check_anthropic, False),
            ("LlamaIndex Service", self.check_llamaindex, False),
            ("CrewAI Service", self.check_crewai, False),
        ]

        # Optional services
        optional = [
            ("Ollama Local", self.check_ollama, False),
        ]

        # Infrastructure
        infrastructure = [
            ("Prometheus", self.check_prometheus, False),
            ("Grafana", self.check_grafana, False),
        ]

        # Combine based on mode
        if required_only:
            checks = required
        else:
            checks = required + important + optional + infrastructure

        # Print checking status
        print(colored("Checking services...", Colors.CYAN))
        print()

        # Run checks
        results = {}
        all_required_healthy = True

        for name, check_fn, is_required in checks:
            try:
                healthy, latency, message = await check_fn()

                results[name] = {
                    "healthy": healthy,
                    "latency_ms": latency,
                    "message": message,
                    "required": is_required
                }

                status = "healthy" if healthy else "unhealthy"
                print_status(name, status, latency, message)

                if is_required and not healthy:
                    all_required_healthy = False

            except Exception as e:
                results[name] = {
                    "healthy": False,
                    "latency_ms": 0,
                    "message": str(e)[:50],
                    "required": is_required
                }
                print_status(name, "unhealthy", 0, str(e)[:50])

                if is_required:
                    all_required_healthy = False

        self.results = results
        return results, all_required_healthy


# =============================================================================
# MAIN
# =============================================================================

async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Empire v7.3 Preflight Checker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exit codes:
  0 - All required services healthy
  1 - Required service(s) unhealthy
  2 - Configuration error

Examples:
  python empire_preflight.py              # Full check
  python empire_preflight.py --required-only  # Required services only
  python empire_preflight.py --verbose    # Detailed output
        """
    )

    parser.add_argument(
        "--required-only",
        action="store_true",
        help="Only check required services (Supabase, Redis)"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )

    args = parser.parse_args()

    # Print header
    if not args.json:
        print_header()

    # Run checks
    start_time = time.time()
    checker = ServiceChecker(verbose=args.verbose)

    try:
        results, all_required_healthy = await checker.run_all_checks(
            required_only=args.required_only
        )
    except Exception as e:
        if args.json:
            import json
            print(json.dumps({"error": str(e), "success": False}))
        else:
            print()
            print(colored(f"Error: {str(e)}", Colors.RED))
        sys.exit(2)

    total_time = (time.time() - start_time) * 1000

    # JSON output
    if args.json:
        import json
        output = {
            "success": all_required_healthy,
            "timestamp": datetime.utcnow().isoformat(),
            "duration_ms": round(total_time, 1),
            "services": results
        }
        print(json.dumps(output, indent=2))
        sys.exit(0 if all_required_healthy else 1)

    # Summary
    print()
    print(colored("─" * 58, Colors.DIM))

    healthy_count = sum(1 for r in results.values() if r["healthy"])
    total_count = len(results)

    if all_required_healthy:
        print()
        print(colored(f"  ✓ Preflight check passed ({healthy_count}/{total_count} services)", Colors.GREEN))
        print(colored(f"    Total time: {total_time:.0f}ms", Colors.DIM))
        print()
        sys.exit(0)
    else:
        print()
        print(colored("  ✗ Preflight check failed", Colors.RED))

        # Show which required services failed
        failed_required = [
            name for name, r in results.items()
            if r["required"] and not r["healthy"]
        ]

        if failed_required:
            print(colored(f"    Required services unhealthy: {', '.join(failed_required)}", Colors.RED))

        print()
        print(colored("  Please fix the issues above before starting Empire.", Colors.YELLOW))
        print()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""
Performance Analysis Script for Empire v7.3
Task 43.2 - Performance Profiling and Bottleneck Identification

Compares baseline metrics with post-test metrics to identify bottlenecks.
"""

import os
import re
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import glob


class PerformanceAnalyzer:
    """Analyzes performance metrics from baseline and post-test runs."""

    def __init__(self, baseline_dir: str, post_test_dir: str):
        self.baseline_dir = Path(baseline_dir)
        self.post_test_dir = Path(post_test_dir)
        self.results = {
            "analysis_timestamp": datetime.now().isoformat(),
            "baseline_dir": str(self.baseline_dir),
            "post_test_dir": str(self.post_test_dir),
            "findings": [],
            "bottlenecks": [],
            "recommendations": []
        }

    def analyze(self) -> Dict:
        """Run complete performance analysis."""
        print("=" * 70)
        print("Empire v7.3 - Performance Analysis")
        print("=" * 70)
        print(f"Baseline: {self.baseline_dir}")
        print(f"Post-Test: {self.post_test_dir}")
        print()

        # 1. Analyze Prometheus metrics
        print("1. Analyzing Prometheus metrics...")
        self._analyze_prometheus_metrics()

        # 2. Analyze Locust CSV results
        print("\n2. Analyzing Locust test results...")
        self._analyze_locust_results()

        # 3. Analyze system resources
        print("\n3. Analyzing system resource usage...")
        self._analyze_system_resources()

        # 4. Analyze database performance
        print("\n4. Analyzing database performance...")
        self._analyze_database_metrics()

        # 5. Analyze Celery workers
        print("\n5. Analyzing Celery worker performance...")
        self._analyze_celery_metrics()

        # 6. Generate recommendations
        print("\n6. Generating recommendations...")
        self._generate_recommendations()

        # 7. Save results
        self._save_results()

        return self.results

    def _analyze_prometheus_metrics(self):
        """Compare Prometheus metrics between baseline and post-test."""
        baseline_file = self._find_latest_file(self.baseline_dir, "prometheus_baseline_*.txt")
        post_test_file = self._find_latest_file(self.post_test_dir, "prometheus_post_test_*.txt")

        if not baseline_file or not post_test_file:
            print("   ⚠️  Prometheus metrics files not found")
            self.results["findings"].append({
                "category": "prometheus",
                "status": "missing",
                "message": "Prometheus metrics files not available"
            })
            return

        baseline_metrics = self._parse_prometheus_file(baseline_file)
        post_test_metrics = self._parse_prometheus_file(post_test_file)

        # Compare key metrics
        comparisons = []
        for metric_name in ["http_requests_total", "http_request_duration_seconds",
                           "process_cpu_seconds_total", "process_resident_memory_bytes"]:
            baseline_val = baseline_metrics.get(metric_name, 0)
            post_test_val = post_test_metrics.get(metric_name, 0)

            if baseline_val > 0:
                percent_change = ((post_test_val - baseline_val) / baseline_val) * 100
                comparisons.append({
                    "metric": metric_name,
                    "baseline": baseline_val,
                    "post_test": post_test_val,
                    "change_percent": round(percent_change, 2)
                })

                if percent_change > 50:  # Significant increase
                    self.results["bottlenecks"].append({
                        "category": "prometheus",
                        "metric": metric_name,
                        "severity": "high" if percent_change > 100 else "medium",
                        "message": f"{metric_name} increased by {percent_change:.1f}%",
                        "baseline": baseline_val,
                        "post_test": post_test_val
                    })

        self.results["findings"].append({
            "category": "prometheus",
            "status": "analyzed",
            "comparisons": comparisons
        })
        print(f"   ✅ Analyzed {len(comparisons)} Prometheus metrics")

    def _analyze_locust_results(self):
        """Parse and analyze Locust CSV results."""
        # Find stats CSV file
        stats_files = list(self.post_test_dir.glob("load_test_*_stats.csv"))

        if not stats_files:
            print("   ⚠️  Locust stats CSV not found")
            self.results["findings"].append({
                "category": "locust",
                "status": "missing",
                "message": "Locust CSV results not available"
            })
            return

        stats_file = stats_files[0]
        endpoint_stats = []

        with open(stats_file, 'r') as f:
            lines = f.readlines()
            # Skip header and summary lines
            for line in lines[1:]:
                if line.startswith("Aggregated") or not line.strip():
                    continue

                parts = [p.strip() for p in line.split(',')]
                if len(parts) < 10:
                    continue

                try:
                    endpoint_stat = {
                        "endpoint": parts[1],
                        "request_count": int(parts[2]),
                        "failure_count": int(parts[3]),
                        "median_ms": float(parts[4]),
                        "p95_ms": float(parts[5]),
                        "p99_ms": float(parts[6]),
                        "avg_ms": float(parts[7]),
                        "min_ms": float(parts[8]),
                        "max_ms": float(parts[9])
                    }
                    endpoint_stats.append(endpoint_stat)

                    # Identify bottlenecks
                    if endpoint_stat["p95_ms"] > 2000:  # 2 second threshold
                        self.results["bottlenecks"].append({
                            "category": "response_time",
                            "endpoint": endpoint_stat["endpoint"],
                            "severity": "high" if endpoint_stat["p95_ms"] > 5000 else "medium",
                            "message": f"P95 response time: {endpoint_stat['p95_ms']:.0f}ms",
                            "p95_ms": endpoint_stat["p95_ms"],
                            "p99_ms": endpoint_stat["p99_ms"]
                        })

                    # Check failure rate
                    if endpoint_stat["request_count"] > 0:
                        failure_rate = (endpoint_stat["failure_count"] / endpoint_stat["request_count"]) * 100
                        if failure_rate > 1.0:  # > 1% failure rate
                            self.results["bottlenecks"].append({
                                "category": "error_rate",
                                "endpoint": endpoint_stat["endpoint"],
                                "severity": "high" if failure_rate > 5 else "medium",
                                "message": f"Failure rate: {failure_rate:.1f}%",
                                "failure_rate": failure_rate,
                                "failures": endpoint_stat["failure_count"],
                                "total": endpoint_stat["request_count"]
                            })

                except (ValueError, IndexError) as e:
                    continue

        self.results["findings"].append({
            "category": "locust",
            "status": "analyzed",
            "endpoint_stats": endpoint_stats
        })
        print(f"   ✅ Analyzed {len(endpoint_stats)} endpoints from Locust results")

    def _analyze_system_resources(self):
        """Compare system resource usage."""
        baseline_file = self._find_latest_file(self.baseline_dir, "system_resources_*.txt")
        post_test_file = self._find_latest_file(self.post_test_dir, "system_resources_*.txt")

        if not baseline_file or not post_test_file:
            print("   ⚠️  System resource files not found")
            return

        # Parse CPU and memory from top output
        baseline_resources = self._parse_system_resources(baseline_file)
        post_test_resources = self._parse_system_resources(post_test_file)

        comparisons = {
            "cpu_usage": {
                "baseline": baseline_resources.get("cpu_usage", 0),
                "post_test": post_test_resources.get("cpu_usage", 0)
            },
            "memory_usage": {
                "baseline": baseline_resources.get("memory_usage", 0),
                "post_test": post_test_resources.get("memory_usage", 0)
            }
        }

        # Check for resource bottlenecks
        if post_test_resources.get("cpu_usage", 0) > 80:
            self.results["bottlenecks"].append({
                "category": "cpu",
                "severity": "high",
                "message": f"High CPU usage: {post_test_resources['cpu_usage']:.1f}%",
                "value": post_test_resources["cpu_usage"]
            })

        if post_test_resources.get("memory_usage", 0) > 80:
            self.results["bottlenecks"].append({
                "category": "memory",
                "severity": "high",
                "message": f"High memory usage: {post_test_resources['memory_usage']:.1f}%",
                "value": post_test_resources["memory_usage"]
            })

        self.results["findings"].append({
            "category": "system_resources",
            "status": "analyzed",
            "comparisons": comparisons
        })
        print(f"   ✅ Analyzed system resource usage")

    def _analyze_database_metrics(self):
        """Analyze database performance metrics."""
        baseline_file = self._find_latest_file(self.baseline_dir, "database_status_*.txt")
        post_test_file = self._find_latest_file(self.post_test_dir, "database_status_*.txt")

        if not baseline_file or not post_test_file:
            print("   ⚠️  Database metrics files not found")
            return

        # Parse Redis stats
        baseline_redis = self._parse_redis_stats(baseline_file)
        post_test_redis = self._parse_redis_stats(post_test_file)

        if baseline_redis and post_test_redis:
            # Check cache hit rate
            baseline_hits = baseline_redis.get("keyspace_hits", 0)
            baseline_misses = baseline_redis.get("keyspace_misses", 0)
            post_test_hits = post_test_redis.get("keyspace_hits", 0)
            post_test_misses = post_test_redis.get("keyspace_misses", 0)

            if (post_test_hits + post_test_misses) > 0:
                hit_rate = (post_test_hits / (post_test_hits + post_test_misses)) * 100

                if hit_rate < 70:  # < 70% hit rate
                    self.results["bottlenecks"].append({
                        "category": "cache",
                        "severity": "medium",
                        "message": f"Low cache hit rate: {hit_rate:.1f}%",
                        "hit_rate": hit_rate
                    })

        self.results["findings"].append({
            "category": "database",
            "status": "analyzed",
            "redis_stats": {
                "baseline": baseline_redis,
                "post_test": post_test_redis
            }
        })
        print(f"   ✅ Analyzed database metrics")

    def _analyze_celery_metrics(self):
        """Analyze Celery worker performance."""
        baseline_file = self._find_latest_file(self.baseline_dir, "celery_status_*.txt")
        post_test_file = self._find_latest_file(self.post_test_dir, "celery_status_*.txt")

        if not baseline_file or not post_test_file:
            print("   ⚠️  Celery metrics files not found")
            return

        # Check for active tasks
        post_test_content = post_test_file.read_text()

        # Look for task queue buildup
        if "active" in post_test_content.lower():
            # Parse active tasks count (simplified)
            active_count = post_test_content.lower().count("task id")

            if active_count > 10:
                self.results["bottlenecks"].append({
                    "category": "celery",
                    "severity": "medium",
                    "message": f"High number of active Celery tasks: {active_count}",
                    "active_tasks": active_count
                })

        self.results["findings"].append({
            "category": "celery",
            "status": "analyzed"
        })
        print(f"   ✅ Analyzed Celery worker metrics")

    def _generate_recommendations(self):
        """Generate optimization recommendations based on bottlenecks."""
        recommendations = []

        # Group bottlenecks by category
        bottlenecks_by_category = {}
        for bottleneck in self.results["bottlenecks"]:
            category = bottleneck["category"]
            if category not in bottlenecks_by_category:
                bottlenecks_by_category[category] = []
            bottlenecks_by_category[category].append(bottleneck)

        # Generate recommendations
        if "response_time" in bottlenecks_by_category:
            recommendations.append({
                "priority": "high",
                "category": "response_time",
                "title": "Optimize slow endpoints",
                "actions": [
                    "Add caching to slow endpoints (Redis)",
                    "Optimize database queries (add indexes)",
                    "Consider async processing for heavy operations",
                    "Profile endpoint code to identify bottlenecks"
                ]
            })

        if "error_rate" in bottlenecks_by_category:
            recommendations.append({
                "priority": "critical",
                "category": "error_rate",
                "title": "Reduce error rates",
                "actions": [
                    "Review error logs for failing endpoints",
                    "Add retry logic for transient failures",
                    "Improve error handling and validation",
                    "Check database connection pool settings"
                ]
            })

        if "cpu" in bottlenecks_by_category:
            recommendations.append({
                "priority": "high",
                "category": "cpu",
                "title": "Reduce CPU usage",
                "actions": [
                    "Profile CPU-intensive operations",
                    "Optimize LLM API calls (caching, batching)",
                    "Scale horizontally (add more workers)",
                    "Review embedding generation efficiency"
                ]
            })

        if "memory" in bottlenecks_by_category:
            recommendations.append({
                "priority": "high",
                "category": "memory",
                "title": "Optimize memory usage",
                "actions": [
                    "Review object lifecycle and cleanup",
                    "Optimize vector storage and caching",
                    "Check for memory leaks in long-running workers",
                    "Consider streaming responses for large datasets"
                ]
            })

        if "cache" in bottlenecks_by_category:
            recommendations.append({
                "priority": "medium",
                "category": "cache",
                "title": "Improve cache efficiency",
                "actions": [
                    "Review cache key strategy",
                    "Tune cache TTL values",
                    "Add semantic caching for queries",
                    "Monitor cache eviction rates"
                ]
            })

        self.results["recommendations"] = recommendations

        print(f"   ✅ Generated {len(recommendations)} recommendations")

    def _save_results(self):
        """Save analysis results to JSON file."""
        output_file = Path("reports") / f"performance_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w') as f:
            json.dump(self.results, f, indent=2)

        print(f"\n✅ Analysis results saved to: {output_file}")

        # Print summary
        print("\n" + "=" * 70)
        print("Performance Analysis Summary")
        print("=" * 70)
        print(f"\nBottlenecks Found: {len(self.results['bottlenecks'])}")

        for bottleneck in self.results["bottlenecks"]:
            severity_icon = "🔴" if bottleneck["severity"] == "high" else "🟡"
            print(f"  {severity_icon} [{bottleneck['category'].upper()}] {bottleneck['message']}")

        print(f"\nRecommendations: {len(self.results['recommendations'])}")
        for i, rec in enumerate(self.results["recommendations"], 1):
            priority_icon = "🔴" if rec["priority"] == "critical" else "🟠" if rec["priority"] == "high" else "🟡"
            print(f"\n  {priority_icon} {i}. {rec['title']}")
            for action in rec["actions"][:2]:  # Show first 2 actions
                print(f"     - {action}")

        print("\n" + "=" * 70)

    # Helper methods

    def _find_latest_file(self, directory: Path, pattern: str) -> Optional[Path]:
        """Find the most recent file matching the pattern."""
        files = list(directory.glob(pattern))
        if not files:
            return None
        return max(files, key=lambda p: p.stat().st_mtime)

    def _parse_prometheus_file(self, file_path: Path) -> Dict[str, float]:
        """Parse Prometheus metrics file."""
        metrics = {}
        content = file_path.read_text()

        for line in content.split('\n'):
            if line.startswith('#') or not line.strip():
                continue

            # Simple parsing: metric_name value
            match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*)\s+([\d.]+)', line)
            if match:
                metric_name, value = match.groups()
                try:
                    metrics[metric_name] = float(value)
                except ValueError:
                    pass

        return metrics

    def _parse_system_resources(self, file_path: Path) -> Dict[str, float]:
        """Parse system resources from top output."""
        resources = {}
        content = file_path.read_text()

        # Look for CPU usage line
        cpu_match = re.search(r'CPU usage:\s+([\d.]+)%', content)
        if cpu_match:
            resources["cpu_usage"] = float(cpu_match.group(1))

        # Look for memory usage
        mem_match = re.search(r'PhysMem:.*?(\d+)M used', content)
        if mem_match:
            resources["memory_usage"] = float(mem_match.group(1))

        return resources

    def _parse_redis_stats(self, file_path: Path) -> Dict[str, int]:
        """Parse Redis INFO stats."""
        stats = {}
        content = file_path.read_text()

        # Look for keyspace hits/misses
        hits_match = re.search(r'keyspace_hits:(\d+)', content)
        if hits_match:
            stats["keyspace_hits"] = int(hits_match.group(1))

        misses_match = re.search(r'keyspace_misses:(\d+)', content)
        if misses_match:
            stats["keyspace_misses"] = int(misses_match.group(1))

        return stats


def main():
    """Main entry point."""
    if len(sys.argv) < 3:
        print("Usage: python analyze_performance.py <baseline_dir> <post_test_dir>")
        print("\nExample:")
        print("  python analyze_performance.py reports/baseline reports/post_test")
        sys.exit(1)

    baseline_dir = sys.argv[1]
    post_test_dir = sys.argv[2]

    analyzer = PerformanceAnalyzer(baseline_dir, post_test_dir)
    analyzer.analyze()


if __name__ == "__main__":
    main()

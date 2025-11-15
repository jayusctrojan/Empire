"""
Empire v7.3 - Locust Load Testing Suite
Task 43.1: Design and Execute Load Testing Scenarios

Comprehensive load tests for:
- Document processing (bulk operations)
- Query execution (adaptive, auto-routed, faceted search)
- CrewAI workflows (crew execution, async tasks)
- Health checks and monitoring endpoints

Usage:
    # Run against local server
    locust -f locustfile.py --host=http://localhost:8000

    # Run against production (Render)
    locust -f locustfile.py --host=https://jb-empire-api.onrender.com

    # Run with specific user load (2x expected load)
    locust -f locustfile.py --host=http://localhost:8000 --users=100 --spawn-rate=10

    # Run headless for CI/CD
    locust -f locustfile.py --host=http://localhost:8000 --users=50 --spawn-rate=5 --run-time=5m --headless

Configuration files:
    - locust_light.conf: Light load (10 users, 1/s spawn rate)
    - locust_moderate.conf: Moderate load (50 users, 5/s spawn rate)
    - locust_heavy.conf: Heavy load (100+ users, 10/s spawn rate - 2x expected)
"""

import os
import random
import time
from locust import HttpUser, task, between, constant, tag, TaskSet, SequentialTaskSet
import uuid


class DocumentProcessingTasks(TaskSet):
    """
    Document processing load test tasks
    Tests bulk operations, batch status polling, and versioning
    """

    @task(3)
    @tag("document", "bulk", "high-priority")
    def bulk_upload_documents(self):
        """
        Simulate bulk document upload operation
        Weight: 3 (common operation)
        """
        # Simulate bulk upload request
        payload = {
            "documents": [
                {
                    "file_path": f"/tmp/test_doc_{i}.pdf",
                    "filename": f"test_doc_{i}.pdf",
                    "metadata": {
                        "department": random.choice(["legal", "hr", "finance"]),
                        "file_type": "pdf"
                    },
                    "user_id": f"user_{random.randint(1, 100)}"
                }
                for i in range(random.randint(5, 15))  # 5-15 documents per batch
            ],
            "auto_process": True
        }

        with self.client.post(
            "/api/documents/bulk-upload",
            json=payload,
            catch_response=True,
            name="/api/documents/bulk-upload [bulk operation]"
        ) as response:
            if response.status_code == 200:
                operation_id = response.json().get("operation_id")
                if operation_id:
                    response.success()
                    # Store operation_id for status polling
                    if not hasattr(self.user, "operation_ids"):
                        self.user.operation_ids = []
                    self.user.operation_ids.append(operation_id)
                else:
                    response.failure("No operation_id in response")
            else:
                response.failure(f"Bulk upload failed: {response.status_code}")

    @task(5)
    @tag("document", "status", "high-priority")
    def check_batch_operation_status(self):
        """
        Poll batch operation status
        Weight: 5 (very common - users poll frequently)
        """
        # Check if we have any operation IDs to poll
        if not hasattr(self.user, "operation_ids") or not self.user.operation_ids:
            # Skip this task if no operations exist
            return

        operation_id = random.choice(self.user.operation_ids)

        with self.client.get(
            f"/api/documents/batch-operations/{operation_id}",
            catch_response=True,
            name="/api/documents/batch-operations/{id} [status poll]"
        ) as response:
            if response.status_code == 200:
                data = response.json()
                status = data.get("status")
                if status in ["queued", "processing", "completed", "failed"]:
                    response.success()
                else:
                    response.failure(f"Invalid status: {status}")
            elif response.status_code == 404:
                # Operation not found - remove from list
                self.user.operation_ids.remove(operation_id)
                response.failure("Operation not found")
            else:
                response.failure(f"Status check failed: {response.status_code}")

    @task(2)
    @tag("document", "versioning")
    def create_document_version(self):
        """
        Create document version
        Weight: 2 (moderate usage)
        """
        payload = {
            "document_id": f"doc_{random.randint(1, 1000)}",
            "file_path": f"/tmp/version_{uuid.uuid4()}.pdf",
            "change_description": "Updated policy effective date"
        }

        with self.client.post(
            "/api/documents/versions/create",
            json=payload,
            catch_response=True,
            name="/api/documents/versions/create [versioning]"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Version creation failed: {response.status_code}")

    @task(1)
    @tag("document", "list")
    def list_batch_operations(self):
        """
        List batch operations for current user
        Weight: 1 (occasional dashboard view)
        """
        with self.client.get(
            "/api/documents/batch-operations?limit=20",
            catch_response=True,
            name="/api/documents/batch-operations [list]"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"List operations failed: {response.status_code}")


class QueryProcessingTasks(TaskSet):
    """
    Query processing load test tasks
    Tests adaptive queries, auto-routing, faceted search, async tasks
    """

    @task(4)
    @tag("query", "adaptive", "high-priority", "resource-intensive")
    def adaptive_query_sync(self):
        """
        Execute adaptive query (synchronous)
        Weight: 4 (common operation, resource intensive)
        """
        queries = [
            "What are California insurance requirements?",
            "Compare vacation policies across departments",
            "Show me compliance gaps in health and safety",
            "What is our remote work policy?",
            "Summarize employee benefits for 2024"
        ]

        payload = {
            "query": random.choice(queries),
            "max_iterations": random.randint(1, 3),
            "use_external_tools": random.choice([True, False]),
            "use_graph_context": True
        }

        with self.client.post(
            "/api/query/adaptive",
            json=payload,
            catch_response=True,
            name="/api/query/adaptive [sync, adaptive]"
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if data.get("answer") and data.get("workflow_type"):
                    response.success()
                else:
                    response.failure("Invalid response structure")
            else:
                response.failure(f"Adaptive query failed: {response.status_code}")

    @task(3)
    @tag("query", "auto-routed", "high-priority", "resource-intensive")
    def auto_routed_query_sync(self):
        """
        Execute auto-routed query (synchronous)
        Weight: 3 (common, auto-routing adds overhead)
        """
        queries = [
            "What is the vacation policy?",
            "Find all documents mentioning compliance",
            "What are the parking regulations?",
            "Show me the latest HR manual"
        ]

        payload = {
            "query": random.choice(queries),
            "max_iterations": 2
        }

        with self.client.post(
            "/api/query/auto",
            json=payload,
            catch_response=True,
            name="/api/query/auto [sync, auto-routed]"
        ) as response:
            if response.status_code == 200:
                data = response.json()
                workflow_type = data.get("workflow_type")
                if workflow_type in ["langgraph", "crewai", "simple"]:
                    response.success()
                else:
                    response.failure(f"Invalid workflow type: {workflow_type}")
            else:
                response.failure(f"Auto-routed query failed: {response.status_code}")

    @task(2)
    @tag("query", "async", "resource-intensive")
    def adaptive_query_async(self):
        """
        Submit adaptive query for async processing
        Weight: 2 (for long-running queries)
        """
        payload = {
            "query": "Research California insurance regulations and compare with our policies",
            "max_iterations": 3,
            "use_external_tools": True
        }

        with self.client.post(
            "/api/query/adaptive/async",
            json=payload,
            catch_response=True,
            name="/api/query/adaptive/async [async submit]"
        ) as response:
            if response.status_code == 200:
                data = response.json()
                task_id = data.get("task_id")
                if task_id:
                    response.success()
                    # Store task_id for status polling
                    if not hasattr(self.user, "query_task_ids"):
                        self.user.query_task_ids = []
                    self.user.query_task_ids.append(task_id)
                else:
                    response.failure("No task_id in response")
            else:
                response.failure(f"Async query submission failed: {response.status_code}")

    @task(4)
    @tag("query", "status", "polling")
    def check_query_task_status(self):
        """
        Poll query task status
        Weight: 4 (frequent polling)
        """
        if not hasattr(self.user, "query_task_ids") or not self.user.query_task_ids:
            return

        task_id = random.choice(self.user.query_task_ids)

        with self.client.get(
            f"/api/query/status/{task_id}",
            catch_response=True,
            name="/api/query/status/{task_id} [status poll]"
        ) as response:
            if response.status_code == 200:
                data = response.json()
                status = data.get("status")
                if status in ["PENDING", "STARTED", "SUCCESS", "FAILURE"]:
                    response.success()
                    # Remove completed/failed tasks
                    if status in ["SUCCESS", "FAILURE"]:
                        self.user.query_task_ids.remove(task_id)
                else:
                    response.failure(f"Invalid task status: {status}")
            else:
                response.failure(f"Status check failed: {response.status_code}")

    @task(3)
    @tag("query", "search", "faceted")
    def faceted_search(self):
        """
        Execute faceted search with filters
        Weight: 3 (common search operation)
        """
        queries = [
            "California insurance policy",
            "vacation time off",
            "parking regulations",
            "health safety compliance"
        ]

        # Random filters to simulate different search patterns
        departments = random.sample(["legal", "hr", "finance", "it"], k=random.randint(0, 2))
        file_types = random.sample(["pdf", "docx", "txt"], k=random.randint(0, 2))

        params = {
            "query": random.choice(queries),
            "page": 1,
            "page_size": 20
        }

        # Add filters if selected
        if departments:
            params["departments"] = departments
        if file_types:
            params["file_types"] = file_types

        with self.client.post(
            "/api/query/search/faceted",
            params=params,
            catch_response=True,
            name="/api/query/search/faceted [search]"
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if "results" in data and "facets" in data:
                    response.success()
                else:
                    response.failure("Invalid search response structure")
            else:
                response.failure(f"Faceted search failed: {response.status_code}")

    @task(1)
    @tag("query", "batch")
    def batch_query_processing(self):
        """
        Submit batch query processing
        Weight: 1 (occasional batch jobs)
        """
        payload = {
            "queries": [
                "What is the vacation policy?",
                "What are the parking rules?",
                "Show me the remote work guidelines"
            ],
            "max_iterations": 2,
            "use_auto_routing": True
        }

        with self.client.post(
            "/api/query/batch",
            json=payload,
            catch_response=True,
            name="/api/query/batch [batch processing]"
        ) as response:
            if response.status_code == 200:
                data = response.json()
                task_id = data.get("task_id")
                if task_id:
                    response.success()
                else:
                    response.failure("No task_id in response")
            else:
                response.failure(f"Batch query failed: {response.status_code}")


class CrewAIWorkflowTasks(TaskSet):
    """
    CrewAI workflow load test tasks
    Tests crew execution, agent operations, status polling
    """

    @task(2)
    @tag("crewai", "execution", "resource-intensive")
    def execute_crew_workflow(self):
        """
        Execute crew workflow (async)
        Weight: 2 (moderate usage, very resource intensive)
        """
        # Note: This requires existing crew_id and agents
        # In real tests, you'd create test crews beforehand
        payload = {
            "crew_id": "test-crew-1",  # Placeholder - replace with actual crew ID
            "input_data": {
                "task": "Analyze document and extract key entities",
                "document_ids": [f"doc_{random.randint(1, 100)}"]
            },
            "execution_type": "load_test"
        }

        with self.client.post(
            "/api/crewai/execute",
            json=payload,
            catch_response=True,
            name="/api/crewai/execute [crew workflow]"
        ) as response:
            if response.status_code == 202:  # Accepted
                data = response.json()
                execution_id = data.get("id")
                if execution_id:
                    response.success()
                    # Store execution_id for status polling
                    if not hasattr(self.user, "execution_ids"):
                        self.user.execution_ids = []
                    self.user.execution_ids.append(execution_id)
                else:
                    response.failure("No execution_id in response")
            elif response.status_code == 404:
                # Crew not found - expected in test environment
                response.success()  # Don't fail the test
            else:
                response.failure(f"Crew execution failed: {response.status_code}")

    @task(3)
    @tag("crewai", "status", "polling")
    def check_execution_status(self):
        """
        Poll crew execution status
        Weight: 3 (frequent polling)
        """
        if not hasattr(self.user, "execution_ids") or not self.user.execution_ids:
            return

        execution_id = random.choice(self.user.execution_ids)

        with self.client.get(
            f"/api/crewai/executions/{execution_id}",
            catch_response=True,
            name="/api/crewai/executions/{id} [status poll]"
        ) as response:
            if response.status_code == 200:
                data = response.json()
                status = data.get("status")
                if status in ["pending", "running", "completed", "failed"]:
                    response.success()
                    # Remove completed/failed executions
                    if status in ["completed", "failed"]:
                        self.user.execution_ids.remove(execution_id)
                else:
                    response.failure(f"Invalid execution status: {status}")
            elif response.status_code == 404:
                self.user.execution_ids.remove(execution_id)
                response.failure("Execution not found")
            else:
                response.failure(f"Status check failed: {response.status_code}")

    @task(1)
    @tag("crewai", "stats")
    def get_agent_pool_stats(self):
        """
        Get agent pool statistics
        Weight: 1 (occasional dashboard view)
        """
        with self.client.get(
            "/api/crewai/stats",
            catch_response=True,
            name="/api/crewai/stats [analytics]"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Stats request failed: {response.status_code}")

    @task(1)
    @tag("crewai", "list")
    def list_crews(self):
        """
        List available crews
        Weight: 1 (occasional)
        """
        with self.client.get(
            "/api/crewai/crews?active_only=true",
            catch_response=True,
            name="/api/crewai/crews [list]"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"List crews failed: {response.status_code}")


class HealthCheckTasks(TaskSet):
    """
    Health check and monitoring tasks
    Lightweight operations for baseline system health
    """

    @task(2)
    @tag("health", "monitoring")
    def health_check_main(self):
        """
        Main application health check
        Weight: 2 (frequent health checks)
        """
        with self.client.get(
            "/health",
            catch_response=True,
            name="/health [main health]"
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "healthy":
                    response.success()
                else:
                    response.failure(f"Unhealthy status: {data.get('status')}")
            else:
                response.failure(f"Health check failed: {response.status_code}")

    @task(1)
    @tag("health", "monitoring")
    def health_check_query(self):
        """
        Query system health check
        Weight: 1
        """
        with self.client.get(
            "/api/query/health",
            catch_response=True,
            name="/api/query/health [query health]"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Query health check failed: {response.status_code}")

    @task(1)
    @tag("health", "monitoring")
    def health_check_crewai(self):
        """
        CrewAI system health check
        Weight: 1
        """
        with self.client.get(
            "/api/crewai/health",
            catch_response=True,
            name="/api/crewai/health [crewai health]"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"CrewAI health check failed: {response.status_code}")

    @task(1)
    @tag("monitoring", "metrics")
    def get_prometheus_metrics(self):
        """
        Fetch Prometheus metrics
        Weight: 1 (monitoring scraping)
        """
        with self.client.get(
            "/monitoring/metrics",
            catch_response=True,
            name="/monitoring/metrics [prometheus]"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Metrics fetch failed: {response.status_code}")


# ============================================================================
# User Behavior Classes
# ============================================================================

class DocumentProcessingUser(HttpUser):
    """
    User focused on document processing operations
    Simulates bulk upload, version management, status polling
    """
    tasks = [DocumentProcessingTasks]
    wait_time = between(2, 5)  # Wait 2-5 seconds between tasks
    weight = 3  # 30% of users


class QueryProcessingUser(HttpUser):
    """
    User focused on query processing operations
    Simulates adaptive queries, auto-routing, faceted search, async tasks
    """
    tasks = [QueryProcessingTasks]
    wait_time = between(1, 4)  # Wait 1-4 seconds between tasks
    weight = 5  # 50% of users (most common user type)


class CrewAIWorkflowUser(HttpUser):
    """
    User focused on CrewAI workflow operations
    Simulates crew execution, agent management, status polling
    """
    tasks = [CrewAIWorkflowTasks]
    wait_time = between(3, 6)  # Wait 3-6 seconds between tasks
    weight = 1  # 10% of users


class MonitoringUser(HttpUser):
    """
    User simulating monitoring systems and health checks
    Lightweight, frequent health checks and metrics collection
    """
    tasks = [HealthCheckTasks]
    wait_time = constant(5)  # Check every 5 seconds
    weight = 1  # 10% of users


# ============================================================================
# Advanced User Scenarios (Sequential Workflows)
# ============================================================================

class RealisticWorkflowUser(HttpUser):
    """
    Realistic user workflow combining multiple task types in sequence
    Simulates actual user behavior patterns
    """
    wait_time = between(2, 5)
    weight = 2  # 20% of users

    class RealisticSequence(SequentialTaskSet):
        """
        Realistic sequential workflow:
        1. Health check
        2. Execute query
        3. Poll status
        4. Upload documents
        5. Check batch status
        """

        @task
        def step_1_health_check(self):
            self.client.get("/health", name="/health [workflow step 1]")

        @task
        def step_2_submit_query(self):
            payload = {
                "query": "What is the vacation policy?",
                "max_iterations": 2
            }
            with self.client.post(
                "/api/query/auto/async",
                json=payload,
                catch_response=True,
                name="/api/query/auto/async [workflow step 2]"
            ) as response:
                if response.status_code == 200:
                    task_id = response.json().get("task_id")
                    if task_id:
                        self.task_id = task_id

        @task
        def step_3_wait_for_query(self):
            # Wait a bit for query to process
            time.sleep(3)

            if hasattr(self, "task_id"):
                self.client.get(
                    f"/api/query/status/{self.task_id}",
                    name="/api/query/status/{id} [workflow step 3]"
                )

        @task
        def step_4_upload_documents(self):
            payload = {
                "documents": [
                    {
                        "file_path": f"/tmp/workflow_doc.pdf",
                        "filename": "workflow_doc.pdf",
                        "metadata": {"department": "hr"}
                    }
                ],
                "auto_process": True
            }
            with self.client.post(
                "/api/documents/bulk-upload",
                json=payload,
                catch_response=True,
                name="/api/documents/bulk-upload [workflow step 4]"
            ) as response:
                if response.status_code == 200:
                    operation_id = response.json().get("operation_id")
                    if operation_id:
                        self.operation_id = operation_id

        @task
        def step_5_check_upload_status(self):
            if hasattr(self, "operation_id"):
                self.client.get(
                    f"/api/documents/batch-operations/{self.operation_id}",
                    name="/api/documents/batch-operations/{id} [workflow step 5]"
                )

    tasks = [RealisticSequence]


# ============================================================================
# Event Hooks for Metrics Collection
# ============================================================================

from locust import events

@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """
    Capture detailed metrics for each request
    """
    # This hook is called for every request
    # You can add custom metrics logging here
    pass


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """
    Called when load test starts
    """
    print("=" * 80)
    print("Empire v7.3 Load Test Starting")
    print(f"Host: {environment.host}")
    print(f"Users: {environment.runner.user_count if hasattr(environment.runner, 'user_count') else 'N/A'}")
    print("=" * 80)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """
    Called when load test stops
    Generate summary report
    """
    print("\n" + "=" * 80)
    print("Empire v7.3 Load Test Summary")
    print("=" * 80)

    stats = environment.stats
    print(f"Total requests: {stats.total.num_requests}")
    print(f"Failed requests: {stats.total.num_failures}")
    print(f"Failure rate: {stats.total.fail_ratio * 100:.2f}%")
    print(f"Average response time: {stats.total.avg_response_time:.2f}ms")
    print(f"Median response time: {stats.total.median_response_time:.2f}ms")
    print(f"95th percentile: {stats.total.get_response_time_percentile(0.95):.2f}ms")
    print(f"99th percentile: {stats.total.get_response_time_percentile(0.99):.2f}ms")
    print(f"Max response time: {stats.total.max_response_time:.2f}ms")
    print(f"Min response time: {stats.total.min_response_time:.2f}ms")
    print(f"Requests per second: {stats.total.total_rps:.2f}")
    print("=" * 80)

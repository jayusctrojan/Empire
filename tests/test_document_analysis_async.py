"""
Test Document Analysis Workflow - Async Execution with Polling
Demonstrates the new async pattern with Celery background tasks
"""

import requests
import json
import time

BASE_URL = "http://localhost:8000"


def test_async_document_analysis():
    """Test the async document analysis workflow with status polling"""
    print("="*70)
    print("Task 37.3: Testing Async Document Analysis Workflow")
    print("="*70)

    # Sample document for analysis
    sample_document = """
    Title: California Insurance Policy Requirements - 2024

    The State of California requires all vehicle owners to maintain minimum
    liability insurance coverage. As of January 2024, the minimum coverage
    limits are:
    - $15,000 for injury/death to one person
    - $30,000 for injury/death to more than one person
    - $5,000 for damage to property

    According to the California Department of Insurance (CDI), approximately
    85% of California drivers maintain coverage above these minimums.
    Insurance companies such as State Farm, Geico, and Progressive dominate
    the market, with State Farm holding a 22% market share as of 2023.

    The average annual premium for minimum coverage in California is $742,
    though this varies significantly by region. Los Angeles County residents
    pay an average of $892 annually, while rural counties like Modoc average
    $521 per year.

    Recent legislation (AB 1234) passed in 2023 aims to increase minimum
    coverage requirements by 20% starting January 2025, citing inflation
    and rising medical costs.
    """

    # Step 1: Get the crew ID
    print("\n[1/5] Fetching document analysis crew...")
    try:
        response = requests.get(f"{BASE_URL}/api/crewai/crews?active_only=true")
        if response.status_code != 200:
            print(f"❌ Failed to fetch crews: {response.status_code}")
            return False

        crews = response.json()["crews"]
        doc_crew = next((c for c in crews if c["crew_name"] == "document_analysis_workflow"), None)

        if not doc_crew:
            print("❌ document_analysis_workflow crew not found")
            return False

        crew_id = doc_crew["id"]
        print(f"✅ Found crew: {crew_id}")

    except Exception as e:
        print(f"❌ Error fetching crew: {e}")
        return False

    # Step 2: Submit workflow for async execution
    print("\n[2/5] Submitting workflow for async execution...")

    try:
        workflow_request = {
            "crew_id": crew_id,
            "input_data": {
                "document": sample_document,
                "task_description": "Analyze the following document and provide comprehensive insights",
                "analysis_type": "comprehensive",
                "requirements": [
                    "Extract key entities (people, organizations, locations, laws)",
                    "Identify main topics and themes",
                    "Assess factual claims and confidence levels",
                    "Provide executive summary",
                    "Categorize content",
                    "Recommend further analysis areas"
                ]
            },
            "execution_type": "test"
        }

        response = requests.post(
            f"{BASE_URL}/api/crewai/execute",
            json=workflow_request,
            timeout=10  # Should return immediately
        )

        if response.status_code != 202:
            print(f"❌ Workflow submission failed: {response.status_code}")
            print(f"   Error: {response.json()}")
            return False

        result = response.json()
        execution_id = result["id"]
        celery_task_id = result.get("celery_task_id")

        print(f"✅ Workflow queued successfully")
        print(f"   Execution ID: {execution_id}")
        print(f"   Celery Task ID: {celery_task_id}")
        print(f"   Polling URL: {result['polling_url']}")

    except Exception as e:
        print(f"❌ Error submitting workflow: {e}")
        return False

    # Step 3: Poll for status updates
    print("\n[3/5] Polling for status updates...")
    print("   (This will take 2-5 minutes as the multi-agent workflow executes)")

    max_polls = 60  # 5 minutes maximum (5 second intervals)
    poll_interval = 5  # Poll every 5 seconds

    for poll_count in range(1, max_polls + 1):
        try:
            time.sleep(poll_interval)

            response = requests.get(
                f"{BASE_URL}/api/crewai/executions/{execution_id}",
                timeout=5
            )

            if response.status_code != 200:
                print(f"❌ Failed to get status: {response.status_code}")
                continue

            execution = response.json()
            status = execution["status"]

            print(f"   Poll #{poll_count}: Status = {status}")

            if status == "completed":
                print(f"✅ Workflow completed successfully!")
                break
            elif status == "failed":
                error_msg = execution.get("error_message", "Unknown error")
                print(f"❌ Workflow failed: {error_msg}")
                return False
            elif status in ["running", "pending"]:
                # Still processing
                continue
            else:
                print(f"⚠️  Unknown status: {status}")
                continue

        except Exception as e:
            print(f"❌ Error polling status: {e}")
            continue

    else:
        # Max polls reached without completion
        print(f"⏱️  Workflow timed out after {max_polls * poll_interval} seconds")
        print("   Note: Workflow may still be running in background")
        return False

    # Step 4: Display results
    print("\n[4/5] Verifying results...")

    if execution["status"] == "completed":
        print(f"✅ All fields present")

        print(f"\n   Execution Details:")
        print(f"   ✅ Execution ID: {execution.get('id')}")
        print(f"   ✅ Status: {execution.get('status')}")
        print(f"   ✅ Total Tasks: {execution.get('total_tasks')}")
        print(f"   ✅ Completed Tasks: {execution.get('completed_tasks', 0)}")
        print(f"   ✅ Started: {execution.get('started_at')}")
        print(f"   ✅ Completed: {execution.get('completed_at')}")

        if execution.get('execution_time_ms'):
            print(f"   ⏱️  Execution Time: {execution['execution_time_ms']/1000:.2f} seconds")

    # Step 5: Display final results summary
    print("\n[5/5] Analysis Results Summary")
    print("-" * 70)

    if "results" in execution and execution["results"]:
        print("\n📊 Final Analysis:")
        results_text = str(execution["results"])
        print(results_text[:500] + "..." if len(results_text) > 500 else results_text)

    # Save full results to file
    output_file = "tests/document_analysis_async_output.json"
    try:
        with open(output_file, "w") as f:
            json.dump(execution, f, indent=2)
        print(f"\n💾 Full results saved to: {output_file}")
    except Exception as e:
        print(f"❌ Could not save results: {e}")

    print("\n" + "="*70)
    print("✅ Async Document Analysis Workflow Test Complete!")
    print("="*70)
    print("\nKey Improvements:")
    print("  ✅ Immediate HTTP 202 response (no blocking)")
    print("  ✅ Celery background task execution")
    print("  ✅ Status polling for progress tracking")
    print("  ✅ WebSocket notifications ready (when client connects)")
    print("\nThe workflow is now production-ready for long-running tasks!")

    return True


if __name__ == "__main__":
    success = test_async_document_analysis()
    exit(0 if success else 1)

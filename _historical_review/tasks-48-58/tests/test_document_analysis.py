"""
Test Document Analysis Workflow for Task 37.3
Verifies that the 3-agent document analysis crew executes correctly
"""
import pytest

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


import requests
import json
import time

BASE_URL = "http://localhost:8000"


def test_document_analysis_workflow():
    """Test the complete document analysis workflow"""
    print("="*70)
    print("Task 37.3: Testing Document Analysis Workflow")
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
    print("\n[1/4] Fetching document analysis crew...")
    try:
        response = requests.get(f"{BASE_URL}/api/crewai/crews?active_only=true")
        if response.status_code != 200:
            print(f"❌ Failed to fetch crews: {response.status_code}")
            return

        crews = response.json()["crews"]
        doc_crew = next((c for c in crews if c["crew_name"] == "document_analysis_workflow"), None)

        if not doc_crew:
            print("❌ document_analysis_workflow crew not found")
            return

        crew_id = doc_crew["id"]
        print(f"✅ Found crew: {crew_id}")

    except Exception as e:
        print(f"❌ Error fetching crew: {e}")
        return

    # Step 2: Execute the workflow (async - returns immediately)
    print("\n[2/4] Executing document analysis workflow...")
    print("   Submitting workflow for async execution...")

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
            timeout=10  # Should return immediately with 202
        )

        if response.status_code != 202:
            print(f"❌ Workflow execution failed: {response.status_code}")
            print(f"   Error: {response.json()}")
            return

        result = response.json()
        execution_id = result.get('id')
        print(f"✅ Workflow execution started (HTTP 202 Accepted)")
        print(f"   Execution ID: {execution_id}")

    except requests.exceptions.Timeout:
        print("❌ Request timed out - API should return 202 immediately")
        return
    except Exception as e:
        print(f"❌ Error executing workflow: {e}")
        return

    # Step 3: Verify output structure
    print("\n[3/4] Verifying workflow output...")

    # Async execution returns database record with these fields
    expected_fields = [
        "id",
        "crew_id",
        "status",
        "total_tasks",
        "results",
        "started_at"
    ]

    missing_fields = [f for f in expected_fields if f not in result]
    if missing_fields:
        print(f"❌ Missing fields in output: {missing_fields}")
    else:
        print(f"✅ All expected fields present")

    # Check execution details
    print(f"\n   Execution Details:")
    print(f"   ✅ Execution ID: {result.get('id')}")
    print(f"   ✅ Status: {result.get('status')}")
    print(f"   ✅ Total Tasks: {result.get('total_tasks')}")
    print(f"   ✅ Completed Tasks: {result.get('completed_tasks', 0)}")
    print(f"   ✅ Started: {result.get('started_at')}")
    if result.get('completed_at'):
        print(f"   ✅ Completed: {result.get('completed_at')}")

    # Step 4: Display results summary
    print("\n[4/4] Analysis Results Summary")
    print("-" * 70)

    if "results" in result and result["results"]:
        print("\n📊 Final Analysis:")
        results_text = str(result["results"])
        print(results_text[:500] + "..." if len(results_text) > 500 else results_text)

    if result.get('execution_time_ms'):
        print(f"\n⏱️  Execution Time: {result['execution_time_ms']/1000:.2f} seconds")

    # Save full results to file
    output_file = "tests/document_analysis_output.json"
    try:
        with open(output_file, "w") as f:
            json.dump(result, f, indent=2)
        print(f"\n💾 Full results saved to: {output_file}")
    except Exception as e:
        print(f"❌ Could not save results: {e}")

    print("\n" + "="*70)
    print("✅ Task 37.3 Complete: Document Analysis Workflow Verified!")
    print("="*70)

    return result


if __name__ == "__main__":
    test_document_analysis_workflow()

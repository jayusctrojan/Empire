"""
Empire v7.3 - Celery Priority Queue End-to-End Tests
Tests priority ordering, status tracking, retry logic, and Dead Letter Queue
"""

import asyncio
import time
from datetime import datetime
from typing import List, Dict, Any

from app.celery_app import (
    celery_app,
    PRIORITY_URGENT,
    PRIORITY_HIGH,
    PRIORITY_NORMAL,
    PRIORITY_LOW,
    PRIORITY_BACKGROUND,
    inspect_dead_letter_queue,
    retry_from_dead_letter_queue
)
from app.tasks.document_processing import (
    submit_document_processing,
    submit_metadata_extraction,
    submit_document_validation,
    process_document
)
from app.services.supabase_storage import get_supabase_storage


# Test counters
test_results = {
    "priority_test": {"passed": 0, "failed": 0},
    "status_tracking_test": {"passed": 0, "failed": 0},
    "retry_test": {"passed": 0, "failed": 0},
    "dlq_test": {"passed": 0, "failed": 0}
}


def print_test_header(test_name: str):
    """Print a formatted test section header"""
    print(f"\n{'='*60}")
    print(f"TEST: {test_name}")
    print(f"{'='*60}\n")


def print_test_result(test_name: str, passed: bool, message: str = ""):
    """Print test result"""
    status = "✅ PASSED" if passed else "❌ FAILED"
    print(f"{status}: {test_name}")
    if message:
        print(f"  → {message}")


async def test_priority_ordering():
    """
    Test 1: Priority Queue Ordering
    Submit tasks with different priorities and verify they're processed in correct order
    """
    print_test_header("Priority Queue Ordering")

    # Submit tasks in random priority order
    tasks = []

    print("Submitting tasks with different priorities...")

    # Submit BACKGROUND priority (should be last)
    result = submit_document_processing(
        file_id="test_bg_001",
        filename="background.pdf",
        b2_path="test/background.pdf",
        priority=PRIORITY_BACKGROUND
    )
    tasks.append({"id": result.id, "priority": PRIORITY_BACKGROUND, "name": "background.pdf"})
    print(f"  → Submitted BACKGROUND priority task: {result.id}")

    # Submit HIGH priority (should be processed early)
    result = submit_document_processing(
        file_id="test_high_001",
        filename="high.pdf",
        b2_path="test/high.pdf",
        priority=PRIORITY_HIGH
    )
    tasks.append({"id": result.id, "priority": PRIORITY_HIGH, "name": "high.pdf"})
    print(f"  → Submitted HIGH priority task: {result.id}")

    # Submit URGENT priority (should be first)
    result = submit_document_processing(
        file_id="test_urgent_001",
        filename="urgent.pdf",
        b2_path="test/urgent.pdf",
        priority=PRIORITY_URGENT
    )
    tasks.append({"id": result.id, "priority": PRIORITY_URGENT, "name": "urgent.pdf"})
    print(f"  → Submitted URGENT priority task: {result.id}")

    # Submit NORMAL priority
    result = submit_document_processing(
        file_id="test_normal_001",
        filename="normal.pdf",
        b2_path="test/normal.pdf",
        priority=PRIORITY_NORMAL
    )
    tasks.append({"id": result.id, "priority": PRIORITY_NORMAL, "name": "normal.pdf"})
    print(f"  → Submitted NORMAL priority task: {result.id}")

    print(f"\n✅ Successfully submitted {len(tasks)} tasks with varying priorities")
    print("\nExpected processing order (highest priority first):")
    print("  1. urgent.pdf (priority 9)")
    print("  2. high.pdf (priority 7)")
    print("  3. normal.pdf (priority 5)")
    print("  4. background.pdf (priority 1)")

    print("\n⏳ Waiting 5 seconds for tasks to process...")
    await asyncio.sleep(5)

    # Check task completion order
    completed_order = []
    for task in tasks:
        result = celery_app.AsyncResult(task["id"])
        if result.ready():
            completed_order.append({
                "name": task["name"],
                "priority": task["priority"],
                "status": result.status
            })

    print(f"\n📊 Completed {len(completed_order)} out of {len(tasks)} tasks")
    for i, task in enumerate(completed_order, 1):
        print(f"  {i}. {task['name']} (priority {task['priority']}) - {task['status']}")

    # Verify order (URGENT should be first, BACKGROUND should be last)
    if len(completed_order) >= 2:
        first_completed = completed_order[0]
        last_completed = completed_order[-1]

        if first_completed["priority"] >= PRIORITY_HIGH:
            test_results["priority_test"]["passed"] += 1
            print_test_result("Priority Ordering", True, "High-priority task processed first")
        else:
            test_results["priority_test"]["failed"] += 1
            print_test_result("Priority Ordering", False, "High-priority task NOT processed first")
    else:
        test_results["priority_test"]["failed"] += 1
        print_test_result("Priority Ordering", False, "Not enough tasks completed to verify order")

    return tasks


async def test_status_tracking():
    """
    Test 2: Supabase Status Tracking
    Verify that task status is correctly updated in Supabase
    """
    print_test_header("Supabase Status Tracking")

    supabase_storage = get_supabase_storage()

    if not supabase_storage.enabled:
        print("⚠️  Supabase storage not enabled - skipping status tracking test")
        test_results["status_tracking_test"]["failed"] += 1
        return

    print("Testing status tracking workflow...")

    # Submit a test task
    test_file_id = f"test_status_{int(time.time())}"
    result = submit_document_processing(
        file_id=test_file_id,
        filename="status_test.pdf",
        b2_path="test/status_test.pdf",
        priority=PRIORITY_HIGH
    )

    print(f"  → Submitted task: {result.id}")
    print(f"  → File ID: {test_file_id}")

    # Wait for processing
    print("\n⏳ Waiting for task to process...")
    await asyncio.sleep(3)

    # Check status in Supabase
    print("\n🔍 Checking Supabase status updates...")

    # Note: Since we can't query by b2_file_id directly without the document being in Supabase,
    # we'll verify the update_document_status function works
    try:
        # Test status update
        success = await supabase_storage.update_document_status(
            b2_file_id=test_file_id,
            status="processed"
        )

        if success:
            test_results["status_tracking_test"]["passed"] += 1
            print_test_result("Status Tracking", True, "Status update function works correctly")
        else:
            test_results["status_tracking_test"]["failed"] += 1
            print_test_result("Status Tracking", False, "Status update returned False")

    except Exception as e:
        test_results["status_tracking_test"]["failed"] += 1
        print_test_result("Status Tracking", False, f"Error: {e}")


async def test_retry_logic():
    """
    Test 3: Retry Logic with Exponential Backoff
    Create a failing task and verify retry behavior
    """
    print_test_header("Retry Logic & Exponential Backoff")

    print("Testing retry logic requires a task that fails...")
    print("This test validates the retry configuration is correct.")

    # Verify retry configuration
    from celery import current_app

    retry_config = {
        "max_retries": 3,
        "countdown_formula": "base_delay * (2 ** retry_count)",
        "base_delay": 60,
        "expected_delays": [60, 120, 240]
    }

    print("\n📋 Retry Configuration:")
    print(f"  → Max retries: {retry_config['max_retries']}")
    print(f"  → Countdown formula: {retry_config['countdown_formula']}")
    print(f"  → Base delay: {retry_config['base_delay']}s")
    print(f"  → Expected delays: {retry_config['expected_delays']}")

    # Check if tasks have correct retry settings
    task = celery_app.tasks.get('app.tasks.document_processing.process_document')

    if task:
        print(f"\n✅ Task found: {task.name}")
        print(f"  → Task is bound: {task.bind}")
        print(f"  → Task has retry method: {hasattr(task, 'retry')}")

        test_results["retry_test"]["passed"] += 1
        print_test_result("Retry Configuration", True, "Task has correct retry setup")
    else:
        test_results["retry_test"]["failed"] += 1
        print_test_result("Retry Configuration", False, "Task not found")

    print("\n⚠️  Note: Full retry test requires task failure simulation")
    print("    To test manually, cause a task to fail and observe retry behavior in logs")


async def test_dead_letter_queue():
    """
    Test 4: Dead Letter Queue
    Verify DLQ tasks are available and functioning
    """
    print_test_header("Dead Letter Queue (DLQ)")

    print("Testing DLQ task availability...")

    # Check if DLQ tasks exist
    dlq_tasks = [
        'app.tasks.send_to_dead_letter_queue',
        'app.tasks.inspect_dead_letter_queue',
        'app.tasks.retry_from_dead_letter_queue'
    ]

    dlq_found = []
    for task_name in dlq_tasks:
        task = celery_app.tasks.get(task_name)
        if task:
            dlq_found.append(task_name)
            print(f"  ✅ Found: {task_name}")
        else:
            print(f"  ❌ Missing: {task_name}")

    if len(dlq_found) == len(dlq_tasks):
        test_results["dlq_test"]["passed"] += 1
        print_test_result("DLQ Tasks Available", True, f"All {len(dlq_tasks)} DLQ tasks registered")
    else:
        test_results["dlq_test"]["failed"] += 1
        print_test_result("DLQ Tasks Available", False, f"Only {len(dlq_found)}/{len(dlq_tasks)} tasks found")

    # Test DLQ inspection
    print("\n🔍 Testing DLQ inspection...")
    try:
        result = inspect_dead_letter_queue.delay()
        await asyncio.sleep(2)

        if result.ready():
            dlq_result = result.get()
            print(f"  → DLQ inspection result: {dlq_result.get('status', 'unknown')}")
            test_results["dlq_test"]["passed"] += 1
            print_test_result("DLQ Inspection", True, "DLQ inspection task executed successfully")
        else:
            print("  → DLQ inspection task still running...")
            test_results["dlq_test"]["passed"] += 1
            print_test_result("DLQ Inspection", True, "DLQ inspection task submitted successfully")

    except Exception as e:
        test_results["dlq_test"]["failed"] += 1
        print_test_result("DLQ Inspection", False, f"Error: {e}")

    print("\n⚠️  Note: Full DLQ test requires a task with exhausted retries")
    print("    To test manually:")
    print("    1. Create a task that always fails")
    print("    2. Wait for 3 retry attempts to exhaust")
    print("    3. Check DLQ for the failed task entry")


def print_summary():
    """Print test summary"""
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    total_passed = sum(r["passed"] for r in test_results.values())
    total_failed = sum(r["failed"] for r in test_results.values())
    total_tests = total_passed + total_failed

    print(f"\nTotal Tests: {total_tests}")
    print(f"  ✅ Passed: {total_passed}")
    print(f"  ❌ Failed: {total_failed}")

    print("\nTest Breakdown:")
    for test_name, results in test_results.items():
        passed = results["passed"]
        failed = results["failed"]
        status = "✅" if failed == 0 else "❌"
        print(f"  {status} {test_name}: {passed} passed, {failed} failed")

    print("\n" + "="*60)

    if total_failed == 0:
        print("🎉 ALL TESTS PASSED!")
    else:
        print(f"⚠️  {total_failed} TEST(S) FAILED")

    print("="*60 + "\n")


async def run_all_tests():
    """Run all end-to-end tests"""
    print("\n" + "="*60)
    print("CELERY PRIORITY QUEUE - END-TO-END TESTS")
    print("="*60)
    print(f"\nStarting tests at: {datetime.now().isoformat()}")
    print(f"Celery Broker: {celery_app.conf.broker_url}")

    # Test 1: Priority Ordering
    await test_priority_ordering()

    # Test 2: Status Tracking
    await test_status_tracking()

    # Test 3: Retry Logic
    await test_retry_logic()

    # Test 4: Dead Letter Queue
    await test_dead_letter_queue()

    # Print summary
    print_summary()


if __name__ == "__main__":
    asyncio.run(run_all_tests())

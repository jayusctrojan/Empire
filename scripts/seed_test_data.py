#!/usr/bin/env python3
"""
Empire v7.3 - Test Data Seeding Script - Task 6
Seeds test data for feature flags, users, documents, and other v7.3 features
"""

import os
import sys
import asyncio
from datetime import datetime
from typing import Dict, List
import logging
from supabase import create_client, Client

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TestDataSeeder:
    """Seeds test data for Empire v7.3"""

    def __init__(self):
        """Initialize seeder with Supabase connection"""
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_SERVICE_KEY")

        if not all([self.supabase_url, self.supabase_key]):
            raise ValueError("Missing SUPABASE_URL or SUPABASE_SERVICE_KEY")

        self.client: Client = create_client(self.supabase_url, self.supabase_key)
        logger.info("✅ Supabase client initialized")

    def seed_feature_flags(self) -> Dict[str, any]:
        """Seed feature flag test data (Task 3 - v7.3)"""
        logger.info("🚀 Seeding feature flags...")

        feature_flags = [
            {
                "flag_name": "feature_advanced_search",
                "description": "Enable advanced search with faceted filters and highlighting",
                "enabled": True,
                "user_ids": [],
                "rollout_percentage": 100,
                "metadata": {
                    "category": "search",
                    "priority": "high",
                    "owner": "search-team"
                }
            },
            {
                "flag_name": "feature_course_management",
                "description": "Enable course content organization and module structuring",
                "enabled": True,
                "user_ids": [],
                "rollout_percentage": 100,
                "metadata": {
                    "category": "content",
                    "priority": "high",
                    "owner": "content-team"
                }
            },
            {
                "flag_name": "feature_reporting_dashboard",
                "description": "Enable analytics and reporting dashboard",
                "enabled": False,
                "user_ids": [],
                "rollout_percentage": 0,
                "metadata": {
                    "category": "analytics",
                    "priority": "medium",
                    "owner": "analytics-team"
                }
            },
            {
                "flag_name": "feature_ai_summarization",
                "description": "Enable AI-powered document summarization with Claude",
                "enabled": True,
                "user_ids": [],
                "rollout_percentage": 50,
                "metadata": {
                    "category": "ai",
                    "priority": "high",
                    "owner": "ai-team",
                    "model": "claude-3-5-haiku-20241022"
                }
            },
            {
                "flag_name": "feature_multilingual_support",
                "description": "Enable multi-language document processing and search",
                "enabled": False,
                "user_ids": [],
                "rollout_percentage": 10,
                "metadata": {
                    "category": "i18n",
                    "priority": "low",
                    "owner": "platform-team"
                }
            }
        ]

        results = {"success": 0, "failed": 0, "errors": []}

        for flag in feature_flags:
            try:
                response = self.client.table("feature_flags").upsert(
                    flag,
                    on_conflict="flag_name"
                ).execute()

                logger.info(f"  ✅ Seeded flag: {flag['flag_name']}")
                results["success"] += 1

            except Exception as e:
                logger.error(f"  ❌ Failed to seed {flag['flag_name']}: {e}")
                results["failed"] += 1
                results["errors"].append(str(e))

        logger.info(f"✅ Feature flags seeded: {results['success']} success, {results['failed']} failed")
        return results

    def seed_audit_logs(self) -> Dict[str, any]:
        """Seed audit log test data (Task 41.5 - Security)"""
        logger.info("🚀 Seeding audit logs...")

        audit_events = [
            {
                "user_id": "test_user_admin",
                "event_type": "user_login",
                "event_data": {
                    "ip_address": "192.168.1.100",
                    "user_agent": "Mozilla/5.0 (Test Browser)"
                },
                "severity": "info"
            },
            {
                "user_id": "test_user_admin",
                "event_type": "document_upload",
                "event_data": {
                    "document_id": "doc_test_123",
                    "filename": "test_policy.pdf",
                    "size_bytes": 524288
                },
                "severity": "info"
            },
            {
                "user_id": "test_user_admin",
                "event_type": "config_change",
                "event_data": {
                    "setting": "max_upload_size",
                    "old_value": "10MB",
                    "new_value": "50MB"
                },
                "severity": "warning"
            }
        ]

        results = {"success": 0, "failed": 0, "errors": []}

        for event in audit_events:
            try:
                response = self.client.table("audit_logs").insert(event).execute()
                logger.info(f"  ✅ Seeded audit event: {event['event_type']}")
                results["success"] += 1

            except Exception as e:
                logger.error(f"  ❌ Failed to seed audit log: {e}")
                results["failed"] += 1
                results["errors"].append(str(e))

        logger.info(f"✅ Audit logs seeded: {results['success']} success, {results['failed']} failed")
        return results

    def seed_chat_sessions(self) -> Dict[str, any]:
        """Seed chat session test data (Task 26 - Chat UI)"""
        logger.info("🚀 Seeding chat sessions...")

        sessions = [
            {
                "user_id": "test_user_1",
                "session_name": "Policy Research Session",
                "created_at": datetime.utcnow().isoformat(),
                "last_message_at": datetime.utcnow().isoformat(),
                "metadata": {
                    "department": "insurance",
                    "context": "policy research"
                }
            },
            {
                "user_id": "test_user_2",
                "session_name": "Contract Analysis",
                "created_at": datetime.utcnow().isoformat(),
                "last_message_at": datetime.utcnow().isoformat(),
                "metadata": {
                    "department": "legal",
                    "context": "contract review"
                }
            }
        ]

        results = {"success": 0, "failed": 0, "errors": []}

        for session in sessions:
            try:
                response = self.client.table("chat_sessions").insert(session).execute()
                logger.info(f"  ✅ Seeded session: {session['session_name']}")
                results["success"] += 1

            except Exception as e:
                logger.error(f"  ❌ Failed to seed chat session: {e}")
                results["failed"] += 1
                results["errors"].append(str(e))

        logger.info(f"✅ Chat sessions seeded: {results['success']} success, {results['failed']} failed")
        return results

    def verify_seeded_data(self) -> Dict[str, any]:
        """Verify seeded data exists"""
        logger.info("🔍 Verifying seeded data...")

        verification_results = {}

        # Verify feature flags
        try:
            flags = self.client.table("feature_flags").select("*").execute()
            verification_results["feature_flags"] = len(flags.data)
            logger.info(f"  ✅ Found {len(flags.data)} feature flags")
        except Exception as e:
            logger.error(f"  ❌ Failed to verify feature flags: {e}")
            verification_results["feature_flags"] = 0

        # Verify audit logs
        try:
            logs = self.client.table("audit_logs").select("*").limit(10).execute()
            verification_results["audit_logs"] = len(logs.data)
            logger.info(f"  ✅ Found {len(logs.data)} audit logs (showing first 10)")
        except Exception as e:
            logger.error(f"  ❌ Failed to verify audit logs: {e}")
            verification_results["audit_logs"] = 0

        # Verify chat sessions
        try:
            sessions = self.client.table("chat_sessions").select("*").limit(10).execute()
            verification_results["chat_sessions"] = len(sessions.data)
            logger.info(f"  ✅ Found {len(sessions.data)} chat sessions (showing first 10)")
        except Exception as e:
            logger.error(f"  ❌ Failed to verify chat sessions: {e}")
            verification_results["chat_sessions"] = 0

        return verification_results

    def seed_all(self, dry_run: bool = False) -> Dict[str, any]:
        """Seed all test data"""
        logger.info("=" * 60)
        logger.info("EMPIRE V7.3 - TEST DATA SEEDING")
        logger.info("=" * 60)

        if dry_run:
            logger.info("🔍 DRY RUN MODE - No data will be inserted")
            return {"dry_run": True}

        all_results = {}

        try:
            # Seed feature flags
            all_results["feature_flags"] = self.seed_feature_flags()

            # Seed audit logs
            all_results["audit_logs"] = self.seed_audit_logs()

            # Seed chat sessions
            all_results["chat_sessions"] = self.seed_chat_sessions()

            # Verify data
            all_results["verification"] = self.verify_seeded_data()

            # Summary
            logger.info("=" * 60)
            logger.info("SEEDING SUMMARY")
            logger.info("=" * 60)
            total_success = sum(r.get("success", 0) for r in all_results.values() if isinstance(r, dict))
            total_failed = sum(r.get("failed", 0) for r in all_results.values() if isinstance(r, dict))
            logger.info(f"✅ Total successful insertions: {total_success}")
            logger.info(f"❌ Total failed insertions: {total_failed}")
            logger.info("=" * 60)

            return all_results

        except Exception as e:
            logger.error(f"❌ Fatal error during seeding: {e}")
            raise


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Seed test data for Empire v7.3"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be seeded without inserting data"
    )

    args = parser.parse_args()

    try:
        seeder = TestDataSeeder()
        results = seeder.seed_all(dry_run=args.dry_run)

        # Exit with error code if any seeding failed
        total_failed = sum(
            r.get("failed", 0)
            for r in results.values()
            if isinstance(r, dict) and "failed" in r
        )

        if total_failed > 0:
            logger.error(f"❌ {total_failed} insertions failed")
            sys.exit(1)
        else:
            logger.info("✅ All test data seeded successfully")
            sys.exit(0)

    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

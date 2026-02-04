#!/usr/bin/env python3
"""
Empire v7.3 - Database Migration Runner - Task 6
Automatically runs SQL migrations in order from the migrations/ directory
"""

import os
import sys
import psycopg2
from pathlib import Path
from datetime import datetime
from typing import List, Dict
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MigrationRunner:
    """Manages database migrations for Empire v7.3"""

    def __init__(self):
        """Initialize migration runner with database connection"""
        self.db_host = os.getenv("SUPABASE_DB_HOST")
        self.db_name = os.getenv("SUPABASE_DB_NAME")
        self.db_user = os.getenv("SUPABASE_DB_USER")
        self.db_password = os.getenv("SUPABASE_DB_PASSWORD")
        self.db_port = os.getenv("SUPABASE_DB_PORT", "5432")

        # Validate environment variables
        if not all([self.db_host, self.db_name, self.db_user, self.db_password]):
            raise ValueError("Missing required database environment variables")

        self.connection_string = (
            f"host={self.db_host} "
            f"dbname={self.db_name} "
            f"user={self.db_user} "
            f"password={self.db_password} "
            f"port={self.db_port}"
        )

        # Path to migrations directory
        self.migrations_dir = Path(__file__).parent.parent / "migrations"
        logger.info(f"Migrations directory: {self.migrations_dir}")

    def get_db_connection(self):
        """Create database connection"""
        try:
            conn = psycopg2.connect(self.connection_string)
            logger.info("✅ Database connection established")
            return conn
        except psycopg2.Error as e:
            logger.error(f"❌ Failed to connect to database: {e}")
            raise

    def create_migrations_table(self, conn):
        """Create migrations tracking table if it doesn't exist"""
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        id SERIAL PRIMARY KEY,
                        migration_name VARCHAR(255) NOT NULL UNIQUE,
                        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        success BOOLEAN DEFAULT TRUE,
                        error_message TEXT
                    );
                """)
                conn.commit()
                logger.info("✅ Migrations tracking table ready")
        except psycopg2.Error as e:
            logger.error(f"❌ Failed to create migrations table: {e}")
            conn.rollback()
            raise

    def get_applied_migrations(self, conn) -> List[str]:
        """Get list of already applied migrations"""
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT migration_name
                    FROM schema_migrations
                    WHERE success = TRUE
                    ORDER BY applied_at
                """)
                applied = [row[0] for row in cursor.fetchall()]
                logger.info(f"Found {len(applied)} previously applied migrations")
                return applied
        except psycopg2.Error as e:
            logger.error(f"❌ Failed to get applied migrations: {e}")
            return []

    def get_pending_migrations(self, applied_migrations: List[str]) -> List[Path]:
        """Get list of migration files not yet applied"""
        if not self.migrations_dir.exists():
            logger.warning(f"⚠️  Migrations directory not found: {self.migrations_dir}")
            return []

        # Find all .sql files
        all_migrations = sorted(self.migrations_dir.glob("*.sql"))

        # Filter out already applied
        pending = [
            m for m in all_migrations
            if m.name not in applied_migrations
        ]

        logger.info(f"Found {len(pending)} pending migrations")
        return pending

    def apply_migration(self, conn, migration_file: Path) -> bool:
        """Apply a single migration file"""
        migration_name = migration_file.name
        logger.info(f"📄 Applying migration: {migration_name}")

        try:
            # Read migration SQL
            with open(migration_file, 'r') as f:
                sql = f.read()

            # Execute migration
            with conn.cursor() as cursor:
                cursor.execute(sql)
                conn.commit()

            # Record success (use upsert to handle previously failed migrations)
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO schema_migrations (migration_name, success, applied_at, error_message)
                    VALUES (%s, TRUE, CURRENT_TIMESTAMP, NULL)
                    ON CONFLICT (migration_name) DO UPDATE SET
                        success = TRUE,
                        applied_at = CURRENT_TIMESTAMP,
                        error_message = NULL
                """, (migration_name,))
                conn.commit()

            logger.info(f"✅ Successfully applied: {migration_name}")
            return True

        except psycopg2.Error as e:
            error_msg = str(e)

            # Check if this is an "already exists" error - treat as success (idempotency)
            already_exists_patterns = [
                'already exists',
                'duplicate key value violates unique constraint',
            ]

            is_already_exists = any(pattern in error_msg.lower() for pattern in already_exists_patterns)

            if is_already_exists:
                logger.warning(f"⚠️  Object already exists in {migration_name}, treating as success")
                try:
                    conn.rollback()
                    with conn.cursor() as cursor:
                        cursor.execute("""
                            INSERT INTO schema_migrations (migration_name, success, applied_at, error_message)
                            VALUES (%s, TRUE, CURRENT_TIMESTAMP, %s)
                            ON CONFLICT (migration_name) DO UPDATE SET
                                success = TRUE,
                                applied_at = CURRENT_TIMESTAMP,
                                error_message = %s
                        """, (migration_name, f"Already exists: {error_msg}", f"Already exists: {error_msg}"))
                        conn.commit()
                except Exception as record_error:
                    logger.error(f"❌ Failed to record migration: {record_error}")
                return True

            logger.error(f"❌ Failed to apply {migration_name}: {error_msg}")

            # Record failure (use upsert to handle re-runs)
            try:
                conn.rollback()
                with conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO schema_migrations (migration_name, success, error_message)
                        VALUES (%s, FALSE, %s)
                        ON CONFLICT (migration_name) DO UPDATE SET
                            success = FALSE,
                            error_message = %s,
                            applied_at = CURRENT_TIMESTAMP
                    """, (migration_name, error_msg, error_msg))
                    conn.commit()
            except Exception as record_error:
                logger.error(f"❌ Failed to record migration failure: {record_error}")

            return False

    def run_migrations(self, dry_run: bool = False) -> Dict[str, any]:
        """Run all pending migrations"""
        results = {
            "total": 0,
            "applied": 0,
            "failed": 0,
            "skipped": 0,
            "migrations": []
        }

        try:
            # Connect to database
            conn = self.get_db_connection()

            # Create migrations table
            self.create_migrations_table(conn)

            # Get applied and pending migrations
            applied_migrations = self.get_applied_migrations(conn)
            pending_migrations = self.get_pending_migrations(applied_migrations)

            results["total"] = len(pending_migrations)

            if not pending_migrations:
                logger.info("✅ No pending migrations to apply")
                return results

            logger.info(f"🚀 Running {len(pending_migrations)} pending migrations...")

            if dry_run:
                logger.info("🔍 DRY RUN MODE - No changes will be made")
                for migration in pending_migrations:
                    logger.info(f"  - Would apply: {migration.name}")
                results["skipped"] = len(pending_migrations)
                return results

            # Apply each migration
            for migration_file in pending_migrations:
                success = self.apply_migration(conn, migration_file)

                results["migrations"].append({
                    "name": migration_file.name,
                    "success": success
                })

                if success:
                    results["applied"] += 1
                else:
                    results["failed"] += 1

            # Close connection
            conn.close()

            # Summary
            logger.info("=" * 60)
            logger.info("MIGRATION SUMMARY")
            logger.info("=" * 60)
            logger.info(f"Total migrations: {results['total']}")
            logger.info(f"✅ Successfully applied: {results['applied']}")
            logger.info(f"❌ Failed: {results['failed']}")
            logger.info("=" * 60)

            return results

        except Exception as e:
            logger.error(f"❌ Migration process failed: {e}")
            results["failed"] = results["total"]
            raise


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Run database migrations for Empire v7.3"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without applying changes"
    )

    args = parser.parse_args()

    try:
        runner = MigrationRunner()
        results = runner.run_migrations(dry_run=args.dry_run)

        # Exit with error code if any migrations failed
        if results["failed"] > 0:
            logger.error(f"❌ {results['failed']} migrations failed")
            sys.exit(1)
        else:
            logger.info("✅ All migrations completed successfully")
            sys.exit(0)

    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

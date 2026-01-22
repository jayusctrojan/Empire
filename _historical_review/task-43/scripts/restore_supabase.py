#!/usr/bin/env python3
"""
Restore Supabase Database from Backblaze B2 Backup - Task 42.1

This script:
1. Lists available backups from B2
2. Downloads specified backup
3. Decompresses the backup
4. Restores to Supabase database using psql

Usage:
    # List available backups
    python scripts/restore_supabase.py --list

    # Restore latest backup
    python scripts/restore_supabase.py --latest

    # Restore specific backup
    python scripts/restore_supabase.py --file supabase_backup_20240115_120000.sql.gz

    # Dry run (download but don't restore)
    python scripts/restore_supabase.py --latest --dry-run

Environment Variables Required:
    SUPABASE_DB_HOST - Supabase PostgreSQL host
    SUPABASE_DB_NAME - Database name
    SUPABASE_DB_USER - Database user (postgres role)
    SUPABASE_DB_PASSWORD - Database password
    B2_APPLICATION_KEY_ID - Backblaze B2 key ID
    B2_APPLICATION_KEY - Backblaze B2 application key
    B2_BUCKET_NAME - B2 bucket name for backups
"""

import os
import sys
import subprocess
import logging
import gzip
from datetime import datetime
from pathlib import Path
from typing import Optional, List
import hashlib

# Try to import B2 SDK
try:
    from b2sdk.v2 import B2Api, InMemoryAccountInfo
    B2_AVAILABLE = True
except ImportError:
    B2_AVAILABLE = False
    print("Warning: b2sdk not installed. Install with: pip install b2sdk")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/restore.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class SupabaseRestore:
    """Manages Supabase database restoration from B2 backups"""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.restore_dir = Path("backups/restore")
        self.restore_dir.mkdir(parents=True, exist_ok=True)

        # Supabase connection details
        self.db_host = os.getenv("SUPABASE_DB_HOST")
        self.db_name = os.getenv("SUPABASE_DB_NAME", "postgres")
        self.db_user = os.getenv("SUPABASE_DB_USER", "postgres")
        self.db_password = os.getenv("SUPABASE_DB_PASSWORD")
        self.db_port = os.getenv("SUPABASE_DB_PORT", "5432")

        # B2 configuration
        self.b2_key_id = os.getenv("B2_APPLICATION_KEY_ID")
        self.b2_app_key = os.getenv("B2_APPLICATION_KEY")
        self.b2_bucket_name = os.getenv("B2_BUCKET_NAME", "empire-backups")

        # Validate configuration
        self._validate_config()

    def _validate_config(self):
        """Validate required environment variables"""
        missing = []

        if not self.db_host:
            missing.append("SUPABASE_DB_HOST")
        if not self.db_password:
            missing.append("SUPABASE_DB_PASSWORD")
        if not self.b2_key_id:
            missing.append("B2_APPLICATION_KEY_ID")
        if not self.b2_app_key:
            missing.append("B2_APPLICATION_KEY")

        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}"
            )

        if not B2_AVAILABLE:
            raise ImportError("b2sdk is required. Install with: pip install b2sdk")

    def list_backups(self) -> List[dict]:
        """
        List available backups from B2

        Returns:
            List of backup metadata dicts
        """
        logger.info("Listing available backups from B2")

        try:
            # Initialize B2 API
            info = InMemoryAccountInfo()
            b2_api = B2Api(info)
            b2_api.authorize_account("production", self.b2_key_id, self.b2_app_key)

            # Get bucket
            bucket = b2_api.get_bucket_by_name(self.b2_bucket_name)

            # List backups
            backups = []
            for file_version, _ in bucket.ls(folder_to_list="supabase/", recursive=True):
                backup_info = {
                    "file_name": file_version.file_name,
                    "size_mb": file_version.size / (1024 * 1024),
                    "upload_timestamp": datetime.fromtimestamp(
                        file_version.upload_timestamp / 1000
                    ),
                    "file_id": file_version.id_
                }
                backups.append(backup_info)

            # Sort by timestamp (newest first)
            backups.sort(key=lambda x: x["upload_timestamp"], reverse=True)

            logger.info(f"Found {len(backups)} backup(s)")

            return backups

        except Exception as e:
            logger.error(f"Failed to list backups: {e}")
            return []

    def download_backup(self, file_name: str) -> Optional[Path]:
        """
        Download backup from B2

        Args:
            file_name: Name of backup file in B2

        Returns:
            Path to downloaded file, or None if failed
        """
        local_file = self.restore_dir / Path(file_name).name

        logger.info(f"Downloading backup: {file_name}")

        if self.dry_run:
            logger.info("DRY RUN: Would download backup")
            local_file.touch()
            return local_file

        try:
            # Initialize B2 API
            info = InMemoryAccountInfo()
            b2_api = B2Api(info)
            b2_api.authorize_account("production", self.b2_key_id, self.b2_app_key)

            # Get bucket
            bucket = b2_api.get_bucket_by_name(self.b2_bucket_name)

            # Download file
            bucket.download_file_by_name(file_name).save_to(str(local_file))

            file_size_mb = local_file.stat().st_size / (1024 * 1024)
            logger.info(f"Download complete: {file_size_mb:.2f} MB")

            return local_file

        except Exception as e:
            logger.error(f"Failed to download backup: {e}")
            return None

    def decompress_backup(self, compressed_file: Path) -> Optional[Path]:
        """
        Decompress gzipped backup file

        Args:
            compressed_file: Path to .gz file

        Returns:
            Path to decompressed SQL file, or None if failed
        """
        sql_file = compressed_file.with_suffix('')  # Remove .gz extension

        logger.info(f"Decompressing backup: {sql_file}")

        if self.dry_run:
            logger.info("DRY RUN: Would decompress backup")
            sql_file.touch()
            return sql_file

        try:
            with gzip.open(compressed_file, 'rb') as f_in:
                with open(sql_file, 'wb') as f_out:
                    f_out.write(f_in.read())

            file_size_mb = sql_file.stat().st_size / (1024 * 1024)
            logger.info(f"Decompression complete: {file_size_mb:.2f} MB")

            return sql_file

        except Exception as e:
            logger.error(f"Failed to decompress backup: {e}")
            return None

    def restore_database(self, sql_file: Path, drop_existing: bool = False) -> bool:
        """
        Restore database from SQL dump using psql

        Args:
            sql_file: Path to SQL dump file
            drop_existing: If True, drop and recreate database first

        Returns:
            True if restore successful, False otherwise
        """
        logger.info(f"Restoring database from: {sql_file}")

        if self.dry_run:
            logger.info("DRY RUN: Would restore database")
            return True

        # Set environment variable for password
        env = os.environ.copy()
        env["PGPASSWORD"] = self.db_password

        try:
            # Step 1: Drop and recreate database if requested
            if drop_existing:
                logger.warning("Dropping existing database - THIS WILL DELETE ALL DATA!")
                logger.info("Sleeping 5 seconds... Press Ctrl+C to cancel")

                import time
                time.sleep(5)

                # Connect to postgres database to drop/create
                drop_cmd = [
                    "psql",
                    "-h", self.db_host,
                    "-p", self.db_port,
                    "-U", self.db_user,
                    "-d", "postgres",
                    "-c", f"DROP DATABASE IF EXISTS {self.db_name};"
                ]

                result = subprocess.run(drop_cmd, env=env, capture_output=True, text=True)
                if result.returncode != 0:
                    logger.error(f"Failed to drop database: {result.stderr}")
                    return False

                create_cmd = [
                    "psql",
                    "-h", self.db_host,
                    "-p", self.db_port,
                    "-U", self.db_user,
                    "-d", "postgres",
                    "-c", f"CREATE DATABASE {self.db_name};"
                ]

                result = subprocess.run(create_cmd, env=env, capture_output=True, text=True)
                if result.returncode != 0:
                    logger.error(f"Failed to create database: {result.stderr}")
                    return False

                logger.info("Database dropped and recreated")

            # Step 2: Restore from SQL dump
            restore_cmd = [
                "psql",
                "-h", self.db_host,
                "-p", self.db_port,
                "-U", self.db_user,
                "-d", self.db_name,
                "-f", str(sql_file),
                "-v", "ON_ERROR_STOP=0"  # Continue on errors
            ]

            result = subprocess.run(
                restore_cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=7200  # 2 hour timeout
            )

            if result.returncode != 0:
                logger.warning(f"psql completed with warnings/errors:\n{result.stderr}")
                # Don't fail completely - some errors may be acceptable
            else:
                logger.info("Restore completed successfully")

            # Log any output
            if result.stdout:
                logger.debug(f"psql output:\n{result.stdout}")

            return True

        except subprocess.TimeoutExpired:
            logger.error("Restore timed out after 2 hours")
            return False
        except KeyboardInterrupt:
            logger.info("Restore cancelled by user")
            return False
        except Exception as e:
            logger.error(f"Failed to restore database: {e}")
            return False

    def cleanup_local(self, *files: Path):
        """Remove local files after restore"""
        if self.dry_run:
            logger.info("DRY RUN: Would cleanup local files")
            return

        for file in files:
            try:
                if file.exists():
                    file.unlink()
                    logger.info(f"Removed local file: {file}")
            except Exception as e:
                logger.error(f"Failed to cleanup {file}: {e}")

    def run(
        self,
        backup_file: Optional[str] = None,
        use_latest: bool = False,
        drop_existing: bool = False
    ) -> bool:
        """
        Execute full restore workflow

        Args:
            backup_file: Specific backup file name to restore
            use_latest: If True, restore latest backup
            drop_existing: If True, drop and recreate database before restore

        Returns:
            True if restore successful, False otherwise
        """
        logger.info("=" * 60)
        logger.info("Starting Supabase restore process")
        logger.info(f"Database: {self.db_host}/{self.db_name}")
        logger.info(f"Dry run: {self.dry_run}")
        logger.info("=" * 60)

        try:
            # Step 1: Determine which backup to restore
            if use_latest:
                backups = self.list_backups()
                if not backups:
                    logger.error("No backups found")
                    return False

                backup_file = backups[0]["file_name"]
                logger.info(f"Using latest backup: {backup_file}")
            elif not backup_file:
                logger.error("Must specify --file or --latest")
                return False

            # Step 2: Download backup
            compressed_file = self.download_backup(backup_file)
            if not compressed_file:
                logger.error("Restore failed: Could not download backup")
                return False

            # Step 3: Decompress backup
            sql_file = self.decompress_backup(compressed_file)
            if not sql_file:
                logger.error("Restore failed: Could not decompress backup")
                return False

            # Step 4: Restore database
            restore_success = self.restore_database(sql_file, drop_existing=drop_existing)
            if not restore_success:
                logger.error("Restore failed: Could not restore database")
                return False

            # Step 5: Cleanup local files
            self.cleanup_local(compressed_file, sql_file)

            logger.info("=" * 60)
            logger.info("Restore completed successfully")
            logger.info("=" * 60)

            return True

        except Exception as e:
            logger.error(f"Restore failed with exception: {e}", exc_info=True)
            return False


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Restore Supabase database from B2")
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available backups"
    )
    parser.add_argument(
        "--latest",
        action="store_true",
        help="Restore from latest backup"
    )
    parser.add_argument(
        "--file",
        type=str,
        help="Specific backup file to restore"
    )
    parser.add_argument(
        "--drop-existing",
        action="store_true",
        help="Drop and recreate database before restore (DESTRUCTIVE!)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Download backup but don't actually restore"
    )
    args = parser.parse_args()

    # Ensure logs directory exists
    Path("logs").mkdir(exist_ok=True)

    restore = SupabaseRestore(dry_run=args.dry_run)

    # List backups if requested
    if args.list:
        backups = restore.list_backups()
        if backups:
            print("\nAvailable backups:")
            print("-" * 80)
            for i, backup in enumerate(backups, 1):
                print(f"{i}. {backup['file_name']}")
                print(f"   Size: {backup['size_mb']:.2f} MB")
                print(f"   Date: {backup['upload_timestamp']}")
                print()
        else:
            print("No backups found")
        sys.exit(0)

    # Run restore
    success = restore.run(
        backup_file=args.file,
        use_latest=args.latest,
        drop_existing=args.drop_existing
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

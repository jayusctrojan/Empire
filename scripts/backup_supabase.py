#!/usr/bin/env python3
"""
Automated Supabase Database Backup to Backblaze B2 - Task 42.1

This script:
1. Creates a PostgreSQL dump of the Supabase database
2. Compresses the dump with gzip
3. Uploads to Backblaze B2 with retention management
4. Logs backup success/failure for monitoring

Usage:
    python scripts/backup_supabase.py [--dry-run]

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
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
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
        logging.FileHandler('logs/backup.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class SupabaseBackup:
    """Manages Supabase database backups to B2"""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.backup_dir = Path("backups/temp")
        self.backup_dir.mkdir(parents=True, exist_ok=True)

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

        # Retention policy (days)
        self.retention_days = int(os.getenv("BACKUP_RETENTION_DAYS", "30"))

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

    def create_dump(self) -> Optional[Path]:
        """
        Create PostgreSQL dump using pg_dump

        Returns:
            Path to the dump file, or None if failed
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        dump_file = self.backup_dir / f"supabase_backup_{timestamp}.sql"

        logger.info(f"Creating database dump: {dump_file}")

        if self.dry_run:
            logger.info("DRY RUN: Would create dump")
            # Create empty file for testing
            dump_file.touch()
            return dump_file

        # Set environment variable for password
        env = os.environ.copy()
        env["PGPASSWORD"] = self.db_password

        # Build pg_dump command
        cmd = [
            "pg_dump",
            "-h", self.db_host,
            "-p", self.db_port,
            "-U", self.db_user,
            "-d", self.db_name,
            "-F", "p",  # Plain SQL format
            "--no-owner",  # Skip ownership commands
            "--no-privileges",  # Skip privilege commands
            "-f", str(dump_file)
        ]

        try:
            # Execute pg_dump
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=3600  # 1 hour timeout
            )

            if result.returncode != 0:
                logger.error(f"pg_dump failed: {result.stderr}")
                return None

            # Verify dump file exists and has content
            if not dump_file.exists() or dump_file.stat().st_size == 0:
                logger.error("Dump file is empty or missing")
                return None

            file_size_mb = dump_file.stat().st_size / (1024 * 1024)
            logger.info(f"Dump created successfully: {file_size_mb:.2f} MB")

            return dump_file

        except subprocess.TimeoutExpired:
            logger.error("pg_dump timed out after 1 hour")
            return None
        except Exception as e:
            logger.error(f"Failed to create dump: {e}")
            return None

    def compress_dump(self, dump_file: Path) -> Optional[Path]:
        """
        Compress dump file with gzip

        Args:
            dump_file: Path to SQL dump file

        Returns:
            Path to compressed file, or None if failed
        """
        compressed_file = dump_file.with_suffix('.sql.gz')

        logger.info(f"Compressing dump: {compressed_file}")

        if self.dry_run:
            logger.info("DRY RUN: Would compress dump")
            compressed_file.touch()
            return compressed_file

        try:
            with open(dump_file, 'rb') as f_in:
                with gzip.open(compressed_file, 'wb', compresslevel=9) as f_out:
                    shutil.copyfileobj(f_in, f_out)

            # Calculate compression ratio
            original_size = dump_file.stat().st_size
            compressed_size = compressed_file.stat().st_size
            ratio = (1 - compressed_size / original_size) * 100

            logger.info(
                f"Compression complete: {compressed_size / (1024 * 1024):.2f} MB "
                f"({ratio:.1f}% reduction)"
            )

            # Calculate MD5 checksum for integrity verification
            md5_hash = self._calculate_md5(compressed_file)
            logger.info(f"Backup MD5 checksum: {md5_hash}")

            # Remove uncompressed dump
            dump_file.unlink()
            logger.info("Removed uncompressed dump")

            return compressed_file

        except Exception as e:
            logger.error(f"Failed to compress dump: {e}")
            return None

    def _calculate_md5(self, file_path: Path) -> str:
        """Calculate MD5 checksum of file"""
        md5 = hashlib.md5()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b""):
                md5.update(chunk)
        return md5.hexdigest()

    def upload_to_b2(self, backup_file: Path) -> bool:
        """
        Upload backup to Backblaze B2

        Args:
            backup_file: Path to compressed backup file

        Returns:
            True if upload successful, False otherwise
        """
        logger.info(f"Uploading to B2: {backup_file.name}")

        if self.dry_run:
            logger.info("DRY RUN: Would upload to B2")
            return True

        try:
            # Initialize B2 API
            info = InMemoryAccountInfo()
            b2_api = B2Api(info)
            b2_api.authorize_account("production", self.b2_key_id, self.b2_app_key)

            # Get or create bucket
            bucket = b2_api.get_bucket_by_name(self.b2_bucket_name)

            # Upload file
            b2_file_name = f"supabase/{backup_file.name}"

            bucket.upload_local_file(
                local_file=str(backup_file),
                file_name=b2_file_name,
                file_info={
                    "backup_date": datetime.utcnow().isoformat(),
                    "database": self.db_name,
                    "md5": self._calculate_md5(backup_file)
                }
            )

            logger.info(f"Upload successful: {b2_file_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to upload to B2: {e}")
            return False

    def cleanup_old_backups(self):
        """Remove backups older than retention period from B2"""
        logger.info(f"Cleaning up backups older than {self.retention_days} days")

        if self.dry_run:
            logger.info("DRY RUN: Would cleanup old backups")
            return

        try:
            # Initialize B2 API
            info = InMemoryAccountInfo()
            b2_api = B2Api(info)
            b2_api.authorize_account("production", self.b2_key_id, self.b2_app_key)

            # Get bucket
            bucket = b2_api.get_bucket_by_name(self.b2_bucket_name)

            # Calculate cutoff date
            cutoff_date = datetime.utcnow() - timedelta(days=self.retention_days)
            cutoff_timestamp = int(cutoff_date.timestamp() * 1000)  # B2 uses milliseconds

            # List and delete old backups
            deleted_count = 0
            for file_version, _ in bucket.ls(folder_to_list="supabase/", recursive=True):
                if file_version.upload_timestamp < cutoff_timestamp:
                    logger.info(f"Deleting old backup: {file_version.file_name}")
                    b2_api.delete_file_version(file_version.id_, file_version.file_name)
                    deleted_count += 1

            logger.info(f"Deleted {deleted_count} old backup(s)")

        except Exception as e:
            logger.error(f"Failed to cleanup old backups: {e}")

    def cleanup_local(self, backup_file: Path):
        """Remove local backup file after upload"""
        if self.dry_run:
            logger.info("DRY RUN: Would cleanup local file")
            return

        try:
            backup_file.unlink()
            logger.info(f"Removed local backup: {backup_file}")
        except Exception as e:
            logger.error(f"Failed to cleanup local file: {e}")

    def run(self) -> bool:
        """
        Execute full backup workflow

        Returns:
            True if backup successful, False otherwise
        """
        logger.info("=" * 60)
        logger.info("Starting Supabase backup process")
        logger.info(f"Database: {self.db_host}/{self.db_name}")
        logger.info(f"Dry run: {self.dry_run}")
        logger.info("=" * 60)

        try:
            # Step 1: Create database dump
            dump_file = self.create_dump()
            if not dump_file:
                logger.error("Backup failed: Could not create dump")
                return False

            # Step 2: Compress dump
            compressed_file = self.compress_dump(dump_file)
            if not compressed_file:
                logger.error("Backup failed: Could not compress dump")
                return False

            # Step 3: Upload to B2
            upload_success = self.upload_to_b2(compressed_file)
            if not upload_success:
                logger.error("Backup failed: Could not upload to B2")
                return False

            # Step 4: Cleanup old backups
            self.cleanup_old_backups()

            # Step 5: Cleanup local files
            self.cleanup_local(compressed_file)

            logger.info("=" * 60)
            logger.info("Backup completed successfully")
            logger.info("=" * 60)

            return True

        except Exception as e:
            logger.error(f"Backup failed with exception: {e}", exc_info=True)
            return False


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Backup Supabase database to B2")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate backup without actually creating or uploading"
    )
    args = parser.parse_args()

    # Ensure logs directory exists
    Path("logs").mkdir(exist_ok=True)

    # Run backup
    backup = SupabaseBackup(dry_run=args.dry_run)
    success = backup.run()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

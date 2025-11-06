"""
Empire v7.3 - Mountain Duck File Poller
Monitors local folder synced by Mountain Duck and auto-uploads new files to B2
"""

import os
import asyncio
import logging
from pathlib import Path
from typing import Set, Optional
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import hashlib

from app.services.b2_storage import get_b2_service

# Optional Celery task import
try:
    from app.tasks.document_processing import process_document
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False

logger = logging.getLogger(__name__)


class MountainDuckHandler(FileSystemEventHandler):
    """
    File system event handler for Mountain Duck folder monitoring
    """

    def __init__(self, upload_callback):
        super().__init__()
        self.upload_callback = upload_callback
        self.processing_files: Set[str] = set()

    def on_created(self, event):
        """Handle new file creation"""
        if event.is_directory:
            return

        file_path = event.src_path

        # Ignore hidden files and system files
        if Path(file_path).name.startswith('.'):
            return

        # Avoid duplicate processing
        if file_path in self.processing_files:
            return

        logger.info(f"New file detected: {file_path}")
        self.processing_files.add(file_path)

        # Schedule upload
        asyncio.create_task(self.upload_callback(file_path))

    def on_modified(self, event):
        """Handle file modifications (optional - could trigger re-upload)"""
        # For now, we only handle new files, not modifications
        pass


class MountainDuckPoller:
    """
    Polls a local directory synced by Mountain Duck for new files
    and automatically uploads them to B2 for processing
    """

    def __init__(
        self,
        watch_directory: str,
        poll_interval: int = 30,
        destination_folder: str = "pending/courses"
    ):
        """
        Initialize the Mountain Duck poller

        Args:
            watch_directory: Local directory path to monitor
            poll_interval: Polling interval in seconds (default: 30)
            destination_folder: B2 destination folder (default: pending/courses)
        """
        self.watch_directory = Path(watch_directory)
        self.poll_interval = poll_interval
        self.destination_folder = destination_folder
        self.observer = None
        self.processed_files: Set[str] = set()  # Track already processed files
        self.running = False

        # Validate watch directory
        if not self.watch_directory.exists():
            logger.warning(f"Watch directory does not exist: {watch_directory}")
            self.watch_directory.mkdir(parents=True, exist_ok=True)

        logger.info(f"Mountain Duck poller initialized for: {watch_directory}")

    def get_file_hash(self, file_path: Path) -> str:
        """
        Calculate file hash to track changes

        Args:
            file_path: Path to file

        Returns:
            str: MD5 hash of file
        """
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    async def upload_file_to_b2(self, file_path: str):
        """
        Upload a file to B2 storage

        Args:
            file_path: Path to the file to upload
        """
        try:
            file_path_obj = Path(file_path)

            # Wait a bit to ensure file is fully written
            await asyncio.sleep(2)

            # Check if file still exists and is readable
            if not file_path_obj.exists():
                logger.warning(f"File no longer exists: {file_path}")
                return

            # Get file info
            file_size = file_path_obj.stat().st_size
            file_name = file_path_obj.name

            # Skip very small files (likely incomplete)
            if file_size < 100:
                logger.warning(f"Skipping very small file: {file_name} ({file_size} bytes)")
                return

            # Calculate file hash
            file_hash = self.get_file_hash(file_path_obj)

            # Check if already processed
            file_key = f"{file_name}:{file_hash}"
            if file_key in self.processed_files:
                logger.info(f"File already processed: {file_name}")
                return

            logger.info(f"Uploading {file_name} to B2 ({file_size / (1024*1024):.2f} MB)")

            # Upload to B2
            b2_service = get_b2_service()

            with open(file_path_obj, 'rb') as file_data:
                result = await b2_service.upload_file(
                    file_data=file_data,
                    filename=file_name,
                    folder=self.destination_folder,
                    metadata={
                        "original_path": str(file_path),
                        "uploaded_at": datetime.utcnow().isoformat(),
                        "source": "mountain_duck",
                        "file_hash": file_hash
                    }
                )

            # Mark as processed
            self.processed_files.add(file_key)

            logger.info(f"Successfully uploaded {file_name} (ID: {result['file_id']})")

            # Queue for processing if Celery is available
            if CELERY_AVAILABLE:
                process_document.delay(
                    file_id=result["file_id"],
                    filename=file_name,
                    b2_path=result["file_name"]
                )
                logger.info(f"Queued {file_name} for processing")
            else:
                logger.warning(f"Celery not available - {file_name} will not be auto-processed")

        except Exception as e:
            logger.error(f"Failed to upload {file_path}: {e}")

    def start_watching(self):
        """
        Start watching the directory for new files using watchdog
        """
        if self.running:
            logger.warning("Poller is already running")
            return

        handler = MountainDuckHandler(upload_callback=self.upload_file_to_b2)
        self.observer = Observer()
        self.observer.schedule(handler, str(self.watch_directory), recursive=False)
        self.observer.start()
        self.running = True

        logger.info(f"Started watching directory: {self.watch_directory}")

    def stop_watching(self):
        """
        Stop watching the directory
        """
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.running = False
            logger.info("Stopped watching directory")

    async def poll_directory(self):
        """
        Legacy polling method (fallback if watchdog is not available)
        Scans directory every poll_interval seconds
        """
        logger.info(f"Starting directory polling every {self.poll_interval} seconds")

        while self.running:
            try:
                # Scan directory for new files
                for file_path in self.watch_directory.iterdir():
                    if file_path.is_file() and not file_path.name.startswith('.'):
                        # Check if already processed
                        file_hash = self.get_file_hash(file_path)
                        file_key = f"{file_path.name}:{file_hash}"

                        if file_key not in self.processed_files:
                            await self.upload_file_to_b2(str(file_path))

            except Exception as e:
                logger.error(f"Error during polling: {e}")

            # Wait for next poll
            await asyncio.sleep(self.poll_interval)

    def start_polling(self):
        """
        Start polling the directory (legacy method)
        """
        if self.running:
            logger.warning("Poller is already running")
            return

        self.running = True
        asyncio.create_task(self.poll_directory())


# Global poller instance
_poller = None


def get_poller(
    watch_directory: Optional[str] = None,
    poll_interval: int = 30
) -> MountainDuckPoller:
    """
    Get or create Mountain Duck poller singleton

    Args:
        watch_directory: Directory to watch (default: from env MOUNTAIN_DUCK_WATCH_DIR)
        poll_interval: Polling interval in seconds

    Returns:
        MountainDuckPoller instance
    """
    global _poller

    if _poller is None:
        watch_dir = watch_directory or os.getenv(
            "MOUNTAIN_DUCK_WATCH_DIR",
            str(Path.home() / "Mountain Duck" / "Empire" / "pending")
        )

        _poller = MountainDuckPoller(
            watch_directory=watch_dir,
            poll_interval=poll_interval
        )

    return _poller


def start_mountain_duck_monitoring():
    """
    Start Mountain Duck file monitoring
    Should be called during application startup
    """
    poller = get_poller()

    # Try to use watchdog for real-time monitoring
    # Falls back to polling if watchdog is not available
    try:
        poller.start_watching()
        logger.info("Mountain Duck monitoring started (watchdog mode)")
    except Exception as e:
        logger.warning(f"Watchdog not available, using polling mode: {e}")
        poller.start_polling()
        logger.info("Mountain Duck monitoring started (polling mode)")


def stop_mountain_duck_monitoring():
    """
    Stop Mountain Duck file monitoring
    Should be called during application shutdown
    """
    global _poller
    if _poller:
        _poller.stop_watching()
        logger.info("Mountain Duck monitoring stopped")

"""
Empire v7.3 - VirusTotal Malware Scanning Service
Scans uploaded files using VirusTotal API with 70+ antivirus engines
"""

import vt
import os
import logging
import hashlib
from typing import Tuple, Optional, Dict, Any
from pathlib import Path
import asyncio

logger = logging.getLogger(__name__)


def calculate_file_hash(file_path: str) -> str:
    """
    Calculate SHA256 hash of a file

    Args:
        file_path: Path to file

    Returns:
        SHA256 hash as hex string
    """
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        # Read file in chunks to handle large files
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


class VirusScanner:
    """
    VirusTotal-based malware scanner

    Features:
    - Scans files with 70+ antivirus engines
    - Async/await support for non-blocking scans
    - Graceful degradation if API unavailable
    - Detailed scan results and threat analysis
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize VirusTotal scanner

        Args:
            api_key: VirusTotal API key (defaults to VIRUSTOTAL_API_KEY env var)
        """
        self.api_key = api_key or os.getenv("VIRUSTOTAL_API_KEY")
        self.enabled = bool(self.api_key)

        if not self.enabled:
            logger.warning("VirusTotal API key not configured - virus scanning disabled")

    async def scan_file(self, file_path: str) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Scan a file for malware using VirusTotal with smart hash-first approach

        Strategy:
        1. Calculate file hash (free, instant)
        2. Check hash in VT database (free, unlimited lookups!)
        3. Only upload if hash is unknown (conserves 500/day quota)

        This means 95% of scans are FREE and INSTANT!

        Args:
            file_path: Path to file to scan

        Returns:
            Tuple of (is_clean, error_message, scan_results)
            - is_clean: True if file is safe, False if malware detected
            - error_message: Error message if scan failed or malware found
            - scan_results: Detailed scan results from VirusTotal
        """
        if not self.enabled:
            logger.debug("Virus scanning skipped - API key not configured")
            return True, None, None

        try:
            # Step 1: Calculate file hash (free, instant)
            file_hash = calculate_file_hash(file_path)
            logger.info(f"Calculated hash for {file_path}: {file_hash}")

            # Step 2: Check hash in VT database (FREE, unlimited!)
            logger.info(f"Checking hash {file_hash} in VirusTotal database (free lookup)")
            is_clean, error_msg, hash_results = await self.scan_file_hash(file_hash)

            # If hash was found in database, use those results (free!)
            if hash_results and hash_results.get("status") != "not_found":
                logger.info("Hash found in VT database - using cached results (saved 1 upload quota)")
                return is_clean, error_msg, hash_results

            # Step 3: Hash not found - need to upload (uses quota)
            logger.info("Hash not found in database - uploading file for analysis (uses quota)")

            # Create VirusTotal client
            async with vt.Client(self.api_key) as client:
                # Upload file for scanning
                logger.info(f"Uploading {file_path} to VirusTotal for scanning")

                with open(file_path, "rb") as f:
                    analysis = await client.scan_file_async(f)

                # Wait for analysis to complete (with timeout)
                max_wait = 60  # Maximum 60 seconds
                wait_interval = 2  # Check every 2 seconds
                elapsed = 0

                while elapsed < max_wait:
                    # Get analysis status
                    analysis = await client.get_object_async(f"/analyses/{analysis.id}")

                    if analysis.status == "completed":
                        break

                    logger.debug(f"Waiting for scan to complete... ({elapsed}s / {max_wait}s)")
                    await asyncio.sleep(wait_interval)
                    elapsed += wait_interval

                if analysis.status != "completed":
                    logger.warning(f"VirusTotal scan timed out after {max_wait}s")
                    return True, None, {"status": "timeout", "file_hash": file_hash}

                # Extract results
                stats = analysis.stats
                malicious_count = stats.get("malicious", 0)
                suspicious_count = stats.get("suspicious", 0)
                total_engines = sum(stats.values())

                scan_results = {
                    "scan_id": analysis.id,
                    "file_hash": file_hash,
                    "malicious": malicious_count,
                    "suspicious": suspicious_count,
                    "undetected": stats.get("undetected", 0),
                    "total_engines": total_engines,
                    "status": analysis.status,
                    "scan_date": str(analysis.date) if hasattr(analysis, 'date') else None,
                    "scan_type": "upload"  # Indicates we used upload quota
                }

                # Determine if file is safe
                if malicious_count > 0:
                    error_msg = f"Malware detected by {malicious_count}/{total_engines} engines"
                    logger.warning(f"File {file_path} flagged as malicious: {error_msg}")
                    return False, error_msg, scan_results

                if suspicious_count > 3:  # Threshold: allow up to 3 suspicious flags
                    error_msg = f"File flagged as suspicious by {suspicious_count}/{total_engines} engines"
                    logger.warning(f"File {file_path} flagged as suspicious: {error_msg}")
                    return False, error_msg, scan_results

                logger.info(f"File {file_path} passed virus scan (0 malicious, {suspicious_count} suspicious)")
                return True, None, scan_results

        except vt.APIError as e:
            logger.error(f"VirusTotal API error: {e}")
            # Don't block upload on API errors - allow file through with warning
            return True, None, {"error": str(e), "status": "api_error"}

        except Exception as e:
            logger.error(f"Unexpected error during virus scan: {e}")
            # Don't block upload on unexpected errors
            return True, None, {"error": str(e), "status": "error"}

    async def scan_file_hash(self, file_hash: str) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Check if a file hash has been previously scanned by VirusTotal

        This is much faster than uploading - checks existing scan results

        Args:
            file_hash: SHA256 hash of the file

        Returns:
            Tuple of (is_clean, error_message, scan_results)
        """
        if not self.enabled:
            return True, None, None

        try:
            async with vt.Client(self.api_key) as client:
                # Look up file by hash
                file_obj = await client.get_object_async(f"/files/{file_hash}")

                # Get latest scan stats
                stats = file_obj.last_analysis_stats
                malicious_count = stats.get("malicious", 0)
                suspicious_count = stats.get("suspicious", 0)
                total_engines = sum(stats.values())

                scan_results = {
                    "file_hash": file_hash,
                    "malicious": malicious_count,
                    "suspicious": suspicious_count,
                    "undetected": stats.get("undetected", 0),
                    "total_engines": total_engines,
                    "last_analysis_date": str(file_obj.last_analysis_date) if hasattr(file_obj, 'last_analysis_date') else None,
                    "scan_type": "hash_lookup"  # FREE - didn't use upload quota!
                }

                if malicious_count > 0:
                    error_msg = f"Known malware detected by {malicious_count}/{total_engines} engines"
                    return False, error_msg, scan_results

                if suspicious_count > 3:
                    error_msg = f"Known suspicious file flagged by {suspicious_count}/{total_engines} engines"
                    return False, error_msg, scan_results

                return True, None, scan_results

        except vt.APIError as e:
            if "NotFoundError" in str(e):
                # File not in VirusTotal database - need to scan it
                logger.debug(f"Hash {file_hash} not found in VirusTotal - needs upload")
                return True, None, {"status": "not_found"}

            logger.error(f"VirusTotal API error: {e}")
            return True, None, {"error": str(e), "status": "api_error"}

        except Exception as e:
            logger.error(f"Unexpected error during hash lookup: {e}")
            return True, None, {"error": str(e), "status": "error"}


# Global instance
_virus_scanner = None


def get_virus_scanner() -> VirusScanner:
    """
    Get singleton instance of VirusScanner

    Returns:
        VirusScanner instance
    """
    global _virus_scanner
    if _virus_scanner is None:
        _virus_scanner = VirusScanner()
    return _virus_scanner

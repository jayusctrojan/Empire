"""
Response Compression Middleware

Task 43.3 - Performance Optimization

Enables Gzip compression for HTTP responses to reduce bandwidth usage
and improve transfer times for large JSON payloads.

Features:
- Automatic compression for responses > 1KB
- Smart content-type detection (JSON, HTML, text)
- Respects client Accept-Encoding header
- Minimal CPU overhead

Usage:
    from app.middleware.compression import add_compression_middleware

    # In app/main.py
    add_compression_middleware(app)
"""

import logging
from starlette.middleware.gzip import GZipMiddleware

logger = logging.getLogger(__name__)


def add_compression_middleware(app, minimum_size: int = 1000):
    """
    Add Gzip compression middleware to FastAPI application

    Compresses responses that are:
    - Larger than minimum_size bytes (default: 1KB)
    - Have compressible content types (JSON, HTML, text, XML)
    - Requested by clients supporting gzip (Accept-Encoding header)

    Args:
        app: FastAPI application instance
        minimum_size: Minimum response size in bytes to compress (default: 1000)

    Example:
        from fastapi import FastAPI
        from app.middleware.compression import add_compression_middleware

        app = FastAPI()
        add_compression_middleware(app, minimum_size=1000)
    """
    # Use Starlette's built-in GZipMiddleware
    # It automatically handles:
    # - Client capability detection (Accept-Encoding: gzip)
    # - Content-type filtering (text/*, application/json, etc.)
    # - Already-compressed content (skips if Content-Encoding present)
    # - Streaming responses

    app.add_middleware(
        GZipMiddleware,
        minimum_size=minimum_size,
        compresslevel=6  # Balance between speed (1) and compression (9)
    )

    logger.info(
        f"Added GZip compression middleware "
        f"(min_size={minimum_size}B, level=6)"
    )


# Compression Statistics Tracking (Optional)
class CompressionStats:
    """
    Track compression effectiveness for monitoring

    Usage:
        from app.middleware.compression import compression_stats

        stats = compression_stats.get_stats()
        # {"requests_compressed": 1234, "bytes_saved": 5678900}
    """

    def __init__(self):
        self.requests_compressed = 0
        self.requests_uncompressed = 0
        self.bytes_before = 0
        self.bytes_after = 0

    def record_compression(self, before_size: int, after_size: int):
        """Record a compressed response"""
        self.requests_compressed += 1
        self.bytes_before += before_size
        self.bytes_after += after_size

    def record_uncompressed(self, size: int):
        """Record an uncompressed response"""
        self.requests_uncompressed += 1
        self.bytes_before += size
        self.bytes_after += size

    def get_stats(self) -> dict:
        """Get compression statistics"""
        total_requests = self.requests_compressed + self.requests_uncompressed
        bytes_saved = self.bytes_before - self.bytes_after

        compression_ratio = 0.0
        if self.bytes_before > 0:
            compression_ratio = (bytes_saved / self.bytes_before) * 100

        return {
            "total_requests": total_requests,
            "requests_compressed": self.requests_compressed,
            "requests_uncompressed": self.requests_uncompressed,
            "compression_rate": (
                (self.requests_compressed / total_requests * 100)
                if total_requests > 0 else 0.0
            ),
            "bytes_before": self.bytes_before,
            "bytes_after": self.bytes_after,
            "bytes_saved": bytes_saved,
            "compression_ratio": compression_ratio
        }

    def reset(self):
        """Reset statistics"""
        self.requests_compressed = 0
        self.requests_uncompressed = 0
        self.bytes_before = 0
        self.bytes_after = 0


# Singleton instance for tracking
compression_stats = CompressionStats()

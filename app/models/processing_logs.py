"""
Empire v7.3 - Processing Logs Model
Data model for error and processing logs
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


class ErrorSeverity(str, Enum):
    """Error severity levels"""
    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ErrorCategory(str, Enum):
    """Error categories"""
    NETWORK = "network"
    SERVICE_UNAVAILABLE = "service_unavailable"
    VALIDATION = "validation"
    PARSING = "parsing"
    DATABASE = "database"
    STORAGE = "storage"
    TIMEOUT = "timeout"
    AUTHENTICATION = "authentication"
    CONFIGURATION = "configuration"
    UNKNOWN = "unknown"


class ProcessingLogEntry(BaseModel):
    """Processing log entry model"""
    id: Optional[str] = None
    timestamp: datetime
    severity: ErrorSeverity
    category: ErrorCategory
    error_type: str
    error_message: str
    stack_trace: Optional[str] = None

    # Context fields
    task_id: Optional[str] = None
    task_type: Optional[str] = None
    file_id: Optional[str] = None
    filename: Optional[str] = None
    user_id: Optional[str] = None
    document_id: Optional[str] = None

    # Retry information
    retry_count: int = 0
    max_retries: int = 3

    # Recovery information
    recovery_action: Optional[str] = None
    resolution_status: str = "unresolved"  # unresolved, retrying, resolved, failed

    # Additional context
    additional_context: Optional[Dict[str, Any]] = None

    # Metadata
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        json_schema_extra = {
            "example": {
                "timestamp": "2025-01-05T10:30:00Z",
                "severity": "error",
                "category": "network",
                "error_type": "ConnectionError",
                "error_message": "Failed to connect to LlamaIndex service",
                "stack_trace": "Traceback (most recent call last)...",
                "task_id": "celery-task-123",
                "task_type": "document_processing",
                "file_id": "b2-file-456",
                "filename": "document.pdf",
                "retry_count": 1,
                "max_retries": 3,
                "resolution_status": "retrying",
                "recovery_action": "exponential_backoff_retry"
            }
        }


class ProcessingLogCreate(BaseModel):
    """Schema for creating a processing log entry"""
    timestamp: datetime
    severity: ErrorSeverity
    category: ErrorCategory
    error_type: str
    error_message: str
    stack_trace: Optional[str] = None
    task_id: Optional[str] = None
    task_type: Optional[str] = None
    file_id: Optional[str] = None
    filename: Optional[str] = None
    user_id: Optional[str] = None
    document_id: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    recovery_action: Optional[str] = None
    resolution_status: str = "unresolved"
    additional_context: Optional[Dict[str, Any]] = None


class ProcessingLogUpdate(BaseModel):
    """Schema for updating a processing log entry"""
    recovery_action: Optional[str] = None
    resolution_status: Optional[str] = None
    additional_context: Optional[Dict[str, Any]] = None


# SQL Schema for Supabase
"""
CREATE TABLE processing_logs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    severity TEXT NOT NULL CHECK (severity IN ('critical', 'error', 'warning', 'info')),
    category TEXT NOT NULL CHECK (category IN (
        'network', 'service_unavailable', 'validation', 'parsing',
        'database', 'storage', 'timeout', 'authentication',
        'configuration', 'unknown'
    )),
    error_type TEXT NOT NULL,
    error_message TEXT NOT NULL,
    stack_trace TEXT,

    -- Context fields
    task_id TEXT,
    task_type TEXT,
    file_id TEXT,
    filename TEXT,
    user_id UUID REFERENCES users(id),
    document_id UUID,

    -- Retry information
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,

    -- Recovery information
    recovery_action TEXT,
    resolution_status TEXT DEFAULT 'unresolved' CHECK (resolution_status IN (
        'unresolved', 'retrying', 'resolved', 'failed'
    )),

    -- Additional context (JSONB for flexible data)
    additional_context JSONB,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX idx_processing_logs_timestamp ON processing_logs(timestamp DESC);
CREATE INDEX idx_processing_logs_severity ON processing_logs(severity);
CREATE INDEX idx_processing_logs_category ON processing_logs(category);
CREATE INDEX idx_processing_logs_task_id ON processing_logs(task_id);
CREATE INDEX idx_processing_logs_file_id ON processing_logs(file_id);
CREATE INDEX idx_processing_logs_resolution_status ON processing_logs(resolution_status);
CREATE INDEX idx_processing_logs_user_id ON processing_logs(user_id);

-- Update updated_at timestamp automatically
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_processing_logs_updated_at BEFORE UPDATE
    ON processing_logs FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
"""

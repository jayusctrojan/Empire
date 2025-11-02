# Milestone 7: Admin Tools and Management

**Purpose**: Implement administrative tools for document management, user management, system statistics, and batch operations.

**Key Technologies**:
- FastAPI admin endpoints with authentication
- Supabase for admin data storage
- Background task management with Celery
- Batch operations for bulk document processing
- System statistics and analytics

**Architecture**:
- Admin-only API endpoints with role-based access control
- Document CRUD operations with cascade deletes
- User management and session tracking
- System-wide statistics dashboards
- Batch processing queues

---

## 7.1 Supabase Schema - Admin Tables

```sql
-- ============================================================================
-- Milestone 7: Admin Tools Schema
-- ============================================================================

-- Admin users table
CREATE TABLE IF NOT EXISTS public.admin_users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    role VARCHAR(50) DEFAULT 'admin', -- 'super_admin', 'admin', 'viewer'
    is_active BOOLEAN DEFAULT true,
    last_login_at TIMESTAMPTZ,
    login_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for admin_users
CREATE INDEX IF NOT EXISTS idx_admin_users_username ON public.admin_users(username);
CREATE INDEX IF NOT EXISTS idx_admin_users_email ON public.admin_users(email);
CREATE INDEX IF NOT EXISTS idx_admin_users_role ON public.admin_users(role);
CREATE INDEX IF NOT EXISTS idx_admin_users_active ON public.admin_users(is_active) WHERE is_active = true;

-- Admin sessions table (for tracking admin logins)
CREATE TABLE IF NOT EXISTS public.admin_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    admin_user_id UUID NOT NULL REFERENCES admin_users(id) ON DELETE CASCADE,
    session_token VARCHAR(255) UNIQUE NOT NULL,
    ip_address VARCHAR(50),
    user_agent TEXT,
    expires_at TIMESTAMPTZ NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for admin_sessions
CREATE INDEX IF NOT EXISTS idx_admin_sessions_token ON public.admin_sessions(session_token);
CREATE INDEX IF NOT EXISTS idx_admin_sessions_user ON public.admin_sessions(admin_user_id);
CREATE INDEX IF NOT EXISTS idx_admin_sessions_active ON public.admin_sessions(is_active) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_admin_sessions_expires ON public.admin_sessions(expires_at);

-- Admin activity log
CREATE TABLE IF NOT EXISTS public.admin_activity_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    admin_user_id UUID REFERENCES admin_users(id) ON DELETE SET NULL,
    action_type VARCHAR(50) NOT NULL, -- 'create', 'update', 'delete', 'bulk_operation'
    resource_type VARCHAR(50) NOT NULL, -- 'document', 'user', 'session', 'system'
    resource_id VARCHAR(255),
    action_details JSONB DEFAULT '{}',
    ip_address VARCHAR(50),
    user_agent TEXT,
    status VARCHAR(20) DEFAULT 'success', -- 'success', 'failure', 'partial'
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for admin_activity_log
CREATE INDEX IF NOT EXISTS idx_admin_activity_user ON public.admin_activity_log(admin_user_id);
CREATE INDEX IF NOT EXISTS idx_admin_activity_type ON public.admin_activity_log(action_type);
CREATE INDEX IF NOT EXISTS idx_admin_activity_resource ON public.admin_activity_log(resource_type);
CREATE INDEX IF NOT EXISTS idx_admin_activity_created ON public.admin_activity_log(created_at DESC);

-- Batch operations table
CREATE TABLE IF NOT EXISTS public.batch_operations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    operation_type VARCHAR(50) NOT NULL, -- 'bulk_delete', 'bulk_reprocess', 'bulk_export'
    initiated_by UUID REFERENCES admin_users(id) ON DELETE SET NULL,
    total_items INTEGER NOT NULL,
    processed_items INTEGER DEFAULT 0,
    successful_items INTEGER DEFAULT 0,
    failed_items INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'running', 'completed', 'failed', 'cancelled'
    parameters JSONB DEFAULT '{}',
    results JSONB DEFAULT '{}',
    error_message TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for batch_operations
CREATE INDEX IF NOT EXISTS idx_batch_ops_status ON public.batch_operations(status);
CREATE INDEX IF NOT EXISTS idx_batch_ops_type ON public.batch_operations(operation_type);
CREATE INDEX IF NOT EXISTS idx_batch_ops_initiated ON public.batch_operations(initiated_by);
CREATE INDEX IF NOT EXISTS idx_batch_ops_created ON public.batch_operations(created_at DESC);

-- System configuration table
CREATE TABLE IF NOT EXISTS public.system_config (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    config_key VARCHAR(100) UNIQUE NOT NULL,
    config_value JSONB NOT NULL,
    config_type VARCHAR(50) NOT NULL, -- 'feature_flag', 'setting', 'limit'
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    modified_by UUID REFERENCES admin_users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for system_config
CREATE INDEX IF NOT EXISTS idx_system_config_key ON public.system_config(config_key);
CREATE INDEX IF NOT EXISTS idx_system_config_type ON public.system_config(config_type);
CREATE INDEX IF NOT EXISTS idx_system_config_active ON public.system_config(is_active) WHERE is_active = true;

-- API usage tracking
CREATE TABLE IF NOT EXISTS public.api_usage_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(100),
    endpoint VARCHAR(255) NOT NULL,
    method VARCHAR(10) NOT NULL,
    status_code INTEGER NOT NULL,
    response_time_ms INTEGER,
    request_size_bytes INTEGER,
    response_size_bytes INTEGER,
    ip_address VARCHAR(50),
    user_agent TEXT,
    error_message TEXT,
    metadata JSONB DEFAULT '{}',
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for api_usage_log (partitioned by day for performance)
CREATE INDEX IF NOT EXISTS idx_api_usage_endpoint ON public.api_usage_log(endpoint);
CREATE INDEX IF NOT EXISTS idx_api_usage_user ON public.api_usage_log(user_id);
CREATE INDEX IF NOT EXISTS idx_api_usage_timestamp ON public.api_usage_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_api_usage_status ON public.api_usage_log(status_code);

-- ============================================================================
-- Admin Functions
-- ============================================================================

-- Function: Get system statistics
CREATE OR REPLACE FUNCTION get_system_statistics()
RETURNS TABLE (
    total_documents BIGINT,
    total_chunks BIGINT,
    total_embeddings BIGINT,
    total_users BIGINT,
    total_sessions BIGINT,
    total_messages BIGINT,
    storage_size_gb DECIMAL(10, 2),
    documents_today BIGINT,
    searches_today BIGINT,
    messages_today BIGINT,
    active_sessions INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        (SELECT COUNT(*) FROM documents)::BIGINT AS total_documents,
        (SELECT COUNT(*) FROM document_chunks)::BIGINT AS total_chunks,
        (SELECT COUNT(*) FROM document_chunks WHERE embedding IS NOT NULL)::BIGINT AS total_embeddings,
        (SELECT COUNT(DISTINCT user_id) FROM chat_sessions)::BIGINT AS total_users,
        (SELECT COUNT(*) FROM chat_sessions)::BIGINT AS total_sessions,
        (SELECT COUNT(*) FROM chat_messages)::BIGINT AS total_messages,
        (SELECT COALESCE(SUM(file_size_bytes), 0) / (1024.0 * 1024.0 * 1024.0) FROM documents)::DECIMAL(10, 2) AS storage_size_gb,
        (SELECT COUNT(*) FROM documents WHERE created_at > NOW() - INTERVAL '1 day')::BIGINT AS documents_today,
        (SELECT COUNT(*) FROM search_queries WHERE created_at > NOW() - INTERVAL '1 day')::BIGINT AS searches_today,
        (SELECT COUNT(*) FROM chat_messages WHERE created_at > NOW() - INTERVAL '1 day')::BIGINT AS messages_today,
        (SELECT COUNT(*) FROM chat_sessions WHERE is_active = true AND last_message_at > NOW() - INTERVAL '1 hour')::INTEGER AS active_sessions;
END;
$$ LANGUAGE plpgsql;

-- Function: Get user activity summary
CREATE OR REPLACE FUNCTION get_user_activity_summary(
    p_user_id VARCHAR(100) DEFAULT NULL,
    p_time_window INTERVAL DEFAULT '7 days'
)
RETURNS TABLE (
    user_id VARCHAR(100),
    document_count BIGINT,
    session_count BIGINT,
    message_count BIGINT,
    search_count BIGINT,
    last_active TIMESTAMPTZ,
    total_tokens_used BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        cs.user_id,
        COUNT(DISTINCT d.id)::BIGINT AS document_count,
        COUNT(DISTINCT cs.id)::BIGINT AS session_count,
        COUNT(cm.id)::BIGINT AS message_count,
        COUNT(sq.id)::BIGINT AS search_count,
        MAX(cs.last_message_at) AS last_active,
        SUM(cs.total_tokens)::BIGINT AS total_tokens_used
    FROM chat_sessions cs
    LEFT JOIN documents d ON d.uploaded_by = cs.user_id
    LEFT JOIN chat_messages cm ON cm.session_id = cs.id
    LEFT JOIN search_queries sq ON sq.user_id = cs.user_id
    WHERE
        cs.created_at > NOW() - p_time_window
        AND (p_user_id IS NULL OR cs.user_id = p_user_id)
    GROUP BY cs.user_id
    ORDER BY last_active DESC;
END;
$$ LANGUAGE plpgsql;

-- Function: Get document statistics by type
CREATE OR REPLACE FUNCTION get_document_statistics_by_type()
RETURNS TABLE (
    file_type VARCHAR(50),
    document_count BIGINT,
    total_size_mb DECIMAL(10, 2),
    avg_chunks_per_doc DECIMAL(10, 2),
    avg_processing_time_ms DECIMAL(10, 2),
    success_rate DECIMAL(5, 2)
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        d.file_type,
        COUNT(*)::BIGINT AS document_count,
        (SUM(d.file_size_bytes) / (1024.0 * 1024.0))::DECIMAL(10, 2) AS total_size_mb,
        (COUNT(dc.id)::DECIMAL / COUNT(DISTINCT d.id)::DECIMAL)::DECIMAL(10, 2) AS avg_chunks_per_doc,
        AVG(pm.duration_ms)::DECIMAL(10, 2) AS avg_processing_time_ms,
        (COUNT(*) FILTER (WHERE d.processing_status = 'completed')::DECIMAL / COUNT(*)::DECIMAL * 100)::DECIMAL(5, 2) AS success_rate
    FROM documents d
    LEFT JOIN document_chunks dc ON d.document_id = dc.document_id
    LEFT JOIN performance_metrics pm ON d.document_id = pm.document_id AND pm.operation_type = 'extraction'
    GROUP BY d.file_type
    ORDER BY document_count DESC;
END;
$$ LANGUAGE plpgsql;

-- Function: Bulk delete documents
CREATE OR REPLACE FUNCTION bulk_delete_documents(
    p_document_ids VARCHAR(64)[],
    p_admin_user_id UUID
)
RETURNS TABLE (
    deleted_count INTEGER,
    failed_ids VARCHAR(64)[]
) AS $$
DECLARE
    doc_id VARCHAR(64);
    deleted INTEGER := 0;
    failed VARCHAR(64)[] := '{}';
BEGIN
    FOREACH doc_id IN ARRAY p_document_ids
    LOOP
        BEGIN
            -- Delete document (cascades to chunks, embeddings, etc.)
            DELETE FROM documents WHERE document_id = doc_id;
            deleted := deleted + 1;

            -- Log admin action
            INSERT INTO admin_activity_log (admin_user_id, action_type, resource_type, resource_id, status)
            VALUES (p_admin_user_id, 'delete', 'document', doc_id, 'success');

        EXCEPTION WHEN OTHERS THEN
            failed := array_append(failed, doc_id);

            -- Log failure
            INSERT INTO admin_activity_log (admin_user_id, action_type, resource_type, resource_id, status, error_message)
            VALUES (p_admin_user_id, 'delete', 'document', doc_id, 'failure', SQLERRM);
        END;
    END LOOP;

    RETURN QUERY SELECT deleted, failed;
END;
$$ LANGUAGE plpgsql;

-- Function: Get slow queries
CREATE OR REPLACE FUNCTION get_slow_queries(
    p_threshold_ms INTEGER DEFAULT 1000,
    p_limit INTEGER DEFAULT 20
)
RETURNS TABLE (
    query_text TEXT,
    search_type VARCHAR(50),
    avg_processing_time_ms DECIMAL(10, 2),
    query_count BIGINT,
    last_executed TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        sq.query_text,
        sq.search_type,
        AVG(sq.processing_time_ms)::DECIMAL(10, 2) AS avg_processing_time_ms,
        COUNT(*)::BIGINT AS query_count,
        MAX(sq.created_at) AS last_executed
    FROM search_queries sq
    WHERE sq.processing_time_ms > p_threshold_ms
    GROUP BY sq.query_text, sq.search_type
    ORDER BY avg_processing_time_ms DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Trigger: Update admin user timestamp
CREATE OR REPLACE FUNCTION update_admin_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_admin_users_timestamp
    BEFORE UPDATE ON admin_users
    FOR EACH ROW
    EXECUTE FUNCTION update_admin_timestamp();

CREATE TRIGGER update_system_config_timestamp
    BEFORE UPDATE ON system_config
    FOR EACH ROW
    EXECUTE FUNCTION update_admin_timestamp();
```

---

## 7.2 Python Services - Admin Management

### 7.2.1 Admin Service

```python
# app/services/admin_service.py

from typing import Dict, List, Optional
from datetime import datetime, timedelta
from passlib.context import CryptContext
import secrets
from supabase import create_client, Client
from app.config import Settings

settings = Settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AdminService:
    """Service for admin user management and authentication"""

    def __init__(self):
        self.supabase: Client = create_client(
            settings.supabase_url,
            settings.supabase_key
        )

    async def create_admin_user(
        self,
        username: str,
        email: str,
        password: str,
        full_name: Optional[str] = None,
        role: str = 'admin'
    ) -> Dict:
        """Create a new admin user"""
        password_hash = pwd_context.hash(password)

        user_data = {
            'username': username,
            'email': email,
            'password_hash': password_hash,
            'full_name': full_name,
            'role': role,
            'is_active': True
        }

        result = self.supabase.table('admin_users').insert(user_data).execute()
        return result.data[0] if result.data else None

    async def authenticate(self, username: str, password: str) -> Optional[Dict]:
        """Authenticate admin user and create session"""
        # Get user
        result = self.supabase.table('admin_users') \
            .select('*') \
            .eq('username', username) \
            .eq('is_active', True) \
            .single() \
            .execute()

        if not result.data:
            return None

        user = result.data

        # Verify password
        if not pwd_context.verify(password, user['password_hash']):
            return None

        # Create session
        session_token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(hours=24)

        session_data = {
            'admin_user_id': user['id'],
            'session_token': session_token,
            'expires_at': expires_at.isoformat(),
            'is_active': True
        }

        session_result = self.supabase.table('admin_sessions') \
            .insert(session_data) \
            .execute()

        # Update login count
        self.supabase.table('admin_users') \
            .update({
                'last_login_at': datetime.now().isoformat(),
                'login_count': user['login_count'] + 1
            }) \
            .eq('id', user['id']) \
            .execute()

        return {
            'user': user,
            'session': session_result.data[0] if session_result.data else None,
            'token': session_token
        }

    async def verify_session(self, session_token: str) -> Optional[Dict]:
        """Verify admin session token"""
        result = self.supabase.table('admin_sessions') \
            .select('*, admin_users(*)') \
            .eq('session_token', session_token) \
            .eq('is_active', True) \
            .gte('expires_at', datetime.now().isoformat()) \
            .single() \
            .execute()

        return result.data if result.data else None

    async def log_admin_activity(
        self,
        admin_user_id: str,
        action_type: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        action_details: Optional[Dict] = None,
        status: str = 'success',
        error_message: Optional[str] = None
    ):
        """Log admin activity"""
        log_data = {
            'admin_user_id': admin_user_id,
            'action_type': action_type,
            'resource_type': resource_type,
            'resource_id': resource_id,
            'action_details': action_details or {},
            'status': status,
            'error_message': error_message
        }

        self.supabase.table('admin_activity_log').insert(log_data).execute()

    async def get_system_statistics(self) -> Dict:
        """Get overall system statistics"""
        result = self.supabase.rpc('get_system_statistics').execute()
        return result.data[0] if result.data else {}

    async def get_user_activity(
        self,
        user_id: Optional[str] = None,
        time_window: str = '7 days'
    ) -> List[Dict]:
        """Get user activity summary"""
        result = self.supabase.rpc(
            'get_user_activity_summary',
            {
                'p_user_id': user_id,
                'p_time_window': time_window
            }
        ).execute()

        return result.data if result.data else []

    async def get_document_statistics(self) -> List[Dict]:
        """Get document statistics by type"""
        result = self.supabase.rpc('get_document_statistics_by_type').execute()
        return result.data if result.data else []

admin_service = AdminService()
```

### 7.2.2 Document Management Service

```python
# app/services/document_management_service.py

from typing import Dict, List, Optional
from datetime import datetime
from supabase import create_client, Client
from app.config import Settings
from app.services.admin_service import admin_service

settings = Settings()

class DocumentManagementService:
    """Service for admin document operations"""

    def __init__(self):
        self.supabase: Client = create_client(
            settings.supabase_url,
            settings.supabase_key
        )

    async def get_all_documents(
        self,
        limit: int = 50,
        offset: int = 0,
        status_filter: Optional[str] = None,
        file_type_filter: Optional[str] = None,
        sort_by: str = 'created_at',
        sort_order: str = 'desc'
    ) -> Dict:
        """Get all documents with filters"""
        query = self.supabase.table('documents').select('*')

        if status_filter:
            query = query.eq('processing_status', status_filter)

        if file_type_filter:
            query = query.eq('file_type', file_type_filter)

        # Apply sorting
        if sort_order == 'desc':
            query = query.order(sort_by, desc=True)
        else:
            query = query.order(sort_by)

        # Apply pagination
        query = query.range(offset, offset + limit - 1)

        result = query.execute()

        # Get total count
        count_query = self.supabase.table('documents').select('id', count='exact')
        if status_filter:
            count_query = count_query.eq('processing_status', status_filter)
        if file_type_filter:
            count_query = count_query.eq('file_type', file_type_filter)

        count_result = count_query.execute()

        return {
            'documents': result.data if result.data else [],
            'total': count_result.count,
            'limit': limit,
            'offset': offset
        }

    async def get_document_details(self, document_id: str) -> Dict:
        """Get detailed document information"""
        # Get document
        doc_result = self.supabase.table('documents') \
            .select('*') \
            .eq('document_id', document_id) \
            .single() \
            .execute()

        if not doc_result.data:
            return None

        document = doc_result.data

        # Get chunks
        chunks_result = self.supabase.table('document_chunks') \
            .select('id, chunk_index, content_length') \
            .eq('document_id', document_id) \
            .execute()

        # Get processing metrics
        metrics_result = self.supabase.table('performance_metrics') \
            .select('*') \
            .eq('document_id', document_id) \
            .execute()

        return {
            'document': document,
            'chunk_count': len(chunks_result.data) if chunks_result.data else 0,
            'chunks': chunks_result.data if chunks_result.data else [],
            'processing_metrics': metrics_result.data if metrics_result.data else []
        }

    async def delete_document(
        self,
        document_id: str,
        admin_user_id: str
    ) -> Dict:
        """Delete a document and all associated data"""
        try:
            # Delete from documents table (cascades to chunks, embeddings)
            result = self.supabase.table('documents') \
                .delete() \
                .eq('document_id', document_id) \
                .execute()

            # Log admin action
            await admin_service.log_admin_activity(
                admin_user_id=admin_user_id,
                action_type='delete',
                resource_type='document',
                resource_id=document_id,
                status='success'
            )

            return {
                'success': True,
                'document_id': document_id,
                'deleted_at': datetime.now().isoformat()
            }

        except Exception as e:
            # Log failure
            await admin_service.log_admin_activity(
                admin_user_id=admin_user_id,
                action_type='delete',
                resource_type='document',
                resource_id=document_id,
                status='failure',
                error_message=str(e)
            )

            return {
                'success': False,
                'error': str(e)
            }

    async def bulk_delete_documents(
        self,
        document_ids: List[str],
        admin_user_id: str
    ) -> Dict:
        """Bulk delete multiple documents"""
        result = self.supabase.rpc(
            'bulk_delete_documents',
            {
                'p_document_ids': document_ids,
                'p_admin_user_id': admin_user_id
            }
        ).execute()

        return {
            'deleted_count': result.data[0]['deleted_count'],
            'failed_ids': result.data[0]['failed_ids'],
            'total_requested': len(document_ids)
        }

    async def reprocess_document(
        self,
        document_id: str,
        admin_user_id: str
    ) -> Dict:
        """Queue document for reprocessing"""
        from app.tasks.celery_tasks import process_document_task

        # Update document status
        self.supabase.table('documents') \
            .update({'processing_status': 'reprocessing'}) \
            .eq('document_id', document_id) \
            .execute()

        # Queue reprocessing task
        task = process_document_task.delay(document_id)

        # Log admin action
        await admin_service.log_admin_activity(
            admin_user_id=admin_user_id,
            action_type='reprocess',
            resource_type='document',
            resource_id=document_id,
            action_details={'task_id': task.id}
        )

        return {
            'success': True,
            'document_id': document_id,
            'task_id': task.id
        }

    async def get_failed_documents(self, limit: int = 50) -> List[Dict]:
        """Get documents that failed processing"""
        result = self.supabase.table('documents') \
            .select('*') \
            .eq('processing_status', 'failed') \
            .order('created_at', desc=True) \
            .limit(limit) \
            .execute()

        return result.data if result.data else []

document_management_service = DocumentManagementService()
```

### 7.2.3 Batch Operations Service

```python
# app/services/batch_operations_service.py

from typing import Dict, List
from datetime import datetime
import asyncio
from supabase import create_client, Client
from app.config import Settings

settings = Settings()

class BatchOperationsService:
    """Service for managing batch operations"""

    def __init__(self):
        self.supabase: Client = create_client(
            settings.supabase_url,
            settings.supabase_key
        )

    async def create_batch_operation(
        self,
        operation_type: str,
        admin_user_id: str,
        total_items: int,
        parameters: Dict
    ) -> Dict:
        """Create a new batch operation"""
        operation_data = {
            'operation_type': operation_type,
            'initiated_by': admin_user_id,
            'total_items': total_items,
            'status': 'pending',
            'parameters': parameters
        }

        result = self.supabase.table('batch_operations') \
            .insert(operation_data) \
            .execute()

        return result.data[0] if result.data else None

    async def update_batch_progress(
        self,
        operation_id: str,
        processed: int,
        successful: int,
        failed: int,
        status: str = 'running'
    ):
        """Update batch operation progress"""
        self.supabase.table('batch_operations') \
            .update({
                'processed_items': processed,
                'successful_items': successful,
                'failed_items': failed,
                'status': status
            }) \
            .eq('id', operation_id) \
            .execute()

    async def complete_batch_operation(
        self,
        operation_id: str,
        results: Dict,
        status: str = 'completed'
    ):
        """Mark batch operation as complete"""
        self.supabase.table('batch_operations') \
            .update({
                'status': status,
                'results': results,
                'completed_at': datetime.now().isoformat()
            }) \
            .eq('id', operation_id) \
            .execute()

    async def get_batch_operation(self, operation_id: str) -> Dict:
        """Get batch operation details"""
        result = self.supabase.table('batch_operations') \
            .select('*') \
            .eq('id', operation_id) \
            .single() \
            .execute()

        return result.data if result.data else None

    async def list_batch_operations(
        self,
        limit: int = 20,
        status_filter: Optional[str] = None
    ) -> List[Dict]:
        """List batch operations"""
        query = self.supabase.table('batch_operations').select('*')

        if status_filter:
            query = query.eq('status', status_filter)

        result = query.order('created_at', desc=True).limit(limit).execute()

        return result.data if result.data else []

batch_operations_service = BatchOperationsService()
```

---

## 7.3 FastAPI Admin Endpoints

```python
# app/routers/admin.py

from fastapi import APIRouter, Depends, HTTPException, Header, Query
from typing import Dict, List, Optional
from datetime import datetime

from app.services.admin_service import admin_service
from app.services.document_management_service import document_management_service
from app.services.batch_operations_service import batch_operations_service

router = APIRouter(prefix="/admin", tags=["admin"])

# Authentication dependency
async def verify_admin_token(authorization: str = Header(None)) -> Dict:
    """Verify admin authentication token"""
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")

    token = authorization.split(' ')[1]
    session = await admin_service.verify_session(token)

    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    return session

# ============================================================================
# Authentication Endpoints
# ============================================================================

@router.post("/auth/login")
async def admin_login(username: str, password: str) -> Dict:
    """Admin login endpoint"""
    auth_result = await admin_service.authenticate(username, password)

    if not auth_result:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return {
        'token': auth_result['token'],
        'user': {
            'id': auth_result['user']['id'],
            'username': auth_result['user']['username'],
            'email': auth_result['user']['email'],
            'role': auth_result['user']['role']
        },
        'expires_at': auth_result['session']['expires_at']
    }

@router.post("/auth/logout")
async def admin_logout(session: Dict = Depends(verify_admin_token)) -> Dict:
    """Admin logout endpoint"""
    # Deactivate session
    admin_service.supabase.table('admin_sessions') \
        .update({'is_active': False}) \
        .eq('session_token', session['session_token']) \
        .execute()

    return {'success': True, 'message': 'Logged out successfully'}

# ============================================================================
# System Statistics
# ============================================================================

@router.get("/stats/system")
async def get_system_stats(session: Dict = Depends(verify_admin_token)) -> Dict:
    """Get overall system statistics"""
    stats = await admin_service.get_system_statistics()
    return {'statistics': stats}

@router.get("/stats/documents")
async def get_document_stats(session: Dict = Depends(verify_admin_token)) -> Dict:
    """Get document statistics by type"""
    stats = await admin_service.get_document_statistics()
    return {'statistics': stats}

@router.get("/stats/users")
async def get_user_stats(
    user_id: Optional[str] = None,
    time_window: str = '7 days',
    session: Dict = Depends(verify_admin_token)
) -> Dict:
    """Get user activity statistics"""
    stats = await admin_service.get_user_activity(user_id, time_window)
    return {'statistics': stats}

# ============================================================================
# Document Management
# ============================================================================

@router.get("/documents")
async def list_documents(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    status: Optional[str] = None,
    file_type: Optional[str] = None,
    sort_by: str = 'created_at',
    sort_order: str = 'desc',
    session: Dict = Depends(verify_admin_token)
) -> Dict:
    """List all documents with filters"""
    result = await document_management_service.get_all_documents(
        limit=limit,
        offset=offset,
        status_filter=status,
        file_type_filter=file_type,
        sort_by=sort_by,
        sort_order=sort_order
    )
    return result

@router.get("/documents/{document_id}")
async def get_document_details(
    document_id: str,
    session: Dict = Depends(verify_admin_token)
) -> Dict:
    """Get detailed document information"""
    details = await document_management_service.get_document_details(document_id)

    if not details:
        raise HTTPException(status_code=404, detail="Document not found")

    return details

@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: str,
    session: Dict = Depends(verify_admin_token)
) -> Dict:
    """Delete a document"""
    admin_user_id = session['admin_users']['id']
    result = await document_management_service.delete_document(document_id, admin_user_id)

    if not result['success']:
        raise HTTPException(status_code=500, detail=result['error'])

    return result

@router.post("/documents/bulk-delete")
async def bulk_delete_documents(
    document_ids: List[str],
    session: Dict = Depends(verify_admin_token)
) -> Dict:
    """Bulk delete multiple documents"""
    admin_user_id = session['admin_users']['id']
    result = await document_management_service.bulk_delete_documents(document_ids, admin_user_id)
    return result

@router.post("/documents/{document_id}/reprocess")
async def reprocess_document(
    document_id: str,
    session: Dict = Depends(verify_admin_token)
) -> Dict:
    """Queue document for reprocessing"""
    admin_user_id = session['admin_users']['id']
    result = await document_management_service.reprocess_document(document_id, admin_user_id)
    return result

@router.get("/documents/failed")
async def get_failed_documents(
    limit: int = Query(50, le=200),
    session: Dict = Depends(verify_admin_token)
) -> Dict:
    """Get documents that failed processing"""
    documents = await document_management_service.get_failed_documents(limit)
    return {'documents': documents, 'count': len(documents)}

# ============================================================================
# Batch Operations
# ============================================================================

@router.get("/batch-operations")
async def list_batch_operations(
    limit: int = Query(20, le=100),
    status: Optional[str] = None,
    session: Dict = Depends(verify_admin_token)
) -> Dict:
    """List batch operations"""
    operations = await batch_operations_service.list_batch_operations(limit, status)
    return {'operations': operations, 'count': len(operations)}

@router.get("/batch-operations/{operation_id}")
async def get_batch_operation(
    operation_id: str,
    session: Dict = Depends(verify_admin_token)
) -> Dict:
    """Get batch operation details"""
    operation = await batch_operations_service.get_batch_operation(operation_id)

    if not operation:
        raise HTTPException(status_code=404, detail="Batch operation not found")

    return operation

# ============================================================================
# Activity Log
# ============================================================================

@router.get("/activity-log")
async def get_activity_log(
    limit: int = Query(50, le=200),
    admin_user_id: Optional[str] = None,
    action_type: Optional[str] = None,
    session: Dict = Depends(verify_admin_token)
) -> Dict:
    """Get admin activity log"""
    query = admin_service.supabase.table('admin_activity_log').select('*')

    if admin_user_id:
        query = query.eq('admin_user_id', admin_user_id)

    if action_type:
        query = query.eq('action_type', action_type)

    result = query.order('created_at', desc=True).limit(limit).execute()

    return {
        'activities': result.data if result.data else [],
        'count': len(result.data) if result.data else 0
    }
```

---

## 7.4 Environment Variables

```bash
# Add to .env

# Admin Settings
ADMIN_SESSION_DURATION_HOURS=24
ADMIN_PASSWORD_MIN_LENGTH=8
ENABLE_ADMIN_ACTIVITY_LOG=true

# Batch Operations
MAX_BATCH_SIZE=1000
BATCH_OPERATION_TIMEOUT_MINUTES=30
```

---

**Performance Targets**:
- Admin authentication: <200ms
- Document list with filters: <500ms
- Bulk delete (100 documents): <5 seconds
- Statistics calculation: <1 second
- Activity log retrieval: <300ms

**Next**: Milestone 8 (CrewAI Integration) with Supabase schemas

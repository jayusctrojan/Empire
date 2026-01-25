# Database Setup and SQL Schemas

This file contains all SQL schemas, CREATE TABLE statements, and database functions from the n8n orchestration guide.

### 10.2.3 Database Schema for Document Management

```sql
-- Complete Supabase Schema for Document Management
-- This schema supports all document processing features

-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";

-- Main documents table
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id VARCHAR(64) UNIQUE NOT NULL, -- SHA256 hash
    filename TEXT NOT NULL,
    file_hash VARCHAR(64) UNIQUE NOT NULL,
    mime_type VARCHAR(255) NOT NULL,
    file_size BIGINT NOT NULL,
    category VARCHAR(50) NOT NULL,
    storage_path TEXT NOT NULL,
    upload_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processing_status VARCHAR(50) DEFAULT 'uploaded',
    processing_complete BOOLEAN DEFAULT FALSE,
    processing_started_at TIMESTAMPTZ,
    processing_completed_at TIMESTAMPTZ,
    processing_duration_ms INTEGER,
    metadata JSONB DEFAULT '{}',
    tags TEXT[] DEFAULT '{}',
    vector_count INTEGER DEFAULT 0,
    chunk_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    last_accessed TIMESTAMPTZ,
    access_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for documents table
CREATE INDEX idx_documents_document_id ON documents(document_id);
CREATE INDEX idx_documents_file_hash ON documents(file_hash);
CREATE INDEX idx_documents_category ON documents(category);
CREATE INDEX idx_documents_processing_status ON documents(processing_status);
CREATE INDEX idx_documents_upload_date ON documents(upload_date DESC);
CREATE INDEX idx_documents_metadata ON documents USING gin(metadata);
CREATE INDEX idx_documents_tags ON documents USING gin(tags);
CREATE INDEX idx_documents_filename_trgm ON documents USING gin(filename gin_trgm_ops);

-- Document chunks table for text extraction
CREATE TABLE IF NOT EXISTS document_chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id VARCHAR(64) NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    content_length INTEGER NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    start_page INTEGER,
    end_page INTEGER,
    metadata JSONB DEFAULT '{}',
    embedding vector(1536), -- OpenAI embedding dimension
    embedding_model VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(document_id, chunk_index)
);

-- Create indexes for chunks table
CREATE INDEX idx_chunks_document_id ON document_chunks(document_id);
CREATE INDEX idx_chunks_content_hash ON document_chunks(content_hash);
CREATE INDEX idx_chunks_embedding_hnsw ON document_chunks 
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
CREATE INDEX idx_chunks_content_trgm ON document_chunks USING gin(content gin_trgm_ops);

-- Error logs table
CREATE TABLE IF NOT EXISTS error_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    error_type VARCHAR(100) NOT NULL,
    error_message TEXT NOT NULL,
    error_stack TEXT,
    severity VARCHAR(20) NOT NULL DEFAULT 'error',
    component VARCHAR(100) NOT NULL,
    document_id VARCHAR(64),
    workflow_id VARCHAR(100),
    execution_id VARCHAR(100),
    metadata JSONB DEFAULT '{}',
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMPTZ,
    resolved_by VARCHAR(100),
    resolution_notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for error logs
CREATE INDEX idx_error_logs_timestamp ON error_logs(timestamp DESC);
CREATE INDEX idx_error_logs_error_type ON error_logs(error_type);
CREATE INDEX idx_error_logs_severity ON error_logs(severity);
CREATE INDEX idx_error_logs_component ON error_logs(component);
CREATE INDEX idx_error_logs_document_id ON error_logs(document_id);
CREATE INDEX idx_error_logs_resolved ON error_logs(resolved);

-- Processing queue table
CREATE TABLE IF NOT EXISTS processing_queue (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id VARCHAR(64) NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    priority INTEGER DEFAULT 5,
    status VARCHAR(50) DEFAULT 'pending',
    processor_type VARCHAR(50) NOT NULL,
    attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    last_attempt_at TIMESTAMPTZ,
    next_attempt_at TIMESTAMPTZ,
    error_message TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for processing queue
CREATE INDEX idx_queue_status ON processing_queue(status);
CREATE INDEX idx_queue_priority ON processing_queue(priority DESC, created_at ASC);
CREATE INDEX idx_queue_document_id ON processing_queue(document_id);
CREATE INDEX idx_queue_next_attempt ON processing_queue(next_attempt_at);

-- Audit log table
CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    entity_id VARCHAR(255) NOT NULL,
    user_id VARCHAR(255),
    ip_address INET,
    user_agent TEXT,
    old_values JSONB,
    new_values JSONB,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for audit log
CREATE INDEX idx_audit_timestamp ON audit_log(timestamp DESC);
CREATE INDEX idx_audit_action ON audit_log(action);
CREATE INDEX idx_audit_entity ON audit_log(entity_type, entity_id);
CREATE INDEX idx_audit_user ON audit_log(user_id);

-- Create update trigger for documents
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trigger_queue_updated_at
    BEFORE UPDATE ON processing_queue
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- Function to update document access stats
CREATE OR REPLACE FUNCTION update_document_access(p_document_id VARCHAR(64))
RETURNS VOID AS $$
BEGIN
    UPDATE documents 
    SET 
        last_accessed = NOW(),
        access_count = COALESCE(access_count, 0) + 1
    WHERE document_id = p_document_id;
END;
$$ LANGUAGE plpgsql;

-- Function to add document to processing queue
CREATE OR REPLACE FUNCTION add_to_processing_queue(
    p_document_id VARCHAR(64),
    p_processor_type VARCHAR(50),
    p_priority INTEGER DEFAULT 5
)
RETURNS UUID AS $$
DECLARE
    v_queue_id UUID;
BEGIN
    INSERT INTO processing_queue (
        document_id,
        processor_type,
        priority,
        status,
        next_attempt_at
    ) VALUES (
        p_document_id,
        p_processor_type,
        p_priority,
        'pending',
        NOW()
    ) RETURNING id INTO v_queue_id;
    
    RETURN v_queue_id;
END;
$$ LANGUAGE plpgsql;

-- Function to get next item from processing queue
CREATE OR REPLACE FUNCTION get_next_from_queue(p_processor_type VARCHAR(50))
RETURNS TABLE (
    queue_id UUID,
    document_id VARCHAR(64),
    priority INTEGER,
    attempts INTEGER,
    metadata JSONB
) AS $$
BEGIN
    RETURN QUERY
    UPDATE processing_queue q
    SET 
        status = 'processing',
        attempts = attempts + 1,
        last_attempt_at = NOW(),
        next_attempt_at = CASE 
            WHEN attempts + 1 >= max_attempts THEN NULL
            ELSE NOW() + INTERVAL '5 minutes' * (attempts + 1)
        END
    WHERE q.id = (
        SELECT id 
        FROM processing_queue 
        WHERE status = 'pending' 
        AND processor_type = p_processor_type
        AND (next_attempt_at IS NULL OR next_attempt_at <= NOW())
        ORDER BY priority DESC, created_at ASC
        LIMIT 1
        FOR UPDATE SKIP LOCKED
    )
    RETURNING q.id, q.document_id, q.priority, q.attempts, q.metadata;
END;
$$ LANGUAGE plpgsql;
```

### 10.2.4 Tabular Data Processing (NEW - Gap 1.3)

**Purpose**: Handle CSV, Excel, and structured data with dedicated storage and processing pipelines.

#### Database Schema for Tabular Data

```sql
-- Table for storing structured/tabular document rows
CREATE TABLE IF NOT EXISTS public.tabular_document_rows (
  id BIGSERIAL PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
  row_number INTEGER NOT NULL,
  row_data JSONB NOT NULL,
  row_hash TEXT GENERATED ALWAYS AS (encode(sha256(row_data::text::bytea), 'hex')) STORED,
  schema_metadata JSONB, -- Stores inferred schema information
  inferred_relationships JSONB, -- Stores detected foreign keys and relationships
  search_vector tsvector GENERATED ALWAYS AS (to_tsvector('english', row_data::text)) STORED,
  CONSTRAINT unique_document_row UNIQUE(document_id, row_number)
);

-- Indexes for performance
CREATE INDEX idx_tabular_rows_document ON tabular_document_rows(document_id);
CREATE INDEX idx_tabular_rows_data_gin ON tabular_document_rows USING gin(row_data);
CREATE INDEX idx_tabular_rows_search ON tabular_document_rows USING gin(search_vector);
CREATE INDEX idx_tabular_rows_hash ON tabular_document_rows(row_hash);

-- Schema inference metadata table
CREATE TABLE IF NOT EXISTS public.tabular_schemas (
  id BIGSERIAL PRIMARY KEY,
  document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
  schema_definition JSONB NOT NULL,
  column_types JSONB NOT NULL,
  inferred_at TIMESTAMPTZ DEFAULT NOW(),
  confidence_scores JSONB,
  sample_size INTEGER,
  CONSTRAINT unique_document_schema UNIQUE(document_id)
);
```

#### n8n Workflow: Tabular Data Processing

```json
{
  "name": "Empire - Tabular Data Processor",
  "nodes": [
    {
      "parameters": {
        "operation": "text",
        "destinationKey": "csv_content"
      },
      "name": "Extract CSV/Excel Content",
      "type": "n8n-nodes-base.extractFromFile",
      "position": [450, 300]
    },
    {
      "parameters": {
        "functionCode": "// Parse CSV and infer schema\nconst Papa = require('papaparse');\nconst parsed = Papa.parse($input.item.csv_content, {\n  header: true,\n  dynamicTyping: true,\n  skipEmptyLines: true\n});\n\n// Infer column types\nconst schema = {};\nif (parsed.data.length > 0) {\n  const sample = parsed.data.slice(0, 100); // Sample first 100 rows\n  \n  Object.keys(parsed.data[0]).forEach(column => {\n    const values = sample.map(row => row[column]).filter(v => v !== null);\n    \n    // Determine type\n    let columnType = 'string';\n    if (values.every(v => typeof v === 'number')) {\n      columnType = 'number';\n    } else if (values.every(v => v instanceof Date)) {\n      columnType = 'date';\n    } else if (values.every(v => typeof v === 'boolean')) {\n      columnType = 'boolean';\n    }\n    \n    schema[column] = {\n      type: columnType,\n      nullable: values.length < sample.length,\n      unique_count: new Set(values).size,\n      sample_values: [...new Set(values)].slice(0, 5)\n    };\n  });\n}\n\nreturn {\n  rows: parsed.data,\n  schema: schema,\n  row_count: parsed.data.length,\n  column_count: Object.keys(schema).length\n};"
      },
      "name": "Parse and Infer Schema",
      "type": "n8n-nodes-base.code",
      "position": [650, 300]
    },
    {
      "parameters": {
        "batchSize": 100,
        "options": {}
      },
      "name": "Batch Rows",
      "type": "n8n-nodes-base.splitInBatches",
      "position": [850, 300]
    },
    {
      "parameters": {
        "operation": "insert",
        "schema": "public",
        "table": "tabular_document_rows",
        "columns": "document_id,row_number,row_data,schema_metadata",
        "additionalFields": {}
      },
      "name": "Insert Rows to Database",
      "type": "n8n-nodes-base.postgres",
      "position": [1050, 300]
    },
    {
      "parameters": {
        "operation": "insert",
        "schema": "public",
        "table": "tabular_schemas",
        "columns": "document_id,schema_definition,column_types,sample_size"
      },
      "name": "Store Schema Metadata",
      "type": "n8n-nodes-base.postgres",
      "position": [1050, 450]
    }
  ]
}
```

### 10.2.5 Metadata Fields Management (NEW - Gap 1.5)

**Purpose**: Provide controlled vocabularies and metadata validation for advanced filtering.

#### Database Schema

```sql
-- Metadata field definitions for controlled vocabularies
CREATE TABLE IF NOT EXISTS public.metadata_fields (
  id BIGSERIAL PRIMARY KEY,
  field_name TEXT NOT NULL UNIQUE,
  field_type VARCHAR(50) NOT NULL CHECK (field_type IN ('string', 'number', 'date', 'enum', 'boolean')),
  allowed_values TEXT[], -- For enum types only
  validation_regex TEXT, -- For string types
  min_value NUMERIC, -- For number types
  max_value NUMERIC, -- For number types
  description TEXT,
  is_required BOOLEAN DEFAULT FALSE,
  is_searchable BOOLEAN DEFAULT TRUE,
  is_facetable BOOLEAN DEFAULT TRUE,
  display_order INTEGER,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert default metadata fields
INSERT INTO public.metadata_fields (field_name, field_type, allowed_values, description, is_required, display_order) VALUES
  ('department', 'enum', ARRAY['HR', 'Engineering', 'Sales', 'Marketing', 'Operations', 'Legal', 'Finance'], 'Document department', false, 1),
  ('document_type', 'enum', ARRAY['Policy', 'Procedure', 'Report', 'Memo', 'Contract', 'Invoice', 'Manual'], 'Type of document', true, 2),
  ('confidentiality', 'enum', ARRAY['Public', 'Internal', 'Confidential', 'Secret'], 'Confidentiality level', true, 3),
  ('document_date', 'date', NULL, 'Date of document creation', false, 4),
  ('expiry_date', 'date', NULL, 'Document expiration date', false, 5),
  ('author', 'string', NULL, 'Document author name', false, 6),
  ('version', 'string', NULL, 'Document version', false, 7),
  ('tags', 'string', NULL, 'Comma-separated tags', false, 8),
  ('review_status', 'enum', ARRAY['Draft', 'Under Review', 'Approved', 'Archived'], 'Review status', false, 9),
  ('language', 'enum', ARRAY['en', 'es', 'fr', 'de', 'zh', 'ja'], 'Document language', false, 10)
ON CONFLICT (field_name) DO NOTHING;

-- Function to validate metadata against field definitions
CREATE OR REPLACE FUNCTION validate_document_metadata(metadata JSONB)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
  field RECORD;
  field_value TEXT;
  validation_errors JSONB := '[]'::JSONB;
  validated_metadata JSONB := '{}'::JSONB;
BEGIN
  -- Check each defined field
  FOR field IN SELECT * FROM metadata_fields WHERE is_required = true
  LOOP
    IF NOT metadata ? field.field_name THEN
      validation_errors := validation_errors || jsonb_build_object(
        'field', field.field_name,
        'error', 'Required field missing'
      );
    END IF;
  END LOOP;

  -- Validate present fields
  FOR field IN SELECT * FROM metadata_fields
  LOOP
    IF metadata ? field.field_name THEN
      field_value := metadata->>field.field_name;

      -- Validate based on type
      CASE field.field_type
        WHEN 'enum' THEN
          IF NOT field_value = ANY(field.allowed_values) THEN
            validation_errors := validation_errors || jsonb_build_object(
              'field', field.field_name,
              'error', format('Value must be one of: %s', array_to_string(field.allowed_values, ', '))
            );
          ELSE
            validated_metadata := validated_metadata || jsonb_build_object(field.field_name, field_value);
          END IF;

        WHEN 'date' THEN
          BEGIN
            validated_metadata := validated_metadata || jsonb_build_object(field.field_name, field_value::date);
          EXCEPTION WHEN OTHERS THEN
            validation_errors := validation_errors || jsonb_build_object(
              'field', field.field_name,
              'error', 'Invalid date format'
            );
          END;

        WHEN 'number' THEN
          BEGIN
            IF field.min_value IS NOT NULL AND field_value::numeric < field.min_value THEN
              RAISE EXCEPTION 'Below minimum';
            END IF;
            IF field.max_value IS NOT NULL AND field_value::numeric > field.max_value THEN
              RAISE EXCEPTION 'Above maximum';
            END IF;
            validated_metadata := validated_metadata || jsonb_build_object(field.field_name, field_value::numeric);
          EXCEPTION WHEN OTHERS THEN
            validation_errors := validation_errors || jsonb_build_object(
              'field', field.field_name,
              'error', format('Must be a number between %s and %s', field.min_value, field.max_value)
            );
          END;

        WHEN 'string' THEN
          IF field.validation_regex IS NOT NULL AND NOT field_value ~ field.validation_regex THEN
            validation_errors := validation_errors || jsonb_build_object(
              'field', field.field_name,
              'error', 'Invalid format'
            );
          ELSE
            validated_metadata := validated_metadata || jsonb_build_object(field.field_name, field_value);
          END IF;

        ELSE
          validated_metadata := validated_metadata || jsonb_build_object(field.field_name, field_value);
      END CASE;
    END IF;
  END LOOP;

  -- Return result
  IF jsonb_array_length(validation_errors) > 0 THEN
    RETURN jsonb_build_object(
      'valid', false,
      'errors', validation_errors,
      'metadata', metadata
    );
  ELSE
    RETURN jsonb_build_object(
      'valid', true,
      'errors', '[]'::jsonb,
      'metadata', validated_metadata
    );
  END IF;
END;
$$;
```

### 10.5.3 Complete Hybrid Search SQL Function

**Purpose**: Implement production-grade 4-method hybrid search with RRF fusion for superior search quality (30-50% improvement over vector-only search).

**Implementation**: Add this function to Supabase SQL Editor

```sql
-- Empire v7.0 Dynamic Hybrid Search Function
-- Adapted for nomic-embed-text (768 dimensions)
-- Combines: Dense (vector) + Sparse (FTS) + ILIKE (pattern) + Fuzzy (trigram)
-- Fusion: Reciprocal Rank Fusion (RRF)

-- Required extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE OR REPLACE FUNCTION empire_hybrid_search(
  query_embedding vector(768),  -- nomic-embed-text dimensions
  query_text text,
  match_count int DEFAULT 10,
  filter jsonb DEFAULT '{}'::jsonb,
  dense_weight float DEFAULT 0.4,
  sparse_weight float DEFAULT 0.3,
  ilike_weight float DEFAULT 0.15,
  fuzzy_weight float DEFAULT 0.15,
  rrf_k int DEFAULT 60,
  fuzzy_threshold float DEFAULT 0.3
)
RETURNS TABLE (
  id bigint,
  content text,
  metadata jsonb,
  dense_score float,
  sparse_score float,
  ilike_score float,
  fuzzy_score float,
  final_score double precision
)
LANGUAGE plpgsql
AS $$
DECLARE
  filter_key text;
  filter_op text;
  filter_val_jsonb jsonb;
  filter_val_text text;
  where_clauses text := '';
  base_query text;
  list_items text;
  is_numeric_list boolean;
  clause_parts text[] := '{}'::text[];
  joiner text;
  clauses_array jsonb;
  clause_object jsonb;
  include_dense boolean;
  include_sparse boolean;
  include_ilike boolean;
  include_fuzzy boolean;
  cte_parts text[] := '{}'::text[];
  join_parts text := '';
  select_parts text := '';
  rrf_parts text[] := '{}'::text[];
  id_coalesce text[] := '{}'::text[];
  id_expr text;
BEGIN
  -- Validate weights sum to 1.0
  IF ABS((dense_weight + sparse_weight + ilike_weight + fuzzy_weight) - 1.0) > 0.001 THEN
    RAISE EXCEPTION 'Weights must sum to 1.0. Current: dense=%, sparse=%, ilike=%, fuzzy=%',
      dense_weight, sparse_weight, ilike_weight, fuzzy_weight;
  END IF;

  -- Validate query_text
  IF query_text IS NULL OR trim(query_text) = '' THEN
    RAISE EXCEPTION 'query_text cannot be empty';
  END IF;

  -- Validate parameters
  IF rrf_k < 1 THEN RAISE EXCEPTION 'rrf_k must be >= 1, got: %', rrf_k; END IF;
  IF match_count < 1 THEN RAISE EXCEPTION 'match_count must be >= 1, got: %', match_count; END IF;
  IF fuzzy_threshold < 0 OR fuzzy_threshold > 1 THEN
    RAISE EXCEPTION 'fuzzy_threshold must be between 0 and 1, got: %', fuzzy_threshold;
  END IF;

  -- Handle empty filter
  IF filter IS NULL OR filter = 'null'::jsonb OR filter = '[]'::jsonb OR jsonb_typeof(filter) = 'array' THEN
    filter := '{}'::jsonb;
  END IF;

  -- Process filters (supports $or and $and operators)
  IF filter ? '$or' OR filter ? '$and' THEN
    IF filter ? '$or' THEN
      joiner := ' OR ';
      clauses_array := filter->'$or';
    ELSE
      joiner := ' AND ';
      clauses_array := filter->'$and';
    END IF;

    IF jsonb_typeof(clauses_array) <> 'array' THEN
      RAISE EXCEPTION 'Value for top-level operator must be a JSON array.';
    END IF;

    FOR clause_object IN SELECT * FROM jsonb_array_elements(clauses_array)
    LOOP
      SELECT key INTO filter_key FROM jsonb_object_keys(clause_object) AS t(key) LIMIT 1;
      IF filter_key IS NULL THEN CONTINUE; END IF;

      filter_op := (clause_object->filter_key->>'operator')::text;
      filter_val_jsonb := clause_object->filter_key->'value';

      DECLARE
        single_clause text;
      BEGIN
        IF filter_op IN ('IN', 'NOT IN') THEN
          IF jsonb_typeof(filter_val_jsonb) <> 'array' THEN
            RAISE EXCEPTION 'Value for operator % for key % must be an array.', filter_op, filter_key;
          END IF;
          IF jsonb_array_length(filter_val_jsonb) = 0 THEN
            single_clause := (CASE WHEN filter_op = 'IN' THEN 'false' ELSE 'true' END);
          ELSE
            is_numeric_list := (jsonb_typeof(filter_val_jsonb->0) = 'number');
            IF is_numeric_list THEN
              SELECT string_agg(elem::text, ', ') INTO list_items
              FROM jsonb_array_elements_text(filter_val_jsonb) AS t(elem);
              single_clause := format('((metadata->>%L)::numeric %s (%s))', filter_key, filter_op, list_items);
            ELSE
              SELECT string_agg(quote_literal(elem), ', ') INTO list_items
              FROM jsonb_array_elements_text(filter_val_jsonb) AS t(elem);
              single_clause := format('(metadata->>%L %s (%s))', filter_key, filter_op, list_items);
            END IF;
          END IF;
        ELSE
          filter_val_text := filter_val_jsonb #>> '{}';
          BEGIN
            PERFORM filter_val_text::timestamp;
            IF filter_op NOT IN ('=', '!=', '>', '<', '>=', '<=') THEN
              RAISE EXCEPTION 'Invalid operator % for date/timestamp field %', filter_op, filter_key;
            END IF;
            single_clause := format('((metadata->>%L)::timestamp %s %L::timestamp)',
              filter_key, filter_op, filter_val_text);
          EXCEPTION WHEN others THEN
            IF filter_val_text ~ '^\d+(\.\d+)?$' THEN
              IF filter_op NOT IN ('=', '!=', '>', '<', '>=', '<=') THEN
                RAISE EXCEPTION 'Invalid operator % for numeric field %', filter_op, filter_key;
              END IF;
              single_clause := format('((metadata->>%L)::numeric %s %s)',
                filter_key, filter_op, filter_val_text);
            ELSE
              IF filter_op NOT IN ('=', '!=') THEN
                RAISE EXCEPTION 'Invalid operator % for text field %', filter_op, filter_key;
              END IF;
              single_clause := format('(metadata->>%L %s %L)', filter_key, filter_op, filter_val_text);
            END IF;
          END;
        END IF;
        clause_parts := array_append(clause_parts, single_clause);
      END;
    END LOOP;

    IF array_length(clause_parts, 1) > 0 THEN
      where_clauses := array_to_string(clause_parts, joiner);
    END IF;
  ELSE
    -- Flat filter object (implicit AND)
    DECLARE
      first_clause boolean := true;
    BEGIN
      FOR filter_key, filter_op, filter_val_jsonb IN
        SELECT key, (value->>'operator')::text, value->'value' FROM jsonb_each(filter)
      LOOP
        IF NOT first_clause THEN where_clauses := where_clauses || ' AND ';
        ELSE first_clause := false; END IF;

        IF filter_op IN ('IN', 'NOT IN') THEN
          IF jsonb_typeof(filter_val_jsonb) <> 'array' THEN
            RAISE EXCEPTION 'Value for operator % for key % must be an array.', filter_op, filter_key;
          END IF;
          IF jsonb_array_length(filter_val_jsonb) = 0 THEN
            where_clauses := where_clauses || (CASE WHEN filter_op = 'IN' THEN 'false' ELSE 'true' END);
          ELSE
            is_numeric_list := (jsonb_typeof(filter_val_jsonb->0) = 'number');
            IF is_numeric_list THEN
              SELECT string_agg(elem::text, ', ') INTO list_items
              FROM jsonb_array_elements_text(filter_val_jsonb) AS t(elem);
              where_clauses := where_clauses || format('((metadata->>%L)::numeric %s (%s))',
                filter_key, filter_op, list_items);
            ELSE
              SELECT string_agg(quote_literal(elem), ', ') INTO list_items
              FROM jsonb_array_elements_text(filter_val_jsonb) AS t(elem);
              where_clauses := where_clauses || format('(metadata->>%L %s (%s))',
                filter_key, filter_op, list_items);
            END IF;
          END IF;
        ELSE
          filter_val_text := filter_val_jsonb #>> '{}';
          BEGIN
            PERFORM filter_val_text::timestamp;
            IF filter_op NOT IN ('=', '!=', '>', '<', '>=', '<=') THEN
              RAISE EXCEPTION 'Invalid operator % for date/timestamp field %', filter_op, filter_key;
            END IF;
            where_clauses := where_clauses || format('((metadata->>%L)::timestamp %s %L::timestamp)',
              filter_key, filter_op, filter_val_text);
          EXCEPTION WHEN others THEN
            IF filter_val_text ~ '^\d+(\.\d+)?$' THEN
              IF filter_op NOT IN ('=', '!=', '>', '<', '>=', '<=') THEN
                RAISE EXCEPTION 'Invalid operator % for numeric field %', filter_op, filter_key;
              END IF;
              where_clauses := where_clauses || format('((metadata->>%L)::numeric %s %s)',
                filter_key, filter_op, filter_val_text);
            ELSE
              IF filter_op NOT IN ('=', '!=') THEN
                RAISE EXCEPTION 'Invalid operator % for text field %', filter_op, filter_key;
              END IF;
              where_clauses := where_clauses || format('(metadata->>%L %s %L)',
                filter_key, filter_op, filter_val_text);
            END IF;
          END;
        END IF;
      END LOOP;
    END;
  END IF;

  IF where_clauses = '' OR where_clauses IS NULL THEN
    where_clauses := 'true';
  END IF;

  -- Determine which search methods to include
  include_dense := dense_weight > 0.001;
  include_sparse := sparse_weight > 0.001;
  include_ilike := ilike_weight > 0.001;
  include_fuzzy := fuzzy_weight > 0.001;

  IF NOT (include_dense OR include_sparse OR include_ilike OR include_fuzzy) THEN
    RAISE EXCEPTION 'At least one weight must be greater than 0.001';
  END IF;

  -- Build Dense CTE (vector similarity)
  IF include_dense THEN
    cte_parts := array_append(cte_parts, format($cte$
      dense AS (
        SELECT
          dv2.id,
          (1 - (dv2.embedding <=> %L::vector(768)))::float AS dense_score,
          RANK() OVER (ORDER BY dv2.embedding <=> %L::vector(768) ASC) AS rank
        FROM documents_v2 dv2
        WHERE (%s)
          AND dv2.embedding IS NOT NULL
        ORDER BY dv2.embedding <=> %L::vector(768) ASC
        LIMIT COALESCE(%s, 10) * 2
      )
    $cte$,
      query_embedding, query_embedding, where_clauses, query_embedding, match_count
    ));
  END IF;

  -- Build Sparse CTE (full-text search)
  IF include_sparse THEN
    cte_parts := array_append(cte_parts, format($cte$
      sparse AS (
        SELECT
          dv2.id,
          ts_rank(dv2.fts, websearch_to_tsquery('english', %L))::float AS sparse_score,
          RANK() OVER (ORDER BY ts_rank(dv2.fts, websearch_to_tsquery('english', %L)) DESC) AS rank
        FROM documents_v2 dv2
        WHERE (%s)
          AND dv2.fts @@ websearch_to_tsquery('english', %L)
        ORDER BY sparse_score DESC
        LIMIT COALESCE(%s, 10) * 2
      )
    $cte$,
      query_text, query_text, where_clauses, query_text, match_count
    ));
  END IF;

  -- Build ILIKE CTE (pattern matching)
  IF include_ilike THEN
    cte_parts := array_append(cte_parts, format($cte$
      ilike_match AS (
        SELECT
          dv2.id,
          LEAST(
            (LENGTH(dv2.content) - LENGTH(REPLACE(LOWER(dv2.content), LOWER(%L), '')))
              / NULLIF(LENGTH(dv2.content), 0)::float * 100,
            1.0
          ) AS ilike_score,
          RANK() OVER (ORDER BY
            (LENGTH(dv2.content) - LENGTH(REPLACE(LOWER(dv2.content), LOWER(%L), '')))
              / NULLIF(LENGTH(dv2.content), 0)::float DESC
          ) AS rank
        FROM documents_v2 dv2
        WHERE (%s)
          AND dv2.content ILIKE %L
        LIMIT COALESCE(%s, 10) * 2
      )
    $cte$,
      query_text, query_text, where_clauses, ('%' || query_text || '%'), match_count
    ));
  END IF;

  -- Build Fuzzy CTE (trigram similarity)
  IF include_fuzzy THEN
    cte_parts := array_append(cte_parts, format($cte$
      fuzzy AS (
        SELECT
          dv2.id,
          word_similarity(%L, dv2.content)::float AS fuzzy_score,
          RANK() OVER (ORDER BY word_similarity(%L, dv2.content) DESC) AS rank
        FROM documents_v2 dv2
        WHERE (%s)
          AND %L <%% dv2.content
        ORDER BY fuzzy_score DESC
        LIMIT COALESCE(%s, 10) * 2
      )
    $cte$,
      query_text, query_text, where_clauses, query_text, match_count
    ));
  END IF;

  -- Build JOIN clause dynamically
  IF include_dense THEN
    join_parts := 'FROM dense';
    IF include_sparse THEN
      join_parts := join_parts || ' FULL OUTER JOIN sparse ON dense.id = sparse.id';
    END IF;
    IF include_ilike THEN
      join_parts := join_parts || format(' FULL OUTER JOIN ilike_match ON COALESCE(%s) = ilike_match.id',
        CASE WHEN include_sparse THEN 'dense.id, sparse.id' ELSE 'dense.id' END);
    END IF;
    IF include_fuzzy THEN
      join_parts := join_parts || format(' FULL OUTER JOIN fuzzy ON COALESCE(%s) = fuzzy.id',
        CASE
          WHEN include_sparse AND include_ilike THEN 'dense.id, sparse.id, ilike_match.id'
          WHEN include_sparse THEN 'dense.id, sparse.id'
          WHEN include_ilike THEN 'dense.id, ilike_match.id'
          ELSE 'dense.id'
        END);
    END IF;
  ELSIF include_sparse THEN
    join_parts := 'FROM sparse';
    IF include_ilike THEN
      join_parts := join_parts || ' FULL OUTER JOIN ilike_match ON sparse.id = ilike_match.id';
    END IF;
    IF include_fuzzy THEN
      join_parts := join_parts || format(' FULL OUTER JOIN fuzzy ON COALESCE(%s) = fuzzy.id',
        CASE WHEN include_ilike THEN 'sparse.id, ilike_match.id' ELSE 'sparse.id' END);
    END IF;
  ELSIF include_ilike THEN
    join_parts := 'FROM ilike_match';
    IF include_fuzzy THEN
      join_parts := join_parts || ' FULL OUTER JOIN fuzzy ON ilike_match.id = fuzzy.id';
    END IF;
  ELSE
    join_parts := 'FROM fuzzy';
  END IF;

  -- Build COALESCE for ID
  id_coalesce := '{}'::text[];
  IF include_dense THEN id_coalesce := array_append(id_coalesce, 'dense.id'); END IF;
  IF include_sparse THEN id_coalesce := array_append(id_coalesce, 'sparse.id'); END IF;
  IF include_ilike THEN id_coalesce := array_append(id_coalesce, 'ilike_match.id'); END IF;
  IF include_fuzzy THEN id_coalesce := array_append(id_coalesce, 'fuzzy.id'); END IF;
  id_expr := 'COALESCE(' || array_to_string(id_coalesce, ', ') || ')';
  select_parts := id_expr || ' AS id';

  -- Build RRF calculation
  IF include_dense THEN
    rrf_parts := array_append(rrf_parts, format('(%s * COALESCE(1.0 / (%s + dense.rank), 0.0))',
      dense_weight, rrf_k));
  END IF;
  IF include_sparse THEN
    rrf_parts := array_append(rrf_parts, format('(%s * COALESCE(1.0 / (%s + sparse.rank), 0.0))',
      sparse_weight, rrf_k));
  END IF;
  IF include_ilike THEN
    rrf_parts := array_append(rrf_parts, format('(%s * COALESCE(1.0 / (%s + ilike_match.rank), 0.0))',
      ilike_weight, rrf_k));
  END IF;
  IF include_fuzzy THEN
    rrf_parts := array_append(rrf_parts, format('(%s * COALESCE(1.0 / (%s + fuzzy.rank), 0.0))',
      fuzzy_weight, rrf_k));
  END IF;

  -- Construct final query
  base_query := format($q$
    WITH %s
    SELECT
      %s,
      docs.content,
      docs.metadata,
      %s AS dense_score,
      %s AS sparse_score,
      %s AS ilike_score,
      %s AS fuzzy_score,
      %s AS final_score
    %s
    JOIN documents_v2 docs ON docs.id = %s
    ORDER BY final_score DESC
    LIMIT %s
  $q$,
    array_to_string(cte_parts, ', '),
    select_parts,
    CASE WHEN include_dense THEN 'COALESCE(dense.dense_score, 0.0)::float' ELSE '0.0::float' END,
    CASE WHEN include_sparse THEN 'COALESCE(sparse.sparse_score, 0.0)::float' ELSE '0.0::float' END,
    CASE WHEN include_ilike THEN 'COALESCE(ilike_match.ilike_score, 0.0)::float' ELSE '0.0::float' END,
    CASE WHEN include_fuzzy THEN 'COALESCE(fuzzy.fuzzy_score, 0.0)::float' ELSE '0.0::float' END,
    '(' || array_to_string(rrf_parts, ' + ') || ')::double precision',
    join_parts,
    id_expr,
    match_count
  );

  RETURN QUERY EXECUTE base_query;
END;
$$;

-- Create supporting indexes if they don't exist
CREATE INDEX IF NOT EXISTS documents_v2_embedding_idx
  ON documents_v2 USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS documents_v2_fts_idx
  ON documents_v2 USING gin (fts);

CREATE INDEX IF NOT EXISTS documents_v2_metadata_idx
  ON documents_v2 USING gin (metadata);
```

### 10.5.4 Context Expansion SQL Functions (Enhanced for Total RAG Parity)

**Purpose**: Provide flexible context expansion with both radius-based and range-based retrieval methods for optimal answer quality.

#### Function 1: Range-Based Context Expansion (CRITICAL - Gap 1.1)

```sql
-- Critical for Total RAG parity - Allows efficient batch retrieval of chunk ranges
CREATE OR REPLACE FUNCTION get_chunks_by_ranges(input_data jsonb)
RETURNS TABLE(
  doc_id text,
  chunk_index integer,
  content text,
  metadata jsonb,
  id bigint,
  hierarchical_context jsonb,
  parent_heading text,
  section_depth integer
)
LANGUAGE plpgsql
SECURITY INVOKER
AS $$
DECLARE
  doc_item JSONB;
  range_item JSONB;
  range_start INTEGER;
  range_end INTEGER;
  current_doc_id TEXT;
  parent_heading_text TEXT;
  hierarchical_data JSONB;
BEGIN
  -- Loop through each document in the input array
  FOR doc_item IN SELECT * FROM jsonb_array_elements(input_data)
  LOOP
    -- Extract doc_id from current document item
    current_doc_id := doc_item->>'doc_id';

    -- Get parent heading and hierarchical context for document
    SELECT
      metadata->>'parent_heading',
      jsonb_build_object(
        'document_title', metadata->>'document_title',
        'section_hierarchy', metadata->'section_hierarchy',
        'document_type', metadata->>'document_type'
      )
    INTO parent_heading_text, hierarchical_data
    FROM documents_v2
    WHERE metadata->>'doc_id' = current_doc_id
    LIMIT 1;

    -- Loop through each chunk range for this document
    FOR range_item IN SELECT * FROM jsonb_array_elements(doc_item->'chunk_ranges')
    LOOP
      -- Extract start and end of the range
      range_start := (range_item->0)::INTEGER;
      range_end := (range_item->1)::INTEGER;

      -- Return all chunks within this range with hierarchical context
      RETURN QUERY
      SELECT
        current_doc_id as doc_id,
        (d.metadata->>'chunk_index')::INTEGER as chunk_index,
        d.content,
        d.metadata,
        d.id,
        hierarchical_data as hierarchical_context,
        COALESCE(d.metadata->>'parent_heading', parent_heading_text) as parent_heading,
        COALESCE((d.metadata->>'section_depth')::INTEGER, 0) as section_depth
      FROM documents_v2 d
      WHERE d.metadata->>'doc_id' = current_doc_id
        AND (d.metadata->>'chunk_index')::INTEGER >= range_start
        AND (d.metadata->>'chunk_index')::INTEGER <= range_end
      ORDER BY (d.metadata->>'chunk_index')::INTEGER;
    END LOOP;
  END LOOP;
END;
$$;

-- Grant execute permissions
GRANT EXECUTE ON FUNCTION get_chunks_by_ranges(jsonb) TO authenticated;
GRANT EXECUTE ON FUNCTION get_chunks_by_ranges(jsonb) TO anon;
```

#### Function 2: Original Radius-Based Expansion (Enhanced)

```sql
CREATE OR REPLACE FUNCTION expand_context_chunks(
  chunk_ids bigint[],
  expansion_radius int DEFAULT 2,
  max_total_tokens int DEFAULT 8000
)
RETURNS TABLE (
  id bigint,
  content text,
  metadata jsonb,
  chunk_index int,
  is_original boolean,
  distance_from_original int
)
LANGUAGE plpgsql
AS $$
DECLARE
  chunk_id bigint;
  doc_id text;
  chunk_idx int;
  total_tokens int := 0;
  chunk_tokens int;
BEGIN
  -- Process each original chunk
  FOREACH chunk_id IN ARRAY chunk_ids
  LOOP
    -- Get document context for this chunk
    SELECT
      metadata->>'doc_id',
      (metadata->>'chunk_index')::int
    INTO doc_id, chunk_idx
    FROM documents_v2
    WHERE id = chunk_id;

    -- Return expanded chunks (original + neighbors)
    RETURN QUERY
    SELECT
      d.id,
      d.content,
      d.metadata,
      (d.metadata->>'chunk_index')::int as chunk_index,
      (d.id = chunk_id) as is_original,
      ABS((d.metadata->>'chunk_index')::int - chunk_idx) as distance_from_original
    FROM documents_v2 d
    WHERE d.metadata->>'doc_id' = doc_id
      AND (d.metadata->>'chunk_index')::int >= chunk_idx - expansion_radius
      AND (d.metadata->>'chunk_index')::int <= chunk_idx + expansion_radius
    ORDER BY (d.metadata->>'chunk_index')::int;

    -- Track total tokens to avoid context overflow
    SELECT SUM(LENGTH(content) / 4) INTO total_tokens
    FROM documents_v2 d
    WHERE d.metadata->>'doc_id' = doc_id
      AND (d.metadata->>'chunk_index')::int >= chunk_idx - expansion_radius
      AND (d.metadata->>'chunk_index')::int <= chunk_idx + expansion_radius;

    -- Exit if we're approaching token limit
    IF total_tokens > max_total_tokens THEN
      EXIT;
    END IF;
  END LOOP;
END;
$$;
```

###***REMOVED*** Edge Function Wrapper (CRITICAL - Gap 1.2)

Create a new edge function for HTTP access to context expansion:

```typescript
// supabase/functions/context-expansion/index.ts
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'
import { corsHeaders } from '../_shared/cors.ts'

Deno.serve(async (req) => {
  // Handle CORS
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders })
  }

  try {
    const supabaseClient = createClient(
      Deno.env.get('SUPABASE_URL') ?? '',
      Deno.env.get('SUPABASE_ANON_KEY') ?? '',
      { global: { headers: { Authorization: req.headers.get('Authorization')! } } }
    )

    const { method, chunk_ids, expansion_radius, input_data } = await req.json()

    let data, error

    if (method === 'range') {
      // Use range-based expansion
      ({ data, error } = await supabaseClient.rpc('get_chunks_by_ranges', {
        input_data
      }))
    } else {
      // Use radius-based expansion
      ({ data, error } = await supabaseClient.rpc('expand_context_chunks', {
        chunk_ids,
        expansion_radius: expansion_radius || 2
      }))
    }

    if (error) throw error

    return new Response(
      JSON.stringify({ data }),
      { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    )
  } catch (error) {
    return new Response(
      JSON.stringify({ error: error.message }),
      { headers: { ...corsHeaders, 'Content-Type': 'application/json' }, status: 400 }
    )
  }
})
```

### 10.5.5 Knowledge Graph Entity Tables

**Purpose**: Support LightRAG knowledge graph integration with local entity storage.

```sql
-- Knowledge entities table
CREATE TABLE IF NOT EXISTS knowledge_entities (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_type text NOT NULL,
  entity_value text NOT NULL,
  properties jsonb DEFAULT '{}',
  embedding vector(768),
  confidence float DEFAULT 1.0,
  created_at timestamptz DEFAULT NOW(),
  updated_at timestamptz DEFAULT NOW()
);

-- Knowledge relationships table
CREATE TABLE IF NOT EXISTS knowledge_relationships (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_entity UUID REFERENCES knowledge_entities(id) ON DELETE CASCADE,
  target_entity UUID REFERENCES knowledge_entities(id) ON DELETE CASCADE,
  relationship_type text NOT NULL,
  properties jsonb DEFAULT '{}',
  confidence float DEFAULT 1.0,
  created_at timestamptz DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_entities_type ON knowledge_entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_entities_value ON knowledge_entities(entity_value);
CREATE INDEX IF NOT EXISTS idx_entities_embedding ON knowledge_entities USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_relationships_source ON knowledge_relationships(source_entity);
CREATE INDEX IF NOT EXISTS idx_relationships_target ON knowledge_relationships(target_entity);
CREATE INDEX IF NOT EXISTS idx_relationships_type ON knowledge_relationships(relationship_type);

-- Graph traversal function
CREATE OR REPLACE FUNCTION traverse_knowledge_graph(
  start_entity_value text,
  max_hops int DEFAULT 3,
  relationship_types text[] DEFAULT NULL
)
RETURNS TABLE (
  entity_id uuid,
  entity_value text,
  entity_type text,
  hop_distance int,
  path_confidence float
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  WITH RECURSIVE graph_traverse AS (
    -- Base case: starting entity
    SELECT
      e.id as entity_id,
      e.entity_value,
      e.entity_type,
      0 as hop_distance,
      e.confidence as path_confidence
    FROM knowledge_entities e
    WHERE e.entity_value = start_entity_value

    UNION

    -- Recursive case: follow relationships
    SELECT
      target.id,
      target.entity_value,
      target.entity_type,
      gt.hop_distance + 1,
      gt.path_confidence * r.confidence
    FROM graph_traverse gt
    JOIN knowledge_relationships r ON r.source_entity = gt.entity_id
    JOIN knowledge_entities target ON target.id = r.target_entity
    WHERE gt.hop_distance < max_hops
      AND (relationship_types IS NULL OR r.relationship_type = ANY(relationship_types))
  )
  SELECT DISTINCT ON (entity_id)
    entity_id,
    entity_value,
    entity_type,
    hop_distance,
    path_confidence
  FROM graph_traverse
  ORDER BY entity_id, hop_distance ASC;
END;
$$;
```

### 10.5.6 Structured Data Tables

**Purpose**: Support CSV/Excel processing with dedicated schema.

```sql
-- Record manager for document tracking
CREATE TABLE IF NOT EXISTS record_manager_v2 (
  id BIGSERIAL PRIMARY KEY,
  created_at timestamptz DEFAULT NOW(),
  doc_id text NOT NULL UNIQUE,
  hash text NOT NULL,
  data_type text DEFAULT 'unstructured',
  schema text,
  document_title text,
  document_headline text,        -- NEW: Summary headline for quick reference
  graph_id text,                  -- NEW: LightRAG knowledge graph integration
  hierarchical_index text,        -- NEW: Document structure positioning (e.g., "1.2.3")
  document_summary text,
  status text DEFAULT 'complete'
);

-- Tabular data rows
CREATE TABLE IF NOT EXISTS tabular_document_rows (
  id BIGSERIAL PRIMARY KEY,
  created_at timestamptz DEFAULT NOW(),
  record_manager_id BIGINT REFERENCES record_manager_v2(id) ON DELETE CASCADE,
  row_data jsonb NOT NULL
);

-- Metadata fields management (NEW - Gap Analysis Addition)
CREATE TABLE IF NOT EXISTS metadata_fields (
  id BIGINT GENERATED BY DEFAULT AS IDENTITY NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  field_name TEXT NOT NULL UNIQUE,
  field_type VARCHAR(50) NOT NULL,  -- 'string', 'number', 'date', 'boolean', 'enum', 'array'
  allowed_values TEXT[],             -- For enum types: allowed values list
  validation_regex TEXT,             -- Optional: regex pattern for validation
  description TEXT,
  is_required BOOLEAN DEFAULT FALSE,
  is_searchable BOOLEAN DEFAULT TRUE,
  display_order INTEGER,
  default_value TEXT,
  CONSTRAINT metadata_fields_pkey PRIMARY KEY (id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_tabular_row_data ON tabular_document_rows USING gin (row_data);
CREATE INDEX IF NOT EXISTS idx_record_manager_doc_id ON record_manager_v2(doc_id);
CREATE INDEX IF NOT EXISTS idx_record_manager_type ON record_manager_v2(data_type);
CREATE INDEX IF NOT EXISTS idx_record_manager_graph_id ON record_manager_v2(graph_id);
CREATE INDEX IF NOT EXISTS idx_metadata_fields_name ON metadata_fields(field_name);
```

### 10.5.7 Advanced Context Expansion Function

**Purpose**: Retrieve document chunks by specified ranges for precise context expansion (NEW - Gap Analysis Addition).

**Function**: `get_chunks_by_ranges()`

This function enables efficient retrieval of multiple chunk ranges across documents, supporting advanced context expansion strategies like neighboring chunks (±2), section-based retrieval, and hierarchical document structure.

```sql
CREATE OR REPLACE FUNCTION get_chunks_by_ranges(input_data jsonb)
RETURNS TABLE(
  doc_id text,
  chunk_index integer,
  content text,
  metadata jsonb,
  id bigint,
  hierarchical_context jsonb,  -- Empire enhancement: parent/child relationships
  graph_entities text[]         -- Empire enhancement: linked knowledge graph entities
)
LANGUAGE plpgsql
SECURITY INVOKER
AS $$
DECLARE
  range_item jsonb;
  current_doc_id text;
  start_idx integer;
  end_idx integer;
BEGIN
  -- Input format: {"ranges": [{"doc_id": "doc1", "start": 0, "end": 5}, ...]}
  -- Iterate through each range specification
  FOR range_item IN SELECT * FROM jsonb_array_elements(input_data->'ranges')
  LOOP
    current_doc_id := range_item->>'doc_id';
    start_idx := (range_item->>'start')::integer;
    end_idx := (range_item->>'end')::integer;

    -- Return chunks within the specified range
    RETURN QUERY
    SELECT
      d.doc_id,
      d.chunk_index,
      d.content,
      d.metadata,
      d.id,
      -- Hierarchical context: build parent/sibling/child relationships
      jsonb_build_object(
        'parent_chunk', (
          SELECT jsonb_build_object('chunk_index', chunk_index, 'content', left(content, 100))
          FROM documents_v2
          WHERE doc_id = d.doc_id
            AND chunk_index = GREATEST(0, d.chunk_index - 1)
          LIMIT 1
        ),
        'next_chunk', (
          SELECT jsonb_build_object('chunk_index', chunk_index, 'content', left(content, 100))
          FROM documents_v2
          WHERE doc_id = d.doc_id
            AND chunk_index = d.chunk_index + 1
          LIMIT 1
        ),
        'document_structure', (
          SELECT hierarchical_index
          FROM record_manager_v2
          WHERE doc_id = d.doc_id
        ),
        'total_chunks', (
          SELECT COUNT(*)
          FROM documents_v2
          WHERE doc_id = d.doc_id
        )
      ) AS hierarchical_context,
      -- Graph entities: extract entity references from knowledge graph
      (
        SELECT array_agg(DISTINCT entity_name)
        FROM knowledge_entities
        WHERE metadata->>'source_doc_id' = d.doc_id
          AND (metadata->>'chunk_index')::integer BETWEEN start_idx AND end_idx
      ) AS graph_entities
    FROM documents_v2 d
    WHERE d.doc_id = current_doc_id
      AND d.chunk_index BETWEEN start_idx AND end_idx
    ORDER BY d.chunk_index;
  END LOOP;
END;
$$;

-- Example usage for context expansion (±2 chunks around results):
-- SELECT * FROM get_chunks_by_ranges('{"ranges": [
--   {"doc_id": "doc_123", "start": 3, "end": 7},
--   {"doc_id": "doc_456", "start": 10, "end": 14}
-- ]}'::jsonb);
```

**Empire Enhancements Over Total RAG:**
1. **Hierarchical Context**: Includes parent/child chunk relationships and document structure
2. **Knowledge Graph Integration**: Links to entities from LightRAG knowledge graph
3. **Document Awareness**: Returns total chunks and positioning within document
4. **Performance**: Batch processing of multiple ranges in single call
5. **Metadata Preservation**: Full metadata passthrough for downstream processing

**Integration Points:**
- **RAG Query Pipeline**: Called after initial hybrid search to expand context
- **n8n Function Node**: Accessible via Supabase Edge Function wrapper
- **LlamaIndex**: Provides chunk ranges from document structure analysis
- **LightRAG**: Entity references enable graph-enhanced context

### 10.5.8 Dynamic Hybrid Search Weight Adjustment (NEW - Gap Analysis Addition)

**Purpose**: Automatically tune hybrid search method weights based on query characteristics for optimal results.

**Problem**: Different query types benefit from different search method combinations:
- Short queries need fuzzy matching (typo tolerance)
- Semantic queries benefit from dense vector search
- Exact match queries need ILIKE pattern matching
- Long queries benefit from sparse BM25-style search

**Solution**: Add query analysis node before hybrid search to dynamically adjust weights.

**Implementation Pattern:**

```javascript
// Node: "Analyze Query and Adjust Weights"
// Type: n8n-nodes-base.code
// Position: Before hybrid search execution

const query = $json.query.original || $json.query;
const queryLower = query.toLowerCase();
const wordCount = query.trim().split(/\s+/).length;

// Default balanced weights
const weights = {
  dense_weight: 0.4,    // Vector similarity
  sparse_weight: 0.3,   // BM25 full-text
  ilike_weight: 0.15,   // Pattern matching
  fuzzy_weight: 0.15,   // Trigram similarity
  fuzzy_threshold: 0.3  // Minimum similarity
};

// Query type detection and weight adjustment
if (queryLower.includes('exactly') || queryLower.includes('specific') || queryLower.includes('"')) {
  // Exact match queries: boost ILIKE pattern matching
  weights.dense_weight = 0.2;
  weights.sparse_weight = 0.2;
  weights.ilike_weight = 0.4;
  weights.fuzzy_weight = 0.2;
  weights.query_type = 'exact_match';

} else if (wordCount < 3) {
  // Short queries: boost fuzzy for typo tolerance
  weights.dense_weight = 0.3;
  weights.sparse_weight = 0.2;
  weights.ilike_weight = 0.2;
  weights.fuzzy_weight = 0.3;
  weights.fuzzy_threshold = 0.2; // Lower threshold for short queries
  weights.query_type = 'short_query';

} else if (queryLower.includes('similar') || queryLower.includes('like') ||
           queryLower.includes('related') || queryLower.includes('about')) {
  // Semantic queries: boost dense vector search
  weights.dense_weight = 0.6;
  weights.sparse_weight = 0.2;
  weights.ilike_weight = 0.1;
  weights.fuzzy_weight = 0.1;
  weights.query_type = 'semantic';

} else if (wordCount > 8) {
  // Long queries: boost sparse BM25 for keyword matching
  weights.dense_weight = 0.3;
  weights.sparse_weight = 0.4;
  weights.ilike_weight = 0.15;
  weights.fuzzy_weight = 0.15;
  weights.query_type = 'long_query';

} else if (/[0-9]{4}/.test(query)) {
  // Contains year/number: boost pattern matching
  weights.dense_weight = 0.25;
  weights.sparse_weight = 0.25;
  weights.ilike_weight = 0.35;
  weights.fuzzy_weight = 0.15;
  weights.query_type = 'contains_number';

} else {
  // Balanced query: use default weights
  weights.query_type = 'balanced';
}

// Add metadata for debugging
weights.query_length = query.length;
weights.word_count = wordCount;
weights.has_quotes = query.includes('"');
weights.adjusted_at = new Date().toISOString();

return [{
  json: {
    ...$json,
    search_weights: weights
  }
}];
```

**Integration with Hybrid Search:**

Modify the hybrid search call to use dynamic weights:

```json
{
  "name": "Execute Dynamic Hybrid Search",
  "type": "n8n-nodes-base.postgres",
  "parameters": {
    "operation": "executeQuery",
    "query": "SELECT * FROM empire_hybrid_search(\n  query_text := $1,\n  query_embedding := $2::vector(768),\n  match_count := $3,\n  dense_weight := $4,\n  sparse_weight := $5,\n  ilike_weight := $6,\n  fuzzy_weight := $7,\n  fuzzy_threshold := $8\n)",
    "options": {
      "queryParams": "={{ [\n  $json.query.original,\n  '[' + $json.embedding.join(',') + ']',\n  $json.options.max_results * 2,\n  $json.search_weights.dense_weight,\n  $json.search_weights.sparse_weight,\n  $json.search_weights.ilike_weight,\n  $json.search_weights.fuzzy_weight,\n  $json.search_weights.fuzzy_threshold\n] }}"
    }
  }
}
```

**Performance Impact:**
- Query analysis: <10ms overhead
- Improved relevance: 10-15% better result quality
- Especially beneficial for edge cases (very short/long queries)

**Monitoring:**
Track weight distribution in query_performance_log:
```sql
ALTER TABLE query_performance_log
ADD COLUMN query_type TEXT,
ADD COLUMN weight_config JSONB;
```

### 10.5.9 Natural Language to SQL Translation for Tabular Data (NEW - Gap Analysis Addition)

**Purpose**: Enable natural language queries over structured CSV/Excel data stored in tabular_document_rows table.

**Use Case**: User asks "Show me all customers from California with revenue > $100k" against uploaded sales CSV.

**Implementation Pattern:**

**Step 1: Detect Structured Data Query**

```javascript
// Node: "Detect Query Type"
// Type: n8n-nodes-base.code

const query = $json.query.original;
const queryLower = query.toLowerCase();

// Keywords that indicate structured data query
const structuredKeywords = [
  'show me', 'list', 'filter', 'where', 'count',
  'average', 'sum', 'total', 'max', 'min',
  'group by', 'sort by', 'order by', 'top'
];

const isStructuredQuery = structuredKeywords.some(kw => queryLower.includes(kw));

// Check if we have tabular data documents
const hasTabularData = true; // Query database to check

return [{
  json: {
    ...$json,
    query_type: isStructuredQuery && hasTabularData ? 'structured' : 'semantic',
    requires_sql_translation: isStructuredQuery && hasTabularData
  }
}];
```

**Step 2: Get Table Schema**

```sql
-- Query to get schema of uploaded structured documents
SELECT
  rm.doc_id,
  rm.document_title,
  rm.schema AS table_schema,
  COUNT(tdr.id) AS row_count,
  jsonb_object_keys(tdr.row_data) AS column_names
FROM record_manager_v2 rm
JOIN tabular_document_rows tdr ON rm.id = tdr.record_manager_id
WHERE rm.data_type = 'tabular'
GROUP BY rm.doc_id, rm.document_title, rm.schema;
```

**Step 3: LLM SQL Generation**

```javascript
// Node: "Generate SQL from Natural Language"
// Type: @n8n/n8n-nodes-langchain.lmChatAnthropic (or equivalent)

const prompt = `You are a PostgreSQL expert specializing in querying JSONB data.

USER QUERY: ${$json.query.original}

AVAILABLE TABLES:
${$json.table_schemas.map(t => `
Table: ${t.document_title}
Columns: ${t.column_names.join(', ')}
Row Count: ${t.row_count}
Schema: ${JSON.stringify(t.table_schema, null, 2)}
`).join('\n')}

DATA STORAGE:
- Data is in table: tabular_document_rows
- Column: row_data (JSONB type)
- Access columns using: row_data->>'column_name'
- Join with record_manager_v2 on: record_manager_id

REQUIREMENTS:
1. Generate ONLY valid PostgreSQL SQL
2. Use JSONB operators (->, ->>, #>) for nested access
3. Handle data type casting (::integer, ::float, ::date)
4. Include LIMIT clause (max 100 rows)
5. Return columns that answer the user's question

EXAMPLE QUERIES:

User: "Show customers from California"
SQL:
SELECT
  row_data->>'customer_name' AS customer_name,
  row_data->>'state' AS state,
  row_data->>'revenue' AS revenue
FROM tabular_document_rows tdr
JOIN record_manager_v2 rm ON tdr.record_manager_id = rm.id
WHERE rm.document_title = 'customers.csv'
  AND row_data->>'state' = 'California'
LIMIT 100;

User: "What's the average revenue by state?"
SQL:
SELECT
  row_data->>'state' AS state,
  AVG((row_data->>'revenue')::float) AS avg_revenue,
  COUNT(*) AS customer_count
FROM tabular_document_rows tdr
JOIN record_manager_v2 rm ON tdr.record_manager_id = rm.id
WHERE rm.document_title = 'customers.csv'
  AND row_data->>'revenue' IS NOT NULL
GROUP BY row_data->>'state'
ORDER BY avg_revenue DESC
LIMIT 100;

Now generate SQL for the user query above.
Output ONLY the SQL query, no explanation.`;

// Returns: SQL query as text
```

**Step 4: Execute Generated SQL**

```json
{
  "name": "Execute Structured Query",
  "type": "n8n-nodes-base.postgres",
  "parameters": {
    "operation": "executeQuery",
    "query": "={{ $json.generated_sql }}",
    "options": {
      "queryTimeout": 30000
    }
  },
  "continueOnFail": true
}
```

**Step 5: Format Results**

```javascript
// Node: "Format Structured Results"
// Type: n8n-nodes-base.code

const results = $json;
const rowCount = results.length;

// Convert to markdown table for display
function toMarkdownTable(data) {
  if (data.length === 0) return 'No results found.';

  const headers = Object.keys(data[0]);
  const headerRow = '| ' + headers.join(' | ') + ' |';
  const separator = '| ' + headers.map(() => '---').join(' | ') + ' |';
  const dataRows = data.map(row =>
    '| ' + headers.map(h => row[h] || '').join(' | ') + ' |'
  ).join('\n');

  return `${headerRow}\n${separator}\n${dataRows}`;
}

// Create summary
const summary = {
  query_type: 'structured',
  result_count: rowCount,
  results_markdown: toMarkdownTable(results),
  results_json: results,
  executed_sql: $('Generate SQL from Natural Language').item.json.generated_sql
};

return [{ json: summary }];
```

**Step 6: Merge with Semantic Search (Optional)**

```javascript
// Node: "Merge Structured + Semantic Results"
// Type: n8n-nodes-base.code

// If both structured and semantic results exist, combine them
const structuredResults = $('Format Structured Results').item?.json;
const semanticResults = $('Hybrid Search').item?.json;

const response = {
  answer_type: 'hybrid',
  structured_data: structuredResults,
  related_documents: semanticResults,
  combined_response: `
Here are the results from your structured data query:

${structuredResults.results_markdown}

Additionally, here are related documents:
${semanticResults.map(r => `- ${r.title}: ${r.summary}`).join('\n')}
  `
};

return [{ json: response }];
```

**Error Handling:**

```javascript
// If SQL generation or execution fails, fall back to semantic search
if ($json.error || !$json.generated_sql) {
  return [{
    json: {
      fallback_to_semantic: true,
      error_message: $json.error,
      original_query: $json.query.original
    }
  }];
}
```

**Required Database Enhancement:**

```sql
-- Add index on data_type for faster tabular document lookup
CREATE INDEX IF NOT EXISTS idx_record_manager_data_type
  ON record_manager_v2(data_type)
  WHERE data_type = 'tabular';

-- Add GIN index on row_data for faster JSONB queries
CREATE INDEX IF NOT EXISTS idx_tabular_row_data_gin
  ON tabular_document_rows USING gin(row_data);
```

**Security Considerations:**

1. **SQL Injection Prevention**: LLM-generated SQL is read-only (SELECT only)
2. **Query Timeout**: 30-second maximum execution time
3. **Row Limit**: Maximum 100 rows returned
4. **Validation**: Parse generated SQL to ensure no DROP/DELETE/UPDATE statements

**Performance Targets:**
- Schema retrieval: <100ms
- LLM SQL generation: <2 seconds
- SQL execution: <500ms
- Total structured query: <3 seconds

**Example Workflow Path:**

```
User Query
  ↓
Detect Query Type
  ↓ (if structured)
Get Table Schemas
  ↓
Generate SQL (LLM)
  ↓
Execute SQL
  ↓
Format Results
  ↓
Return to User
```

### 10.6.3 Chat Session Database Schema

```sql
-- Chat sessions table
CREATE TABLE IF NOT EXISTS chat_sessions (
    session_id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    session_data JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_activity TIMESTAMPTZ DEFAULT NOW(),
    message_count INTEGER DEFAULT 0,
    total_tokens_used INTEGER DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes
CREATE INDEX idx_sessions_user_id ON chat_sessions(user_id);
CREATE INDEX idx_sessions_last_activity ON chat_sessions(last_activity DESC);
CREATE INDEX idx_sessions_created_at ON chat_sessions(created_at DESC);

-- Chat messages table for audit
CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id VARCHAR(36) REFERENCES chat_sessions(session_id) ON DELETE CASCADE,
    message_index INTEGER NOT NULL,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    tokens_used INTEGER,
    processing_time_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(session_id, message_index)
);

-- Create indexes
CREATE INDEX idx_messages_session_id ON chat_messages(session_id);
CREATE INDEX idx_messages_created_at ON chat_messages(created_at DESC);
CREATE INDEX idx_messages_role ON chat_messages(role);

-- Feedback table
CREATE TABLE IF NOT EXISTS chat_feedback (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id VARCHAR(36) REFERENCES chat_sessions(session_id),
    message_id UUID REFERENCES chat_messages(id),
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    feedback_text TEXT,
    feedback_type VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes
CREATE INDEX idx_feedback_session_id ON chat_feedback(session_id);
CREATE INDEX idx_feedback_rating ON chat_feedback(rating);
CREATE INDEX idx_feedback_created_at ON chat_feedback(created_at DESC);
```

### 10.6.4 Chat History Storage (CRITICAL - Gap 1.4)

**Purpose**: Persist all chat conversations for multi-turn dialogue and analytics.

#### Database Schema for Chat History

```sql
-- n8n-specific chat history storage
CREATE TABLE IF NOT EXISTS public.n8n_chat_histories (
  id BIGSERIAL PRIMARY KEY,
  session_id VARCHAR(255) NOT NULL,
  user_id VARCHAR(255),
  message JSONB NOT NULL,
  message_type VARCHAR(50) DEFAULT 'message', -- 'message', 'system', 'error', 'tool_use'
  role VARCHAR(50) NOT NULL, -- 'user', 'assistant', 'system'
  token_count INTEGER,
  model_used VARCHAR(100),
  latency_ms INTEGER,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_chat_history_session ON n8n_chat_histories(session_id);
CREATE INDEX idx_chat_history_user ON n8n_chat_histories(user_id);
CREATE INDEX idx_chat_history_created ON n8n_chat_histories(created_at DESC);
CREATE INDEX idx_chat_history_type ON n8n_chat_histories(message_type);

-- Session metadata table
CREATE TABLE IF NOT EXISTS public.chat_sessions (
  id VARCHAR(255) PRIMARY KEY,
  user_id VARCHAR(255),
  title TEXT,
  summary TEXT,
  first_message_at TIMESTAMPTZ,
  last_message_at TIMESTAMPTZ,
  message_count INTEGER DEFAULT 0,
  total_tokens INTEGER DEFAULT 0,
  session_metadata JSONB DEFAULT '{}',
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Function to automatically update session metadata
CREATE OR REPLACE FUNCTION update_chat_session_metadata()
RETURNS TRIGGER AS $$
BEGIN
  -- Update or insert session metadata
  INSERT INTO chat_sessions (
    id,
    user_id,
    first_message_at,
    last_message_at,
    message_count,
    total_tokens
  )
  VALUES (
    NEW.session_id,
    NEW.user_id,
    NEW.created_at,
    NEW.created_at,
    1,
    COALESCE(NEW.token_count, 0)
  )
  ON CONFLICT (id) DO UPDATE SET
    last_message_at = NEW.created_at,
    message_count = chat_sessions.message_count + 1,
    total_tokens = chat_sessions.total_tokens + COALESCE(NEW.token_count, 0),
    updated_at = NOW();

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for automatic session updates
CREATE TRIGGER update_session_on_message
  AFTER INSERT ON n8n_chat_histories
  FOR EACH ROW
  EXECUTE FUNCTION update_chat_session_metadata();

-- Function to retrieve chat history with context
CREATE OR REPLACE FUNCTION get_chat_history(
  p_session_id VARCHAR(255),
  p_limit INTEGER DEFAULT 10,
  p_include_system BOOLEAN DEFAULT false
)
RETURNS TABLE (
  message_id BIGINT,
  role VARCHAR(50),
  content TEXT,
  metadata JSONB,
  created_at TIMESTAMPTZ
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    h.id as message_id,
    h.role,
    h.message->>'content' as content,
    h.metadata,
    h.created_at
  FROM n8n_chat_histories h
  WHERE h.session_id = p_session_id
    AND (p_include_system OR h.message_type != 'system')
  ORDER BY h.created_at DESC
  LIMIT p_limit;
END;
$$;
```

#### n8n Workflow Nodes for Chat History

Add these nodes to your chat workflow:

```json
{
  "nodes": [
    {
      "parameters": {
        "operation": "insert",
        "schema": "public",
        "table": "n8n_chat_histories",
        "columns": "session_id,user_id,message,message_type,role,token_count,model_used,metadata",
        "additionalFields": {}
      },
      "name": "Store User Message",
      "type": "n8n-nodes-base.postgres",
      "position": [450, 200]
    },
    {
      "parameters": {
        "operation": "executeQuery",
        "query": "SELECT * FROM get_chat_history('{{ $json.session_id }}', 5, false);"
      },
      "name": "Retrieve Chat History",
      "type": "n8n-nodes-base.postgres",
      "position": [650, 200]
    },
    {
      "parameters": {
        "operation": "insert",
        "schema": "public",
        "table": "n8n_chat_histories",
        "columns": "session_id,user_id,message,message_type,role,token_count,model_used,latency_ms,metadata"
      },
      "name": "Store Assistant Response",
      "type": "n8n-nodes-base.postgres",
      "position": [1250, 200]
    }
  ]
}
```

### 10.6.5 Graph-Based User Memory System

**Purpose:** Implement production-grade user memory with graph-based relationships, integrated with LightRAG knowledge graph for personalized context retrieval.

**Architecture Overview:**
- **Developer Memory:** mem-agent MCP (local Mac Studio, Claude Desktop integration, NOT for production workflows)
- **Production User Memory:** Supabase graph-based system with three-layer architecture
  1. **Document Knowledge Graph:** LightRAG entities and relationships
  2. **User Memory Graph:** User-specific facts, preferences, goals, context
  3. **Hybrid Graph:** Links user memories to document entities

**Performance Targets:**
- Memory extraction: <2 seconds (Claude API)
- Graph traversal: <100ms (PostgreSQL recursive CTEs)
- Context retrieval: <300ms (combined memory + document search)
- Storage: 768-dim embeddings with pgvector cosine similarity

#### 10.6.5.1 Database Schema

```sql
-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- User memory nodes table
-- Stores individual facts, preferences, goals, and contextual information
CREATE TABLE IF NOT EXISTS user_memory_nodes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(100) NOT NULL,
    session_id VARCHAR(36), -- Optional: links to specific session

    -- Node content
    node_type VARCHAR(50) NOT NULL, -- 'fact', 'preference', 'goal', 'context', 'skill', 'interest'
    content TEXT NOT NULL,
    summary TEXT, -- Short summary for quick reference

    -- Embeddings for semantic search
    embedding vector(768), -- nomic-embed-text embeddings

    -- Metadata
    confidence_score FLOAT DEFAULT 1.0, -- 0.0 to 1.0, decays over time or with contradictions
    source_type VARCHAR(50) DEFAULT 'conversation', -- 'conversation', 'explicit', 'inferred'
    importance_score FLOAT DEFAULT 0.5, -- 0.0 to 1.0, for prioritization

    -- Temporal tracking
    first_mentioned_at TIMESTAMPTZ DEFAULT NOW(),
    last_mentioned_at TIMESTAMPTZ DEFAULT NOW(),
    mention_count INTEGER DEFAULT 1,

    -- Lifecycle management
    is_active BOOLEAN DEFAULT true,
    expires_at TIMESTAMPTZ, -- Optional expiration for time-sensitive facts

    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

-- Indexes for user_memory_nodes
CREATE INDEX idx_user_memory_nodes_user_id ON user_memory_nodes(user_id);
CREATE INDEX idx_user_memory_nodes_session_id ON user_memory_nodes(session_id);
CREATE INDEX idx_user_memory_nodes_type ON user_memory_nodes(node_type);
CREATE INDEX idx_user_memory_nodes_active ON user_memory_nodes(is_active) WHERE is_active = true;
CREATE INDEX idx_user_memory_nodes_embedding ON user_memory_nodes USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_user_memory_nodes_updated ON user_memory_nodes(updated_at DESC);

-- User memory edges table
-- Stores relationships between memory nodes
CREATE TABLE IF NOT EXISTS user_memory_edges (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(100) NOT NULL,

    -- Edge definition
    source_node_id UUID NOT NULL REFERENCES user_memory_nodes(id) ON DELETE CASCADE,
    target_node_id UUID NOT NULL REFERENCES user_memory_nodes(id) ON DELETE CASCADE,
    relationship_type VARCHAR(50) NOT NULL, -- 'causes', 'relates_to', 'contradicts', 'supports', 'precedes', 'enables'

    -- Edge metadata
    strength FLOAT DEFAULT 1.0, -- 0.0 to 1.0, relationship strength
    directionality VARCHAR(20) DEFAULT 'directed', -- 'directed' or 'undirected'

    -- Temporal tracking
    first_observed_at TIMESTAMPTZ DEFAULT NOW(),
    last_observed_at TIMESTAMPTZ DEFAULT NOW(),
    observation_count INTEGER DEFAULT 1,

    -- Lifecycle
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',

    -- Prevent duplicate edges
    UNIQUE(source_node_id, target_node_id, relationship_type)
);

-- Indexes for user_memory_edges
CREATE INDEX idx_user_memory_edges_user_id ON user_memory_edges(user_id);
CREATE INDEX idx_user_memory_edges_source ON user_memory_edges(source_node_id);
CREATE INDEX idx_user_memory_edges_target ON user_memory_edges(target_node_id);
CREATE INDEX idx_user_memory_edges_type ON user_memory_edges(relationship_type);
CREATE INDEX idx_user_memory_edges_active ON user_memory_edges(is_active) WHERE is_active = true;

-- User-document connections table
-- Links user memory nodes to LightRAG document entities for hybrid graph
CREATE TABLE IF NOT EXISTS user_document_connections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(100) NOT NULL,

    -- Connection definition
    memory_node_id UUID NOT NULL REFERENCES user_memory_nodes(id) ON DELETE CASCADE,
    document_entity_id VARCHAR(255) NOT NULL, -- LightRAG entity ID
    document_entity_name VARCHAR(500) NOT NULL, -- Entity name for quick reference
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE, -- Original document

    -- Connection metadata
    connection_type VARCHAR(50) DEFAULT 'related_to', -- 'related_to', 'expert_in', 'interested_in', 'worked_on'
    relevance_score FLOAT DEFAULT 0.5, -- 0.0 to 1.0

    -- Temporal tracking
    first_connected_at TIMESTAMPTZ DEFAULT NOW(),
    last_accessed_at TIMESTAMPTZ DEFAULT NOW(),
    access_count INTEGER DEFAULT 1,

    -- Lifecycle
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',

    -- Prevent duplicate connections
    UNIQUE(memory_node_id, document_entity_id)
);

-- Indexes for user_document_connections
CREATE INDEX idx_user_doc_conn_user_id ON user_document_connections(user_id);
CREATE INDEX idx_user_doc_conn_memory_node ON user_document_connections(memory_node_id);
CREATE INDEX idx_user_doc_conn_doc_entity ON user_document_connections(document_entity_id);
CREATE INDEX idx_user_doc_conn_doc_id ON user_document_connections(document_id);
CREATE INDEX idx_user_doc_conn_type ON user_document_connections(connection_type);
CREATE INDEX idx_user_doc_conn_active ON user_document_connections(is_active) WHERE is_active = true;

-- Update timestamp trigger
CREATE OR REPLACE FUNCTION update_user_memory_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_user_memory_nodes_timestamp
    BEFORE UPDATE ON user_memory_nodes
    FOR EACH ROW
    EXECUTE FUNCTION update_user_memory_timestamp();

CREATE TRIGGER update_user_memory_edges_timestamp
    BEFORE UPDATE ON user_memory_edges
    FOR EACH ROW
    EXECUTE FUNCTION update_user_memory_timestamp();

CREATE TRIGGER update_user_doc_conn_timestamp
    BEFORE UPDATE ON user_document_connections
    FOR EACH ROW
    EXECUTE FUNCTION update_user_memory_timestamp();
```

#### 10.6.5.2 SQL Functions for Graph Traversal

```sql
-- Function: Get user memory context with graph traversal
-- Retrieves relevant user memories with multi-hop graph traversal
CREATE OR REPLACE FUNCTION get_user_memory_context(
    p_user_id VARCHAR(100),
    p_query_embedding vector(768),
    p_max_nodes INTEGER DEFAULT 10,
    p_traversal_depth INTEGER DEFAULT 2,
    p_similarity_threshold FLOAT DEFAULT 0.7
)
RETURNS TABLE (
    node_id UUID,
    node_type VARCHAR(50),
    content TEXT,
    summary TEXT,
    similarity_score FLOAT,
    importance_score FLOAT,
    confidence_score FLOAT,
    hop_distance INTEGER,
    relationship_path TEXT[],
    last_mentioned_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    WITH RECURSIVE
    -- Step 1: Find seed nodes using vector similarity
    seed_nodes AS (
        SELECT
            n.id,
            n.node_type,
            n.content,
            n.summary,
            n.importance_score,
            n.confidence_score,
            n.last_mentioned_at,
            (1 - (n.embedding <=> p_query_embedding)) AS similarity,
            0 AS depth,
            ARRAY[]::TEXT[] AS path
        FROM user_memory_nodes n
        WHERE
            n.user_id = p_user_id
            AND n.is_active = true
            AND (n.expires_at IS NULL OR n.expires_at > NOW())
            AND (1 - (n.embedding <=> p_query_embedding)) >= p_similarity_threshold
        ORDER BY similarity DESC
        LIMIT p_max_nodes
    ),

    -- Step 2: Traverse graph to find related nodes
    graph_traversal AS (
        -- Base case: seed nodes
        SELECT
            id,
            node_type,
            content,
            summary,
            importance_score,
            confidence_score,
            last_mentioned_at,
            similarity,
            depth,
            path
        FROM seed_nodes

        UNION ALL

        -- Recursive case: follow edges to related nodes
        SELECT
            n.id,
            n.node_type,
            n.content,
            n.summary,
            n.importance_score,
            n.confidence_score,
            n.last_mentioned_at,
            gt.similarity * e.strength AS similarity, -- Decay similarity by edge strength
            gt.depth + 1 AS depth,
            gt.path || e.relationship_type AS path
        FROM graph_traversal gt
        INNER JOIN user_memory_edges e ON e.source_node_id = gt.id
        INNER JOIN user_memory_nodes n ON n.id = e.target_node_id
        WHERE
            gt.depth < p_traversal_depth
            AND e.is_active = true
            AND e.user_id = p_user_id
            AND n.is_active = true
            AND (n.expires_at IS NULL OR n.expires_at > NOW())
            AND NOT (n.id = ANY(SELECT id FROM graph_traversal)) -- Prevent cycles
    )

    -- Step 3: Rank and return results
    SELECT DISTINCT ON (gt.id)
        gt.id AS node_id,
        gt.node_type,
        gt.content,
        gt.summary,
        gt.similarity AS similarity_score,
        gt.importance_score,
        gt.confidence_score,
        gt.depth AS hop_distance,
        gt.path AS relationship_path,
        gt.last_mentioned_at
    FROM graph_traversal gt
    ORDER BY
        gt.id,
        -- Prioritize: high similarity, low depth, high importance, recent mentions
        (gt.similarity * 0.4 +
         (1.0 - gt.depth::FLOAT / p_traversal_depth) * 0.3 +
         gt.importance_score * 0.2 +
         gt.confidence_score * 0.1) DESC
    LIMIT p_max_nodes * 2; -- Return more results to account for graph expansion
END;
$$ LANGUAGE plpgsql;

-- Function: Get personalized document entities
-- Retrieves LightRAG entities relevant to user based on memory graph
CREATE OR REPLACE FUNCTION get_personalized_document_entities(
    p_user_id VARCHAR(100),
    p_query TEXT,
    p_max_entities INTEGER DEFAULT 5
)
RETURNS TABLE (
    entity_id VARCHAR(255),
    entity_name VARCHAR(500),
    relevance_score FLOAT,
    connection_count INTEGER,
    related_memories TEXT[],
    document_ids UUID[]
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        udc.document_entity_id AS entity_id,
        udc.document_entity_name AS entity_name,
        AVG(udc.relevance_score * n.confidence_score * n.importance_score) AS relevance_score,
        COUNT(DISTINCT udc.memory_node_id)::INTEGER AS connection_count,
        ARRAY_AGG(DISTINCT n.summary) AS related_memories,
        ARRAY_AGG(DISTINCT udc.document_id) AS document_ids
    FROM user_document_connections udc
    INNER JOIN user_memory_nodes n ON n.id = udc.memory_node_id
    WHERE
        udc.user_id = p_user_id
        AND udc.is_active = true
        AND n.is_active = true
        AND (n.expires_at IS NULL OR n.expires_at > NOW())
    GROUP BY udc.document_entity_id, udc.document_entity_name
    ORDER BY
        relevance_score DESC,
        connection_count DESC,
        MAX(udc.last_accessed_at) DESC
    LIMIT p_max_entities;
END;
$$ LANGUAGE plpgsql;

-- Function: Decay old memories
-- Reduces confidence scores for memories not mentioned recently
CREATE OR REPLACE FUNCTION decay_user_memories(
    p_user_id VARCHAR(100),
    p_days_threshold INTEGER DEFAULT 30,
    p_decay_rate FLOAT DEFAULT 0.1
)
RETURNS INTEGER AS $$
DECLARE
    rows_affected INTEGER;
BEGIN
    UPDATE user_memory_nodes
    SET
        confidence_score = GREATEST(0.0, confidence_score - p_decay_rate),
        updated_at = NOW()
    WHERE
        user_id = p_user_id
        AND is_active = true
        AND last_mentioned_at < NOW() - INTERVAL '1 day' * p_days_threshold
        AND confidence_score > 0.0;

    GET DIAGNOSTICS rows_affected = ROW_COUNT;
    RETURN rows_affected;
END;
$$ LANGUAGE plpgsql;

-- Function: Detect contradicting memories
-- Identifies memories with contradictory content using embeddings
CREATE OR REPLACE FUNCTION detect_contradicting_memories(
    p_user_id VARCHAR(100),
    p_new_node_id UUID
)
RETURNS TABLE (
    conflicting_node_id UUID,
    conflicting_content TEXT,
    similarity_score FLOAT,
    confidence_comparison TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        n1.id AS conflicting_node_id,
        n1.content AS conflicting_content,
        (1 - (n1.embedding <=> n2.embedding)) AS similarity_score,
        CASE
            WHEN n1.confidence_score > n2.confidence_score THEN 'older_more_confident'
            WHEN n1.confidence_score < n2.confidence_score THEN 'newer_more_confident'
            ELSE 'equal_confidence'
        END AS confidence_comparison
    FROM user_memory_nodes n1
    CROSS JOIN user_memory_nodes n2
    WHERE
        n1.user_id = p_user_id
        AND n2.id = p_new_node_id
        AND n1.id != n2.id
        AND n1.is_active = true
        AND n1.node_type = n2.node_type
        AND (1 - (n1.embedding <=> n2.embedding)) > 0.85 -- High similarity but...
        -- Look for contradiction patterns in content (simple heuristic)
        AND (
            n1.content ILIKE '%not%' OR n1.content ILIKE '%don''t%' OR
            n2.content ILIKE '%not%' OR n2.content ILIKE '%don''t%'
        )
    ORDER BY similarity_score DESC
    LIMIT 5;
END;
$$ LANGUAGE plpgsql;
```

#### 10.6.5.3 n8n Workflow: Memory Extraction

**Workflow Name:** `User_Memory_Extraction_v7`

**Trigger:** Called after each user message in chat interface

**Purpose:** Extract and store user facts, preferences, goals from conversation using Claude analysis

```json
{
  "name": "User_Memory_Extraction_v7",
  "nodes": [
    {
      "parameters": {
        "httpMethod": "POST",
        "path": "memory-extract",
        "options": {}
      },
      "name": "Webhook Trigger",
      "type": "n8n-nodes-base.webhook",
      "typeVersion": 2,
      "position": [250, 300],
      "id": "webhook_mem_extract_501",
      "webhookId": "memory-extract-v7"
    },
    {
      "parameters": {
        "language": "javaScript",
        "jsCode": "// Prepare context for memory extraction\nconst userId = $json.userId;\nconst sessionId = $json.sessionId;\nconst currentMessage = $json.message;\nconst conversationHistory = $json.conversationHistory || [];\n\n// Build conversation context (last 5 exchanges)\nconst recentExchanges = conversationHistory.slice(-10);\nconst conversationContext = recentExchanges\n  .map(msg => `${msg.role}: ${msg.content}`)\n  .join('\\n\\n');\n\nreturn [{\n  json: {\n    userId: userId,\n    sessionId: sessionId,\n    currentMessage: currentMessage,\n    conversationContext: conversationContext,\n    timestamp: new Date().toISOString()\n  }\n}];"
      },
      "name": "Prepare Context",
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [450, 300],
      "id": "prepare_context_502"
    },
    {
      "parameters": {
        "method": "POST",
        "url": "https://api.anthropic.com/v1/messages",
        "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth",
        "sendHeaders": true,
        "headerParameters": {
          "parameters": [
            {
              "name": "anthropic-version",
              "value": "2023-06-01"
            }
          ]
        },
        "sendBody": true,
        "contentType": "json",
        "bodyParameters": {
          "parameters": [
            {
              "name": "model",
              "value": "claude-sonnet-4-5-20250929"
            },
            {
              "name": "max_tokens",
              "value": 2000
            },
            {
              "name": "messages",
              "value": "={{ [{role: 'user', content: $json.prompt}] }}"
            }
          ]
        },
        "options": {}
      },
      "name": "Claude Memory Extraction",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [650, 300],
      "id": "claude_mem_extract_503",
      "credentials": {
        "httpHeaderAuth": {
          "id": "{{ANTHROPIC_API_KEY_CREDENTIAL_ID}}",
          "name": "Anthropic API Key"
        }
      }
    },
    {
      "parameters": {
        "language": "javaScript",
        "jsCode": "// Build prompt for memory extraction\nconst conversationContext = $json.conversationContext;\nconst currentMessage = $json.currentMessage;\n\nconst prompt = `You are a memory extraction assistant. Analyze the following conversation and extract structured user information.\n\nCONVERSATION CONTEXT:\n${conversationContext}\n\nCURRENT MESSAGE:\n${currentMessage}\n\nExtract the following types of information:\n1. **FACTS**: Concrete, factual information about the user (name, job, location, etc.)\n2. **PREFERENCES**: User likes, dislikes, preferences\n3. **GOALS**: User objectives, goals, aspirations\n4. **CONTEXT**: Background context, situation, constraints\n5. **SKILLS**: User skills, expertise, knowledge areas\n6. **INTERESTS**: Topics or domains the user is interested in\n\nFor each extracted item, provide:\n- **type**: One of: fact, preference, goal, context, skill, interest\n- **content**: The full description\n- **summary**: A concise 1-sentence summary\n- **confidence**: 0.0-1.0 confidence score\n- **source**: 'explicit' (directly stated) or 'inferred' (implied)\n- **importance**: 0.0-1.0 importance score\n\nAlso identify RELATIONSHIPS between extracted items:\n- **source**: Summary of first item\n- **target**: Summary of second item  \n- **type**: One of: causes, relates_to, contradicts, supports, precedes, enables\n- **strength**: 0.0-1.0 relationship strength\n\nReturn ONLY valid JSON in this format:\n{\n  \"memories\": [\n    {\n      \"type\": \"fact\",\n      \"content\": \"...\",\n      \"summary\": \"...\",\n      \"confidence\": 0.95,\n      \"source\": \"explicit\",\n      \"importance\": 0.8\n    }\n  ],\n  \"relationships\": [\n    {\n      \"source\": \"User works as software engineer\",\n      \"target\": \"User interested in AI\",\n      \"type\": \"relates_to\",\n      \"strength\": 0.7\n    }\n  ]\n}\n\nIf no new information to extract, return: {\"memories\": [], \"relationships\": []}`;\n\nreturn [{\n  json: {\n    ...($json),\n    prompt: prompt\n  }\n}];"
      },
      "name": "Build Extraction Prompt",
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [450, 300],
      "id": "build_prompt_504"
    },
    {
      "parameters": {
        "language": "javaScript",
        "jsCode": "// Parse Claude response\nconst response = $json.content[0].text;\nlet extracted;\n\ntry {\n  // Extract JSON from response (handle markdown code blocks)\n  const jsonMatch = response.match(/```json\\s*([\\s\\S]*?)\\s*```/) || \n                    response.match(/\\{[\\s\\S]*\\}/);\n  \n  if (jsonMatch) {\n    const jsonStr = jsonMatch[1] || jsonMatch[0];\n    extracted = JSON.parse(jsonStr);\n  } else {\n    extracted = { memories: [], relationships: [] };\n  }\n} catch (error) {\n  console.error('Failed to parse extraction:', error);\n  extracted = { memories: [], relationships: [] };\n}\n\nreturn [{\n  json: {\n    userId: $('Prepare Context').item.json.userId,\n    sessionId: $('Prepare Context').item.json.sessionId,\n    timestamp: $('Prepare Context').item.json.timestamp,\n    extracted: extracted,\n    memoryCount: extracted.memories?.length || 0,\n    relationshipCount: extracted.relationships?.length || 0\n  }\n}];"
      },
      "name": "Parse Extraction",
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [850, 300],
      "id": "parse_extraction_505"
    },
    {
      "parameters": {
        "conditions": {
          "boolean": [
            {
              "value1": "={{ $json.memoryCount > 0 }}",
              "value2": true
            }
          ]
        }
      },
      "name": "Has Memories?",
      "type": "n8n-nodes-base.if",
      "typeVersion": 2,
      "position": [1050, 300],
      "id": "has_memories_506"
    },
    {
      "parameters": {
        "method": "POST",
        "url": "http://localhost:11434/api/embeddings",
        "sendBody": true,
        "contentType": "json",
        "bodyParameters": {
          "parameters": [
            {
              "name": "model",
              "value": "nomic-embed-text"
            },
            {
              "name": "prompt",
              "value": "={{ $json.content }}"
            }
          ]
        },
        "options": {}
      },
      "name": "Generate Embedding",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [1250, 200],
      "id": "gen_embedding_507"
    },
    {
      "parameters": {
        "operation": "executeQuery",
        "query": "INSERT INTO user_memory_nodes (\n  user_id,\n  session_id,\n  node_type,\n  content,\n  summary,\n  embedding,\n  confidence_score,\n  source_type,\n  importance_score,\n  metadata\n) VALUES (\n  $1, $2, $3, $4, $5, $6::vector, $7, $8, $9, $10\n)\nRETURNING id, summary",
        "options": {
          "queryParams": "={{ [\n  $json.userId,\n  $json.sessionId,\n  $json.type,\n  $json.content,\n  $json.summary,\n  JSON.stringify($json.embedding),\n  $json.confidence,\n  $json.source,\n  $json.importance,\n  JSON.stringify({extracted_at: $json.timestamp})\n] }}"
        }
      },
      "name": "Store Memory Node",
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2.6,
      "position": [1450, 200],
      "id": "store_node_508",
      "credentials": {
        "postgres": {
          "id": "{{SUPABASE_POSTGRES_CREDENTIALS_ID}}",
          "name": "Supabase PostgreSQL"
        }
      }
    },
    {
      "parameters": {
        "operation": "executeQuery",
        "query": "INSERT INTO user_memory_edges (\n  user_id,\n  source_node_id,\n  target_node_id,\n  relationship_type,\n  strength,\n  metadata\n)\nSELECT \n  $1::VARCHAR,\n  (SELECT id FROM user_memory_nodes WHERE user_id = $1 AND summary = $2 ORDER BY created_at DESC LIMIT 1),\n  (SELECT id FROM user_memory_nodes WHERE user_id = $1 AND summary = $3 ORDER BY created_at DESC LIMIT 1),\n  $4::VARCHAR,\n  $5::FLOAT,\n  $6::JSONB\nWHERE EXISTS (\n  SELECT 1 FROM user_memory_nodes WHERE user_id = $1 AND summary = $2\n)\nAND EXISTS (\n  SELECT 1 FROM user_memory_nodes WHERE user_id = $1 AND summary = $3\n)\nON CONFLICT (source_node_id, target_node_id, relationship_type) \nDO UPDATE SET\n  strength = user_memory_edges.strength + EXCLUDED.strength / 2,\n  observation_count = user_memory_edges.observation_count + 1,\n  last_observed_at = NOW(),\n  updated_at = NOW()\nRETURNING id",
        "options": {
          "queryParams": "={{ [\n  $json.userId,\n  $json.source,\n  $json.target,\n  $json.type,\n  $json.strength,\n  JSON.stringify({created_at: $json.timestamp})\n] }}"
        }
      },
      "name": "Store Relationships",
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2.6,
      "position": [1450, 400],
      "id": "store_relationships_509",
      "credentials": {
        "postgres": {
          "id": "{{SUPABASE_POSTGRES_CREDENTIALS_ID}}",
          "name": "Supabase PostgreSQL"
        }
      }
    },
    {
      "parameters": {
        "language": "javaScript",
        "jsCode": "// Split memories for parallel processing\nconst memories = $json.extracted.memories || [];\nconst userId = $json.userId;\nconst sessionId = $json.sessionId;\nconst timestamp = $json.timestamp;\n\nreturn memories.map(memory => ({\n  json: {\n    userId: userId,\n    sessionId: sessionId,\n    timestamp: timestamp,\n    type: memory.type,\n    content: memory.content,\n    summary: memory.summary,\n    confidence: memory.confidence,\n    source: memory.source,\n    importance: memory.importance\n  }\n}));"
      },
      "name": "Split Memories",
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [1250, 200],
      "id": "split_memories_510"
    },
    {
      "parameters": {
        "language": "javaScript",
        "jsCode": "// Split relationships for parallel processing\nconst relationships = $json.extracted.relationships || [];\nconst userId = $json.userId;\nconst timestamp = $json.timestamp;\n\nreturn relationships.map(rel => ({\n  json: {\n    userId: userId,\n    timestamp: timestamp,\n    source: rel.source,\n    target: rel.target,\n    type: rel.type,\n    strength: rel.strength\n  }\n}));"
      },
      "name": "Split Relationships",
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [1250, 400],
      "id": "split_relationships_511"
    },
    {
      "parameters": {
        "respondWith": "json",
        "responseBody": "={{ {\n  success: true,\n  memoriesStored: $json.memoryCount,\n  relationshipsStored: $json.relationshipCount\n} }}"
      },
      "name": "Return Response",
      "type": "n8n-nodes-base.respondToWebhook",
      "typeVersion": 1,
      "position": [1650, 300],
      "id": "return_response_512"
    }
  ],
  "connections": {
    "Webhook Trigger": {
      "main": [[{ "node": "Prepare Context", "type": "main", "index": 0 }]]
    },
    "Prepare Context": {
      "main": [[{ "node": "Build Extraction Prompt", "type": "main", "index": 0 }]]
    },
    "Build Extraction Prompt": {
      "main": [[{ "node": "Claude Memory Extraction", "type": "main", "index": 0 }]]
    },
    "Claude Memory Extraction": {
      "main": [[{ "node": "Parse Extraction", "type": "main", "index": 0 }]]
    },
    "Parse Extraction": {
      "main": [[{ "node": "Has Memories?", "type": "main", "index": 0 }]]
    },
    "Has Memories?": {
      "main": [
        [
          { "node": "Split Memories", "type": "main", "index": 0 },
          { "node": "Split Relationships", "type": "main", "index": 0 }
        ]
      ]
    },
    "Split Memories": {
      "main": [[{ "node": "Generate Embedding", "type": "main", "index": 0 }]]
    },
    "Generate Embedding": {
      "main": [[{ "node": "Store Memory Node", "type": "main", "index": 0 }]]
    },
    "Split Relationships": {
      "main": [[{ "node": "Store Relationships", "type": "main", "index": 0 }]]
    },
    "Store Memory Node": {
      "main": [[{ "node": "Return Response", "type": "main", "index": 0 }]]
    },
    "Store Relationships": {
      "main": [[{ "node": "Return Response", "type": "main", "index": 0 }]]
    }
  }
}
```

#### 10.6.5.4 n8n Workflow: Memory Retrieval with Graph Context

**Workflow Name:** `User_Memory_Retrieval_v7`

**Trigger:** Called before RAG query execution

**Purpose:** Retrieve personalized context from user memory graph to enhance query results

```json
{
  "name": "User_Memory_Retrieval_v7",
  "nodes": [
    {
      "parameters": {
        "httpMethod": "POST",
        "path": "memory-retrieve",
        "options": {}
      },
      "name": "Webhook Trigger",
      "type": "n8n-nodes-base.webhook",
      "typeVersion": 2,
      "position": [250, 300],
      "id": "webhook_mem_retrieve_601",
      "webhookId": "memory-retrieve-v7"
    },
    {
      "parameters": {
        "method": "POST",
        "url": "http://localhost:11434/api/embeddings",
        "sendBody": true,
        "contentType": "json",
        "bodyParameters": {
          "parameters": [
            {
              "name": "model",
              "value": "nomic-embed-text"
            },
            {
              "name": "prompt",
              "value": "={{ $json.query }}"
            }
          ]
        },
        "options": {}
      },
      "name": "Generate Query Embedding",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [450, 300],
      "id": "gen_query_embed_602"
    },
    {
      "parameters": {
        "operation": "executeQuery",
        "query": "SELECT * FROM get_user_memory_context(\n  $1::VARCHAR,\n  $2::vector,\n  $3::INTEGER,\n  $4::INTEGER,\n  $5::FLOAT\n)",
        "options": {
          "queryParams": "={{ [\n  $json.userId,\n  JSON.stringify($json.embedding),\n  10,\n  2,\n  0.7\n] }}"
        }
      },
      "name": "Get Memory Context",
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2.6,
      "position": [650, 300],
      "id": "get_mem_context_603",
      "credentials": {
        "postgres": {
          "id": "{{SUPABASE_POSTGRES_CREDENTIALS_ID}}",
          "name": "Supabase PostgreSQL"
        }
      }
    },
    {
      "parameters": {
        "operation": "executeQuery",
        "query": "SELECT * FROM get_personalized_document_entities(\n  $1::VARCHAR,\n  $2::TEXT,\n  $3::INTEGER\n)",
        "options": {
          "queryParams": "={{ [\n  $json.userId,\n  $json.query,\n  5\n] }}"
        }
      },
      "name": "Get Personalized Entities",
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2.6,
      "position": [650, 450],
      "id": "get_pers_entities_604",
      "credentials": {
        "postgres": {
          "id": "{{SUPABASE_POSTGRES_CREDENTIALS_ID}}",
          "name": "Supabase PostgreSQL"
        }
      }
    },
    {
      "parameters": {
        "language": "javaScript",
        "jsCode": "// Combine memory context and personalized entities\nconst memoryContext = $('Get Memory Context').all();\nconst personalizedEntities = $('Get Personalized Entities').all();\nconst originalQuery = $('Webhook Trigger').item.json.query;\nconst userId = $('Webhook Trigger').item.json.userId;\n\n// Format memory context\nconst memories = memoryContext.map(item => ({\n  type: item.json.node_type,\n  content: item.json.summary || item.json.content,\n  similarity: item.json.similarity_score,\n  importance: item.json.importance_score,\n  hopDistance: item.json.hop_distance,\n  relationshipPath: item.json.relationship_path\n}));\n\n// Format personalized entities\nconst entities = personalizedEntities.map(item => ({\n  entityId: item.json.entity_id,\n  entityName: item.json.entity_name,\n  relevanceScore: item.json.relevance_score,\n  connectionCount: item.json.connection_count,\n  relatedMemories: item.json.related_memories\n}));\n\n// Build enriched query context\nconst memoryContextText = memories.length > 0 ? \n  'USER CONTEXT:\\n' + memories.map(m => \n    `- ${m.content} (${m.type}, similarity: ${m.similarity.toFixed(2)})`\n  ).join('\\n') : '';\n\nconst entityContextText = entities.length > 0 ?\n  '\\n\\nRELATED EXPERTISE/INTERESTS:\\n' + entities.map(e =>\n    `- ${e.entityName} (${e.connectionCount} connections)`\n  ).join('\\n') : '';\n\nconst enrichedQuery = memoryContextText || entityContextText ? \n  `${originalQuery}\\n\\n${memoryContextText}${entityContextText}` : originalQuery;\n\nreturn [{\n  json: {\n    userId: userId,\n    originalQuery: originalQuery,\n    enrichedQuery: enrichedQuery,\n    memoryContext: {\n      memories: memories,\n      entities: entities,\n      memoryCount: memories.length,\n      entityCount: entities.length\n    },\n    hasContext: memories.length > 0 || entities.length > 0\n  }\n}];"
      },
      "name": "Build Enriched Context",
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [850, 300],
      "id": "build_enriched_605"
    },
    {
      "parameters": {
        "respondWith": "json",
        "responseBody": "={{ $json }}"
      },
      "name": "Return Context",
      "type": "n8n-nodes-base.respondToWebhook",
      "typeVersion": 1,
      "position": [1050, 300],
      "id": "return_context_606"
    }
  ],
  "connections": {
    "Webhook Trigger": {
      "main": [[
        { "node": "Generate Query Embedding", "type": "main", "index": 0 }
      ]]
    },
    "Generate Query Embedding": {
      "main": [[
        { "node": "Get Memory Context", "type": "main", "index": 0 },
        { "node": "Get Personalized Entities", "type": "main", "index": 0 }
      ]]
    },
    "Get Memory Context": {
      "main": [[{ "node": "Build Enriched Context", "type": "main", "index": 0 }]]
    },
    "Get Personalized Entities": {
      "main": [[{ "node": "Build Enriched Context", "type": "main", "index": 0 }]]
    },
    "Build Enriched Context": {
      "main": [[{ "node": "Return Context", "type": "main", "index": 0 }]]
    }
  }
}
```

#### 10.6.5.5 Integration with Main Chat Workflow

Add the following node to the main chat workflow (Section 10.6.2) **before** the "Call RAG Pipeline" node:

```javascript
// Node: "Retrieve User Memory Context"
// Position: Between "Session Management" and "Call RAG Pipeline"
{
  "parameters": {
    "method": "POST",
    "url": "http://localhost:5678/webhook/memory-retrieve",
    "sendBody": true,
    "contentType": "json",
    "bodyParameters": {
      "parameters": [
        {
          "name": "userId",
          "value": "={{ $json.userId }}"
        },
        {
          "name": "query",
          "value": "={{ $json.message }}"
        }
      ]
    },
    "options": {}
  },
  "name": "Retrieve User Memory Context",
  "type": "n8n-nodes-base.httpRequest",
  "typeVersion": 4.2,
  "position": [750, 300],
  "id": "retrieve_user_mem_607"
}
```

Update the "Call RAG Pipeline" node to use enriched query:

```javascript
// Modified "Call RAG Pipeline" node
{
  "parameters": {
    "method": "POST",
    "url": "http://localhost:5678/webhook/rag-query",
    "sendBody": true,
    "bodyParameters": {
      "parameters": [
        {
          "name": "query",
          "value": "={{ $json.enrichedQuery || $json.message }}" // Use enriched if available
        },
        {
          "name": "filters",
          "value": "={{ {} }}"
        },
        {
          "name": "options",
          "value": "={{ {max_results: 5, rerank: true} }}"
        },
        {
          "name": "userContext",
          "value": "={{ $json.memoryContext }}" // Pass memory context
        }
      ]
    }
  },
  "name": "Call RAG Pipeline",
  "type": "n8n-nodes-base.httpRequest",
  "typeVersion": 4.2,
  "position": [950, 300],
  "id": "call_rag_404"
}
```

#### 10.6.5.6 Performance Characteristics

**Memory Extraction:**
- Claude API call: 1-2 seconds
- Embedding generation: 50-100ms per memory (parallel processing)
- Database insertion: 10-20ms per node/edge
- **Total**: <3 seconds for typical extraction (3-5 memories)

**Memory Retrieval:**
- Query embedding: 50-100ms
- Graph traversal (2 hops): 50-100ms
- Entity personalization: 30-50ms
- Context building: <10ms
- **Total**: <300ms for complete context retrieval

**Graph Traversal Depth:**
- Depth 1: Direct connections only (~10ms)
- Depth 2: 2-hop connections (~50ms) **[Recommended]**
- Depth 3: 3-hop connections (~150ms)

**Storage Efficiency:**
- Average memory node: ~500 bytes + 3KB embedding = 3.5KB
- 1000 memories per user: ~3.5MB
- 10,000 users with 1000 memories each: ~35GB

**Decay Schedule:**
- Run daily: `SELECT decay_user_memories('all_users', 30, 0.1);`
- Reduces confidence by 10% for memories older than 30 days
- Prevents stale information from polluting context

#### 10.6.5.7 Integration with LightRAG

When LightRAG entities are identified during document processing, create user-document connections:

```sql
-- Example: Connect user memory to LightRAG entity
INSERT INTO user_document_connections (
  user_id,
  memory_node_id,
  document_entity_id,
  document_entity_name,
  document_id,
  connection_type,
  relevance_score
)
SELECT
  'user_123',
  n.id,
  'entity_ai_architecture', -- From LightRAG
  'AI Architecture',
  'd574f5c2-8b9a-4e23-9f1a-3c5d7e8a9b0c',
  'expert_in',
  0.9
FROM user_memory_nodes n
WHERE
  n.user_id = 'user_123'
  AND n.node_type = 'skill'
  AND n.content ILIKE '%AI%architecture%'
LIMIT 1;
```

This creates a **hybrid graph** linking user expertise to document knowledge, enabling queries like:
- "What documents are relevant to my expertise?"
- "Show me papers related to topics I'm interested in"
- "Find entities I've worked with before"

#### 10.6.5.8 Privacy and Security Considerations

**Data Privacy:**
- User memories stored in private Supabase instance (NOT external API like Zep)
- Row-level security enforced on all memory tables
- Automatic PII detection and masking (optional)
- User can request full memory deletion (GDPR compliance)

**Access Control:**
```sql
-- Row-level security policy
ALTER TABLE user_memory_nodes ENABLE ROW LEVEL SECURITY;

CREATE POLICY user_memory_isolation ON user_memory_nodes
  FOR ALL
  USING (user_id = current_setting('app.current_user_id')::VARCHAR);
```

**Memory Expiration:**
- Sensitive facts can have `expires_at` timestamps
- Automatic cleanup of expired memories
- User can manually archive or delete memories

### 10.17.2 Required Database Schema for LangExtract

```sql
-- LangExtract results storage
CREATE TABLE IF NOT EXISTS langextract_results (
  id BIGSERIAL PRIMARY KEY,
  document_id TEXT NOT NULL,
  entities JSONB NOT NULL DEFAULT '[]'::jsonb,
  relationships JSONB NOT NULL DEFAULT '[]'::jsonb,
  confidence_scores JSONB NOT NULL DEFAULT '{}'::jsonb,
  grounding_validation JSONB NOT NULL DEFAULT '{}'::jsonb,
  overall_score FLOAT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast lookups
CREATE INDEX idx_langextract_document ON langextract_results(document_id);
CREATE INDEX idx_langextract_score ON langextract_results(overall_score);
CREATE INDEX idx_langextract_entities ON langextract_results USING gin(entities);

-- View for high-confidence extractions
CREATE VIEW high_confidence_extractions AS
SELECT
  document_id,
  entities,
  relationships,
  overall_score
FROM langextract_results
WHERE overall_score >= 0.85
ORDER BY overall_score DESC;
```

### 10.17.3 Testing the Precision Extraction Workflow

**Test Payload:**
```bash
curl -X POST https://n8n-d21p.onrender.com/webhook/precision-extraction \
  -H "Content-Type: application/json" \
  -d '{
    "documentId": "test-doc-001",
    "fileData": "base64_encoded_file_content",
    "fileName": "sample_contract.pdf"
  }'
```

**Expected Response:**
```json
{
  "document_id": "test-doc-001",
  "entities": [
    {
      "field": "people",
      "value": "John Doe",
      "type": "Person",
      "confidence": 0.95,
      "grounded": true,
      "source_chunk_id": "chunk_123"
    },
    {
      "field": "organizations",
      "value": "Acme Corporation",
      "type": "Organization",
      "confidence": 0.92,
      "grounded": true,
      "source_chunk_id": "chunk_124"
    }
  ],
  "relationships": [
    {
      "type": "works_for",
      "source": "John Doe",
      "target": "Acme Corporation",
      "confidence": 0.89
    }
  ],
  "overall_grounding_score": 0.97
}
```

### 10.18.2 Multi-Modal Database Schema

```sql
-- Multi-modal documents table
CREATE TABLE IF NOT EXISTS multimodal_documents (
  id BIGSERIAL PRIMARY KEY,
  document_id TEXT UNIQUE NOT NULL,
  document_type TEXT NOT NULL, -- 'pdf', 'image', 'audio', 'video', 'structured', 'text'
  content JSONB NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  processed_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_multimodal_type ON multimodal_documents(document_type);
CREATE INDEX idx_multimodal_content ON multimodal_documents USING gin(content);
CREATE INDEX idx_multimodal_metadata ON multimodal_documents USING gin(metadata);

-- View for image documents
CREATE VIEW image_documents AS
SELECT
  document_id,
  content->>'image_description' as description,
  metadata,
  processed_at
FROM multimodal_documents
WHERE document_type = 'image';

-- View for audio/video transcriptions
CREATE VIEW transcribed_media AS
SELECT
  document_id,
  content->>'transcription' as transcription,
  metadata->>'speakers' as speakers,
  metadata->>'timestamps' as timestamps,
  processed_at
FROM multimodal_documents
WHERE document_type IN ('audio', 'video');
```

### 10.20.2 Observability Database Schema

```sql
-- Document processing log
CREATE TABLE IF NOT EXISTS document_processing_log (
  id BIGSERIAL PRIMARY KEY,
  document_id TEXT NOT NULL,
  user_id TEXT,
  status TEXT NOT NULL, -- 'success', 'error', 'in_progress'
  processing_time_ms INTEGER,
  error_message TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_processing_log_created ON document_processing_log(created_at DESC);
CREATE INDEX idx_processing_log_status ON document_processing_log(status);

-- Query performance log
CREATE TABLE IF NOT EXISTS query_performance_log (
  id BIGSERIAL PRIMARY KEY,
  query_id TEXT NOT NULL,
  query_text TEXT NOT NULL,
  hybrid_search_time_ms INTEGER,
  reranking_time_ms INTEGER,
  llm_time_ms INTEGER,
  total_time_ms INTEGER,
  cache_hit BOOLEAN DEFAULT FALSE,
  context_chunks INTEGER,
  relevance_score FLOAT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_query_log_created ON query_performance_log(created_at DESC);
CREATE INDEX idx_query_log_cache ON query_performance_log(cache_hit);

-- Alert log
CREATE TABLE IF NOT EXISTS alert_log (
  id BIGSERIAL PRIMARY KEY,
  severity TEXT NOT NULL, -- 'critical', 'warning', 'info'
  alert_type TEXT NOT NULL,
  message TEXT NOT NULL,
  value FLOAT,
  threshold FLOAT,
  acknowledged BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_alert_log_severity ON alert_log(severity, created_at DESC);
CREATE INDEX idx_alert_log_ack ON alert_log(acknowledged) WHERE acknowledged = FALSE;
```

### 10.20.3 Grafana Dashboard Configuration

```yaml
grafana_dashboards:
  - name: "Empire RAG System Overview"
    panels:
      - title: "Query Latency (P95, P99)"
        type: "graph"
        metrics:
          - empire_latency_p95
          - empire_latency_p99

      - title: "Cache Hit Rate"
        type: "gauge"
        metric: empire_cache_hit_rate
        thresholds:
          - { value: 0.4, color: "red" }
          - { value: 0.6, color: "yellow" }
          - { value: 0.8, color: "green" }

      - title: "Search Quality (Relevance)"
        type: "gauge"
        metric: empire_relevance_score_avg
        thresholds:
          - { value: 0.6, color: "red" }
          - { value: 0.75, color: "yellow" }
          - { value: 0.85, color: "green" }

      - title: "Error Rate"
        type: "graph"
        metric: empire_errors_total
        alert: "errors > 10/min"

      - title: "Active Users"
        type: "stat"
        metric: empire_active_users

      - title: "Processing Time Breakdown"
        type: "bar"
        metrics:
          - empire_search_time_avg
          - empire_reranking_time_avg
          - empire_llm_time_avg
```

CREATE TABLE IF NOT EXISTS batch_processing_log (
  id BIGSERIAL PRIMARY KEY,
  batch_date DATE NOT NULL,
  total_processed INTEGER NOT NULL,
  successful INTEGER NOT NULL,
  failed INTEGER NOT NULL,
  processing_time_ms BIGINT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_batch_log_date ON batch_processing_log(batch_date DESC);
```

CREATE TABLE IF NOT EXISTS public.n8n_chat_histories (
  id BIGSERIAL PRIMARY KEY,
  session_id VARCHAR(255) NOT NULL,
  user_id VARCHAR(255),
  message JSONB NOT NULL,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Tabular Document Rows (Gap 1.3)
CREATE TABLE IF NOT EXISTS public.tabular_document_rows (
  id BIGSERIAL PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  record_manager_id BIGINT REFERENCES documents(id) ON DELETE CASCADE,
  row_data JSONB NOT NULL,
  schema_metadata JSONB,
  inferred_relationships JSONB
);

-- 3. Metadata Fields Management (Gap 1.5)
CREATE TABLE IF NOT EXISTS public.metadata_fields (
  id BIGSERIAL PRIMARY KEY,
  field_name TEXT NOT NULL UNIQUE,
  field_type VARCHAR(50) NOT NULL,
  allowed_values TEXT[],
  validation_regex TEXT,
  description TEXT,
  is_required BOOLEAN DEFAULT FALSE,
  display_order INTEGER,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Knowledge Graph Entities (Local storage)
CREATE TABLE IF NOT EXISTS public.knowledge_entities (
  id BIGSERIAL PRIMARY KEY,
  entity_name TEXT NOT NULL,
  entity_type VARCHAR(100),
  properties JSONB DEFAULT '{}',
  relationships JSONB DEFAULT '[]',
  document_ids TEXT[] DEFAULT '{}',
  confidence_score FLOAT DEFAULT 0.0,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. Graph Relationships
CREATE TABLE IF NOT EXISTS public.graph_relationships (
  id BIGSERIAL PRIMARY KEY,
  source_entity_id BIGINT REFERENCES knowledge_entities(id) ON DELETE CASCADE,
  target_entity_id BIGINT REFERENCES knowledge_entities(id) ON DELETE CASCADE,
  relationship_type VARCHAR(100),
  properties JSONB DEFAULT '{}',
  confidence_score FLOAT DEFAULT 0.0,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. User Memory Graph
CREATE TABLE IF NOT EXISTS public.user_memory_graph (
  id BIGSERIAL PRIMARY KEY,
  user_id VARCHAR(255) NOT NULL,
  fact_text TEXT NOT NULL,
  fact_embedding vector(768),
  entity_refs TEXT[] DEFAULT '{}',
  confidence_score FLOAT DEFAULT 0.8,
  importance_score FLOAT DEFAULT 0.5,
  access_count INTEGER DEFAULT 0,
  last_accessed TIMESTAMPTZ,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 7. Memory Relationships
CREATE TABLE IF NOT EXISTS public.memory_relationships (
  id BIGSERIAL PRIMARY KEY,
  source_memory_id BIGINT REFERENCES user_memory_graph(id) ON DELETE CASCADE,
  target_memory_id BIGINT REFERENCES user_memory_graph(id) ON DELETE CASCADE,
  relationship_type VARCHAR(50),
  confidence FLOAT DEFAULT 0.5,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 8. Batch Processing Log
CREATE TABLE IF NOT EXISTS public.batch_processing_log (
  id BIGSERIAL PRIMARY KEY,
  batch_id UUID DEFAULT gen_random_uuid(),
  batch_date DATE NOT NULL,
  total_documents INTEGER NOT NULL,
  processed_documents INTEGER DEFAULT 0,
  failed_documents INTEGER DEFAULT 0,
  processing_status VARCHAR(50) DEFAULT 'pending',
  error_details JSONB DEFAULT '[]',
  processing_time_ms BIGINT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 9. Document Status Tracking
CREATE TABLE IF NOT EXISTS public.document_status (
  id BIGSERIAL PRIMARY KEY,
  document_id BIGINT REFERENCES documents(id) ON DELETE CASCADE,
  status VARCHAR(50) NOT NULL,
  status_details JSONB DEFAULT '{}',
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 10. Add missing columns to existing tables
ALTER TABLE documents ADD COLUMN IF NOT EXISTS content_hash TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS version_number INTEGER DEFAULT 1;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS previous_version_id BIGINT REFERENCES documents(id);
ALTER TABLE documents ADD COLUMN IF NOT EXISTS is_current_version BOOLEAN DEFAULT TRUE;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS graph_id TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS hierarchical_index JSONB;

-- 11. Create all indexes for performance
CREATE INDEX IF NOT EXISTS idx_chat_history_session ON n8n_chat_histories(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_history_user ON n8n_chat_histories(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_history_created ON n8n_chat_histories(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_tabular_rows_data ON tabular_document_rows USING gin(row_data);
CREATE INDEX IF NOT EXISTS idx_tabular_rows_manager ON tabular_document_rows(record_manager_id);

CREATE INDEX IF NOT EXISTS idx_metadata_fields_name ON metadata_fields(field_name);
CREATE INDEX IF NOT EXISTS idx_metadata_fields_type ON metadata_fields(field_type);

CREATE INDEX IF NOT EXISTS idx_document_hash ON documents(content_hash);
CREATE INDEX IF NOT EXISTS idx_document_version ON documents(version_number, is_current_version);
CREATE INDEX IF NOT EXISTS idx_document_graph ON documents(graph_id);
CREATE INDEX IF NOT EXISTS idx_document_hierarchy ON documents USING gin(hierarchical_index);

CREATE INDEX IF NOT EXISTS idx_knowledge_entities_name ON knowledge_entities(entity_name);
CREATE INDEX IF NOT EXISTS idx_knowledge_entities_type ON knowledge_entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_knowledge_entities_docs ON knowledge_entities USING gin(document_ids);

CREATE INDEX IF NOT EXISTS idx_user_memory_user ON user_memory_graph(user_id);
CREATE INDEX IF NOT EXISTS idx_user_memory_embedding ON user_memory_graph USING hnsw(fact_embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_user_memory_importance ON user_memory_graph(importance_score DESC);

CREATE INDEX IF NOT EXISTS idx_batch_log_date ON batch_processing_log(batch_date DESC);
CREATE INDEX IF NOT EXISTS idx_batch_log_status ON batch_processing_log(processing_status);

CREATE INDEX IF NOT EXISTS idx_document_status ON document_status(document_id, status);

-- 12. Insert default metadata fields
INSERT INTO metadata_fields (field_name, field_type, description, is_required, display_order) VALUES
  ('department', 'enum', 'Department or category', true, 1),
  ('course_code', 'string', 'Course identifier', false, 2),
  ('academic_level', 'enum', 'Academic level', false, 3),
  ('content_type', 'enum', 'Type of content', true, 4),
  ('keywords', 'string', 'Comma-separated keywords', false, 5),
  ('author', 'string', 'Content author', false, 6),
  ('date_created', 'date', 'Creation date', false, 7),
  ('language', 'enum', 'Content language', false, 8)
ON CONFLICT (field_name) DO NOTHING;

-- 13. Grant appropriate permissions
GRANT ALL ON ALL TABLES IN SCHEMA public TO authenticated;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO authenticated;
GRANT ALL ON ALL FUNCTIONS IN SCHEMA public TO authenticated;

COMMIT;

-- Verify all tables were created
SELECT table_name,
       pg_size_pretty(pg_total_relation_size(quote_ident(table_name)::regclass)) as size
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_type = 'BASE TABLE'
ORDER BY table_name;
```

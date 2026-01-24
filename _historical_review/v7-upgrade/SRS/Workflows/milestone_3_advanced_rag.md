## 10.4 Milestone 3: Embeddings and Vector Storage

### 10.4.1 Objectives
- Generate embeddings using OpenAI Ada-002 model
- Store vectors in Supabase with pgvector
- Implement efficient similarity search
- Create hybrid search combining vector and keyword
- Optimize for performance and cost
- Handle batch processing for large documents

### 10.4.2 Complete Embeddings Generation Workflow

```json
{
  "name": "Embeddings_Generation_v7_Complete",
  "nodes": [
    {
      "parameters": {
        "operation": "executeQuery",
        "query": "SELECT \n  c.id,\n  c.document_id,\n  c.chunk_index,\n  c.content,\n  c.content_hash,\n  c.metadata,\n  d.filename,\n  d.category\nFROM document_chunks c\nJOIN documents d ON c.document_id = d.document_id\nWHERE c.embedding IS NULL\nORDER BY d.processing_priority ASC, c.chunk_index ASC\nLIMIT 100",
        "options": {}
      },
      "name": "Get Chunks for Embedding",
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2.6,
      "position": [250, 300],
      "id": "get_chunks_201",
      "credentials": {
        "postgres": {
          "id": "{{SUPABASE_POSTGRES_CREDENTIALS_ID}}",
          "name": "Supabase PostgreSQL"
        }
      }
    },
    {
      "parameters": {
        "batchSize": 20,
        "options": {}
      },
      "name": "Batch for API Efficiency",
      "type": "n8n-nodes-base.splitInBatches",
      "typeVersion": 3.0,
      "position": [450, 300],
      "id": "batch_chunks_202"
    },
    {
      "parameters": {
        "model": "text-embedding-ada-002",
        "options": {
          "dimensions": 1536,
          "encoding_format": "float"
        }
      },
      "name": "Generate Embeddings",
      "type": "@n8n/n8n-nodes-langchain.embeddingsOpenAi",
      "typeVersion": 1.0,
      "position": [650, 300],
      "id": "generate_embeddings_203",
      "credentials": {
        "openAiApi": {
          "id": "{{OPENAI_CREDENTIALS_ID}}",
          "name": "OpenAI API"
        }
      }
    },
    {
      "parameters": {
        "language": "javaScript",
        "jsCode": "// Process embedding results and prepare for storage\nconst batchResults = $input.all();\nconst processedChunks = [];\n\n// Cost tracking\nlet totalTokens = 0;\nconst tokenEstimator = (text) => Math.ceil(text.length / 4);\n\nfor (const item of batchResults) {\n  const chunk = item.json;\n  const embedding = item.json.embedding;\n  \n  if (!embedding || embedding.length !== 1536) {\n    console.error(`Invalid embedding for chunk ${chunk.id}`);\n    continue;\n  }\n  \n  // Estimate token usage\n  const tokens = tokenEstimator(chunk.content);\n  totalTokens += tokens;\n  \n  // Prepare for database storage\n  processedChunks.push({\n    json: {\n      chunk_id: chunk.id,\n      document_id: chunk.document_id,\n      chunk_index: chunk.chunk_index,\n      embedding: embedding,\n      embedding_model: 'text-embedding-ada-002',\n      embedding_dimensions: 1536,\n      tokens_used: tokens,\n      processing_time: new Date().toISOString(),\n      metadata: {\n        ...chunk.metadata,\n        embedding_generated: true,\n        embedding_version: '1.0'\n      }\n    }\n  });\n}\n\n// Add cost calculation\nconst costPerThousand = 0.0001; // $0.0001 per 1K tokens\nconst estimatedCost = (totalTokens / 1000) * costPerMillion;\n\nconsole.log(`Processed ${processedChunks.length} chunks`);\nconsole.log(`Total tokens used: ${totalTokens}`);\nconsole.log(`Estimated cost: $${estimatedCost.toFixed(4)}`);\n\nreturn processedChunks;"
      },
      "name": "Process Embeddings",
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [850, 300],
      "id": "process_embeddings_204"
    },
    {
      "parameters": {
        "operation": "executeQuery",
        "query": "UPDATE document_chunks \nSET \n  embedding = $1::vector,\n  embedding_model = $2,\n  updated_at = NOW()\nWHERE id = $3\nRETURNING id, document_id, chunk_index",
        "options": {
          "queryParams": "={{ [\n  '[' + $json.embedding.join(',') + ']',\n  $json.embedding_model,\n  $json.chunk_id\n] }}",
          "queryBatching": {
            "mode": "transaction",
            "batchSize": 50
          }
        }
      },
      "name": "Store Embeddings",
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2.6,
      "position": [1050, 300],
      "id": "store_embeddings_205",
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
        "query": "UPDATE documents \nSET \n  vector_count = (\n    SELECT COUNT(*) \n    FROM document_chunks \n    WHERE document_id = $1 \n    AND embedding IS NOT NULL\n  ),\n  processing_status = CASE \n    WHEN (\n      SELECT COUNT(*) \n      FROM document_chunks \n      WHERE document_id = $1 \n      AND embedding IS NULL\n    ) = 0 THEN 'embeddings_complete'\n    ELSE 'embeddings_partial'\n  END,\n  updated_at = NOW()\nWHERE document_id = $1",
        "options": {
          "queryParams": "={{ [$json.document_id] }}"
        }
      },
      "name": "Update Document Status",
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2.6,
      "position": [1250, 300],
      "id": "update_doc_status_206"
    }
  ],
  "connections": {
    "Get Chunks for Embedding": {
      "main": [
        [
          {
            "node": "Batch for API Efficiency",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Batch for API Efficiency": {
      "main": [
        [
          {
            "node": "Generate Embeddings",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Generate Embeddings": {
      "main": [
        [
          {
            "node": "Process Embeddings",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Process Embeddings": {
      "main": [
        [
          {
            "node": "Store Embeddings",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Store Embeddings": {
      "main": [
        [
          {
            "node": "Update Document Status",
            "type": "main",
            "index": 0
          }
        ]
      ]
    }
  }
}
```

### 10.4.3 Vector Search Functions

```sql
-- Hybrid search function combining vector similarity and keyword matching
CREATE OR REPLACE FUNCTION hybrid_search_rag(
    query_text TEXT,
    query_embedding vector(1536),
    match_count INTEGER DEFAULT 10,
    similarity_threshold FLOAT DEFAULT 0.7
)
RETURNS TABLE (
    document_id VARCHAR(64),
    chunk_id UUID,
    chunk_index INTEGER,
    content TEXT,
    similarity_score FLOAT,
    keyword_score FLOAT,
    combined_score FLOAT,
    metadata JSONB
) AS $$
BEGIN
    RETURN QUERY
    WITH vector_search AS (
        SELECT 
            c.document_id,
            c.id AS chunk_id,
            c.chunk_index,
            c.content,
            1 - (c.embedding <=> query_embedding) AS similarity_score,
            c.metadata
        FROM document_chunks c
        WHERE c.embedding IS NOT NULL
        AND (1 - (c.embedding <=> query_embedding)) > similarity_threshold
        ORDER BY c.embedding <=> query_embedding
        LIMIT match_count * 2
    ),
    keyword_search AS (
        SELECT 
            c.document_id,
            c.id AS chunk_id,
            c.chunk_index,
            c.content,
            ts_rank_cd(
                to_tsvector('english', c.content),
                plainto_tsquery('english', query_text)
            ) AS keyword_score,
            c.metadata
        FROM document_chunks c
        WHERE to_tsvector('english', c.content) @@ plainto_tsquery('english', query_text)
        LIMIT match_count * 2
    ),
    combined AS (
        SELECT 
            COALESCE(v.document_id, k.document_id) AS document_id,
            COALESCE(v.chunk_id, k.chunk_id) AS chunk_id,
            COALESCE(v.chunk_index, k.chunk_index) AS chunk_index,
            COALESCE(v.content, k.content) AS content,
            COALESCE(v.similarity_score, 0) AS similarity_score,
            COALESCE(k.keyword_score, 0) AS keyword_score,
            COALESCE(v.metadata, k.metadata) AS metadata
        FROM vector_search v
        FULL OUTER JOIN keyword_search k 
            ON v.chunk_id = k.chunk_id
    )
    SELECT 
        document_id,
        chunk_id,
        chunk_index,
        content,
        similarity_score,
        keyword_score,
        (0.7 * similarity_score + 0.3 * LEAST(keyword_score, 1.0)) AS combined_score,
        metadata
    FROM combined
    ORDER BY combined_score DESC
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;

-- Semantic search with document filtering
CREATE OR REPLACE FUNCTION semantic_search_with_filter(
    query_embedding vector(1536),
    filter_category VARCHAR(50) DEFAULT NULL,
    filter_tags TEXT[] DEFAULT NULL,
    match_count INTEGER DEFAULT 10
)
RETURNS TABLE (
    document_id VARCHAR(64),
    filename TEXT,
    chunk_id UUID,
    content TEXT,
    similarity_score FLOAT,
    metadata JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        c.document_id,
        d.filename,
        c.id AS chunk_id,
        c.content,
        1 - (c.embedding <=> query_embedding) AS similarity_score,
        c.metadata
    FROM document_chunks c
    JOIN documents d ON c.document_id = d.document_id
    WHERE c.embedding IS NOT NULL
    AND (filter_category IS NULL OR d.category = filter_category)
    AND (filter_tags IS NULL OR d.tags && filter_tags)
    ORDER BY c.embedding <=> query_embedding
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;

-- Multi-vector search across multiple embeddings
CREATE OR REPLACE FUNCTION multi_vector_search(
    query_embeddings vector(1536)[],
    aggregation_method VARCHAR(10) DEFAULT 'average',
    match_count INTEGER DEFAULT 10
)
RETURNS TABLE (
    document_id VARCHAR(64),
    chunk_id UUID,
    content TEXT,
    avg_similarity FLOAT,
    max_similarity FLOAT,
    metadata JSONB
) AS $$
BEGIN
    RETURN QUERY
    WITH individual_searches AS (
        SELECT 
            c.document_id,
            c.id AS chunk_id,
            c.content,
            c.metadata,
            1 - (c.embedding <=> unnest(query_embeddings)) AS similarity
        FROM document_chunks c
        WHERE c.embedding IS NOT NULL
    ),
    aggregated AS (
        SELECT 
            document_id,
            chunk_id,
            content,
            metadata,
            AVG(similarity) AS avg_similarity,
            MAX(similarity) AS max_similarity
        FROM individual_searches
        GROUP BY document_id, chunk_id, content, metadata
    )
    SELECT 
        document_id,
        chunk_id,
        content,
        avg_similarity,
        max_similarity,
        metadata
    FROM aggregated
    ORDER BY 
        CASE 
            WHEN aggregation_method = 'average' THEN avg_similarity
            WHEN aggregation_method = 'max' THEN max_similarity
            ELSE avg_similarity
        END DESC
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;
```

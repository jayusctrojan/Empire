## 10.10 Milestone 6: LightRAG Integration via HTTP

### 10.7.1 Objectives
- Implement HTTP wrapper for LightRAG API
- Extract entities and relationships
- Build knowledge graphs
- Query graph structures
- Integrate with RAG pipeline
- Handle graph updates and maintenance

### 10.7.2 Complete LightRAG HTTP Integration

```json
{
  "name": "LightRAG_Integration_v7_Complete",
  "nodes": [
    {
      "parameters": {
        "method": "POST",
        "url": "https://lightrag-api.example.com/v1/extract",
        "authentication": "predefinedCredentialType",
        "nodeCredentialType": "httpHeaderAuth",
        "sendHeaders": true,
        "headerParameters": {
          "parameters": [
            {
              "name": "Authorization",
              "value": "Bearer {{ $credentials.lightragApiKey }}"
            },
            {
              "name": "Content-Type",
              "value": "application/json"
            }
          ]
        },
        "sendBody": true,
        "specifyBody": "json",
        "jsonBody": "={{ {\n  \"text\": $json.content,\n  \"document_id\": $json.document_id,\n  \"options\": {\n    \"extract_entities\": true,\n    \"extract_relationships\": true,\n    \"extract_claims\": true,\n    \"confidence_threshold\": 0.7,\n    \"max_entities\": 100,\n    \"max_relationships\": 200\n  }\n} }}",
        "options": {
          "timeout": 30000,
          "retry": {
            "maxTries": 3,
            "waitBetweenTries": 2000
          }
        }
      },
      "name": "LightRAG Extract Entities",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [450, 300],
      "id": "lightrag_extract_501",
      "notes": "Extract entities and relationships from text using LightRAG API"
    },
    {
      "parameters": {
        "language": "javaScript",
        "jsCode": "// Process LightRAG extraction results\nconst extraction = $json;\nconst documentId = $node['Previous'].json.document_id;\n\n// Validate extraction results\nif (!extraction.entities || !extraction.relationships) {\n  throw new Error('Invalid extraction results from LightRAG');\n}\n\n// Process entities\nconst processedEntities = extraction.entities.map((entity, index) => ({\n  id: `${documentId}_entity_${index}`,\n  name: entity.name,\n  type: entity.type,\n  confidence: entity.confidence || 0.5,\n  attributes: entity.attributes || {},\n  mentions: entity.mentions || [],\n  document_id: documentId,\n  created_at: new Date().toISOString()\n}));\n\n// Process relationships\nconst processedRelationships = extraction.relationships.map((rel, index) => ({\n  id: `${documentId}_rel_${index}`,\n  source_entity: rel.source,\n  target_entity: rel.target,\n  relationship_type: rel.type,\n  confidence: rel.confidence || 0.5,\n  attributes: rel.attributes || {},\n  document_id: documentId,\n  created_at: new Date().toISOString()\n}));\n\n// Process claims if available\nconst processedClaims = (extraction.claims || []).map((claim, index) => ({\n  id: `${documentId}_claim_${index}`,\n  subject: claim.subject,\n  predicate: claim.predicate,\n  object: claim.object,\n  confidence: claim.confidence || 0.5,\n  evidence: claim.evidence || '',\n  document_id: documentId,\n  created_at: new Date().toISOString()\n}));\n\n// Calculate graph statistics\nconst stats = {\n  entity_count: processedEntities.length,\n  relationship_count: processedRelationships.length,\n  claim_count: processedClaims.length,\n  unique_entity_types: [...new Set(processedEntities.map(e => e.type))],\n  unique_relationship_types: [...new Set(processedRelationships.map(r => r.relationship_type))],\n  avg_confidence: {\n    entities: processedEntities.reduce((sum, e) => sum + e.confidence, 0) / processedEntities.length,\n    relationships: processedRelationships.reduce((sum, r) => sum + r.confidence, 0) / processedRelationships.length\n  }\n};\n\nreturn [{\n  json: {\n    document_id: documentId,\n    entities: processedEntities,\n    relationships: processedRelationships,\n    claims: processedClaims,\n    statistics: stats,\n    timestamp: new Date().toISOString()\n  }\n}];"
      },
      "name": "Process Extraction Results",
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [650, 300],
      "id": "process_extraction_502"
    },
    {
      "parameters": {
        "method": "POST",
        "url": "https://lightrag-api.example.com/v1/graph/upsert",
        "authentication": "predefinedCredentialType",
        "nodeCredentialType": "httpHeaderAuth",
        "sendHeaders": true,
        "headerParameters": {
          "parameters": [
            {
              "name": "Authorization",
              "value": "Bearer {{ $credentials.lightragApiKey }}"
            }
          ]
        },
        "sendBody": true,
        "specifyBody": "json",
        "jsonBody": "={{ {\n  \"entities\": $json.entities,\n  \"relationships\": $json.relationships,\n  \"claims\": $json.claims,\n  \"document_id\": $json.document_id,\n  \"merge_strategy\": \"upsert\",\n  \"update_embeddings\": true\n} }}"
      },
      "name": "Update Knowledge Graph",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [850, 300],
      "id": "update_graph_503"
    },
    {
      "parameters": {
        "method": "POST",
        "url": "https://lightrag-api.example.com/v1/graph/query",
        "authentication": "predefinedCredentialType",
        "nodeCredentialType": "httpHeaderAuth",
        "sendBody": true,
        "specifyBody": "json",
        "jsonBody": "={{ {\n  \"query\": $json.query,\n  \"query_type\": \"natural_language\",\n  \"max_depth\": 3,\n  \"max_results\": 20,\n  \"include_embeddings\": false,\n  \"filters\": {\n    \"entity_types\": [],\n    \"relationship_types\": [],\n    \"confidence_threshold\": 0.6\n  }\n} }}"
      },
      "name": "Query Knowledge Graph",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [1050, 300],
      "id": "query_graph_504"
    }
  ]
}
```

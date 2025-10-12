# Appendix B - Technical Specifications

## B.1 Hardware Specifications

### Mac Mini M4 Configuration
- **Processor:** Apple M4 chip (10-core CPU, 10-core GPU)
- **Memory:** 24GB unified memory
- **Storage:** 512GB SSD
- **Network:** 10Gb Ethernet
- **Ports:** 2x Thunderbolt 4, 2x USB-A, HDMI 2.1
- **Power:** 39W active, 7W idle

## B.2 Software Stack

### Operating System
- macOS 15.0 (Sequoia) or later
- Python 3.11.x
- Node.js 20.x LTS
- Docker Desktop 24.0+

### Core Services
- mem-agent MCP Server
- Claude Desktop with MCP
- n8n (via Render)
- CrewAI (via Render)

## B.3 API Specifications

### REST API Endpoints
```
POST /api/v1/document/process
GET  /api/v1/document/{id}
POST /api/v1/search/query
GET  /api/v1/status/health
```

### WebSocket Events
```
connect
document.processing
document.completed
error
disconnect
```

## B.4 Database Schemas

### PostgreSQL (Supabase)
```sql
CREATE TABLE documents (
    id UUID PRIMARY KEY,
    title TEXT,
    content TEXT,
    metadata JSONB,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE TABLE processing_jobs (
    id UUID PRIMARY KEY,
    document_id UUID,
    status VARCHAR(50),
    progress INTEGER,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);
```

### Vector Database (Pinecone)
```json
{
  "vectors": {
    "id": "string",
    "values": [0.1, 0.2, ...],
    "metadata": {
      "document_id": "uuid",
      "chunk_index": 0,
      "text": "string"
    }
  }
}
```
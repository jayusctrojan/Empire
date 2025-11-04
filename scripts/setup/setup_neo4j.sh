#!/bin/bash

# ============================================================================
# Empire AI v7.2 - Neo4j Setup Script
# ============================================================================
# This script initializes the Neo4j graph database with the complete schema
# ============================================================================

echo "🚀 Empire AI v7.2 - Neo4j Setup"
echo "================================"
echo ""

# Navigate to project root
cd "$(dirname "$0")/../.." || exit 1

# Check if Neo4j container is running
if ! docker ps | grep -q empire-neo4j; then
    echo "❌ Error: Neo4j container is not running"
    echo "   Please start it with: docker-compose -f config/docker/docker-compose.yml up -d"
    exit 1
fi

echo "✅ Neo4j container is running"
echo ""

# Execute the Cypher schema
echo "📝 Applying Neo4j schema..."
echo ""

docker exec -i empire-neo4j cypher-shell \
    -u neo4j \
    -p empiresecure123 \
    -d neo4j \
    < config/schemas/neo4j_schema.cypher

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Schema applied successfully!"
    echo ""
    echo "Next steps:"
    echo "1. Open Neo4j Browser: http://localhost:7474"
    echo "2. Login with:"
    echo "   Username: neo4j"
    echo "   Password: empiresecure123"
    echo "3. Verify schema with: CALL db.constraints()"
    echo "4. Check indexes with: CALL db.indexes()"
else
    echo ""
    echo "❌ Error applying schema"
    echo "   Please check the error messages above"
    exit 1
fi

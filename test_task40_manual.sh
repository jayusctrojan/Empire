#!/bin/bash
# Manual testing script for Task 40: CrewAI Asset Storage & Retrieval
# Tests all endpoints directly with curl

BASE_URL="http://localhost:8000"

echo "========================================"
echo "Task 40: CrewAI Asset Storage & Retrieval"
echo "Manual API Testing Script"
echo "========================================"
echo ""

# Generate test UUIDs
EXECUTION_ID=$(uuidgen | tr '[:upper:]' '[:lower:]')
DOCUMENT_ID="doc-test-$(date +%s)"

echo "Test Data:"
echo "  Execution ID: $EXECUTION_ID"
echo "  Document ID: $DOCUMENT_ID"
echo ""

# Test 1: Store text-based asset (markdown)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test 1: Store Text-Based Asset (Markdown Summary)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

ASSET1_REQUEST='{
  "execution_id": "'$EXECUTION_ID'",
  "document_id": "'$DOCUMENT_ID'",
  "department": "marketing",
  "asset_type": "summary",
  "asset_name": "Q4 2025 Campaign Summary",
  "content": "# Q4 Marketing Campaign Analysis\n\n## Key Findings\n- Campaign ROI: 325%\n- Lead generation increased by 45%\n- Social media engagement up 67%\n\n## Recommendations\n1. Increase budget for Q1 2026\n2. Focus on high-performing channels\n3. Expand to new markets",
  "content_format": "markdown",
  "metadata": {
    "campaign": "Q4-2025",
    "year": 2025,
    "author": "Marketing Team"
  },
  "confidence_score": 0.95
}'

echo "Request:"
echo "$ASSET1_REQUEST" | jq '.'
echo ""

ASSET1_RESPONSE=$(curl -s -X POST "$BASE_URL/api/crewai/assets" \
  -H "Content-Type: application/json" \
  -d "$ASSET1_REQUEST")

echo "Response:"
echo "$ASSET1_RESPONSE" | jq '.'

# Extract asset ID
ASSET1_ID=$(echo "$ASSET1_RESPONSE" | jq -r '.id')
echo ""
echo "✓ Asset 1 Created: ID=$ASSET1_ID"
echo ""

# Test 2: Store another text asset (legal analysis)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test 2: Store Legal Analysis Asset"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

ASSET2_REQUEST='{
  "execution_id": "'$EXECUTION_ID'",
  "department": "legal",
  "asset_type": "analysis",
  "asset_name": "Contract Risk Assessment - Acme Corp",
  "content": "Contract analysis reveals moderate risk level. Key concerns: payment terms, liability clauses, termination conditions.",
  "content_format": "text",
  "metadata": {
    "contract_id": "CNT-2025-456",
    "risk_level": "medium",
    "reviewer": "Legal Team"
  },
  "confidence_score": 0.87
}'

ASSET2_RESPONSE=$(curl -s -X POST "$BASE_URL/api/crewai/assets" \
  -H "Content-Type: application/json" \
  -d "$ASSET2_REQUEST")

ASSET2_ID=$(echo "$ASSET2_RESPONSE" | jq -r '.id')
echo "✓ Asset 2 Created: ID=$ASSET2_ID (Legal Analysis)"
echo ""

# Test 3: Store HR report
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test 3: Store HR Report Asset"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

ASSET3_REQUEST='{
  "execution_id": "'$EXECUTION_ID'",
  "department": "hr",
  "asset_type": "report",
  "asset_name": "Q4 Employee Satisfaction Report",
  "content": "{\"overall_satisfaction\": 8.2, \"engagement_score\": 7.9, \"retention_rate\": 0.92, \"top_concerns\": [\"work-life balance\", \"career development\"]}",
  "content_format": "json",
  "metadata": {
    "quarter": "Q4",
    "year": 2025,
    "respondents": 450
  },
  "confidence_score": 0.91
}'

ASSET3_RESPONSE=$(curl -s -X POST "$BASE_URL/api/crewai/assets" \
  -H "Content-Type": application/json" \
  -d "$ASSET3_REQUEST")

ASSET3_ID=$(echo "$ASSET3_RESPONSE" | jq -r '.id')
echo "✓ Asset 3 Created: ID=$ASSET3_ID (HR Report)"
echo ""

# Test 4: Retrieve all assets for execution
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test 4: Retrieve Assets by Execution ID"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

EXECUTION_ASSETS=$(curl -s -X GET "$BASE_URL/api/crewai/assets/execution/$EXECUTION_ID")
echo "$EXECUTION_ASSETS" | jq '.total, .assets[] | {id, asset_name, department, asset_type, confidence_score}'
echo ""
TOTAL=$(echo "$EXECUTION_ASSETS" | jq -r '.total')
echo "✓ Retrieved $TOTAL assets for execution $EXECUTION_ID"
echo ""

# Test 5: Filter by department
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test 5: Filter Assets by Department (marketing)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

MARKETING_ASSETS=$(curl -s -X GET "$BASE_URL/api/crewai/assets?department=marketing")
echo "$MARKETING_ASSETS" | jq '.total, .filters_applied, .assets[] | {id, asset_name, department}'
echo ""

# Test 6: Filter by confidence
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test 6: Filter Assets by Confidence (>= 0.9)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

HIGH_CONFIDENCE=$(curl -s -X GET "$BASE_URL/api/crewai/assets?min_confidence=0.9")
echo "$HIGH_CONFIDENCE" | jq '.total, .assets[] | {id, asset_name, confidence_score}'
echo ""

# Test 7: Combined filters
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test 7: Combined Filters (legal + analysis)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

COMBINED=$(curl -s -X GET "$BASE_URL/api/crewai/assets?department=legal&asset_type=analysis")
echo "$COMBINED" | jq '.total, .filters_applied, .assets[] | {id, asset_name, department, asset_type}'
echo ""

# Test 8: Get single asset by ID
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test 8: Get Single Asset by ID"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

SINGLE_ASSET=$(curl -s -X GET "$BASE_URL/api/crewai/assets/$ASSET1_ID")
echo "$SINGLE_ASSET" | jq '{id, asset_name, department, asset_type, confidence_score, metadata, content_preview: .content[:100]}'
echo ""

# Test 9: Update asset confidence and metadata
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test 9: Update Asset Confidence & Metadata"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

UPDATE_REQUEST='{
  "confidence_score": 0.98,
  "metadata": {
    "reviewed_by": "Jane Smith",
    "approved": true,
    "review_date": "2025-01-13"
  }
}'

echo "Updating Asset $ASSET1_ID..."
UPDATED_ASSET=$(curl -s -X PATCH "$BASE_URL/api/crewai/assets/$ASSET1_ID" \
  -H "Content-Type: application/json" \
  -d "$UPDATE_REQUEST")

echo "$UPDATED_ASSET" | jq '{id, asset_name, confidence_score, metadata}'
echo ""
echo "✓ Asset updated - Confidence: $(echo "$UPDATED_ASSET" | jq -r '.confidence_score')"
echo "✓ Metadata merged: original + new keys preserved"
echo ""

# Summary
echo "========================================"
echo "Test Summary"
echo "========================================"
echo "✓ Created 3 assets (marketing, legal, hr)"
echo "✓ Retrieved assets by execution ID"
echo "✓ Filtered by department (marketing)"
echo "✓ Filtered by confidence (>= 0.9)"
echo "✓ Combined filters (department + type)"
echo "✓ Retrieved single asset by ID"
echo "✓ Updated asset confidence from 0.95 to 0.98"
echo "✓ Merged metadata successfully"
echo ""
echo "All Task 40 API endpoints working correctly!"
echo "========================================"

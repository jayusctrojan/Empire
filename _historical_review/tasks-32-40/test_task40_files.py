#!/usr/bin/env python3
"""
File-based asset test for Task 40: CrewAI Asset Storage & Retrieval
Tests B2 storage upload for PDF, PNG, and other binary assets
"""

import requests
import json
from io import BytesIO
from uuid import UUID
import base64

# Configuration
BASE_URL = "http://localhost:8000"
HEADERS = {"Content-Type": "application/json"}

# Use existing CrewAI execution ID from database
EXISTING_EXECUTION_ID = "8bbe2a5f-78c7-4d26-ad7d-fb4dafc8d4ee"

def create_test_pdf():
    """Create a minimal PDF file for testing"""
    # Minimal PDF structure
    pdf_content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/Resources <<
/Font <<
/F1 <<
/Type /Font
/Subtype /Type1
/BaseFont /Helvetica
>>
>>
>>
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj
4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
100 700 Td
(Test PDF Asset) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000317 00000 n
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
410
%%EOF
"""
    return pdf_content

def create_test_png():
    """Create a minimal 1x1 PNG file for testing"""
    # 1x1 transparent PNG
    png_content = base64.b64decode(
        b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )
    return png_content

def test_file_based_assets():
    print("=" * 70)
    print("Task 40: File-Based Asset Testing (B2 Storage)")
    print("=" * 70)
    print()

    # Test 1: Upload PDF asset
    print("Test 1: Upload PDF Asset to B2")
    print("-" * 70)

    pdf_data = create_test_pdf()
    pdf_base64 = base64.b64encode(pdf_data).decode('utf-8')

    asset_pdf = {
        "execution_id": EXISTING_EXECUTION_ID,
        "document_id": None,
        "department": "legal",
        "asset_type": "report",
        "asset_name": "Test Legal Contract",
        "file_content": pdf_base64,  # Base64-encoded binary
        "content_format": "pdf",
        "metadata": {
            "test": True,
            "file_type": "pdf",
            "contract_id": "CNT-2025-789"
        },
        "confidence_score": 0.92
    }

    try:
        response = requests.post(
            f"{BASE_URL}/api/crewai/assets",
            headers=HEADERS,
            json=asset_pdf,
            timeout=30
        )

        print(f"Status: {response.status_code}")

        if response.status_code == 201:
            asset = response.json()
            pdf_asset_id = asset["id"]
            print(f"✓ PDF Asset created: {pdf_asset_id}")
            print(f"  Department: {asset['department']}")
            print(f"  Type: {asset['asset_type']}")
            print(f"  B2 Path: {asset.get('b2_path', 'NULL')}")
            print(f"  File Size: {asset.get('file_size', 'NULL')} bytes")
            print(f"  MIME Type: {asset.get('mime_type', 'NULL')}")
            print(f"  Content (should be NULL): {asset.get('content', 'NULL')}")
            print()

            # Verify B2 path format
            expected_path_prefix = f"crewai/assets/legal/report/{EXISTING_EXECUTION_ID}"
            if asset.get('b2_path') and asset['b2_path'].startswith(expected_path_prefix):
                print(f"✓ B2 path format correct: {asset['b2_path']}")
            else:
                print(f"✗ B2 path format incorrect. Expected prefix: {expected_path_prefix}")
            print()

            # Verify content is NULL for file-based assets
            if asset.get('content') is None:
                print("✓ Content column is NULL (correct for file-based assets)")
            else:
                print("✗ Content column should be NULL for file-based assets")
            print()

        else:
            print(f"✗ Failed: {response.text}")
            return False

    except Exception as e:
        print(f"✗ Error: {e}")
        return False

    # Test 2: Upload PNG asset
    print("Test 2: Upload PNG Image Asset to B2")
    print("-" * 70)

    png_data = create_test_png()
    png_base64 = base64.b64encode(png_data).decode('utf-8')

    asset_png = {
        "execution_id": EXISTING_EXECUTION_ID,
        "document_id": None,
        "department": "marketing",
        "asset_type": "chart",
        "asset_name": "Test ROI Chart",
        "file_content": png_base64,
        "content_format": "png",
        "metadata": {
            "test": True,
            "chart_type": "bar",
            "campaign": "Q4-2025"
        },
        "confidence_score": 0.89
    }

    try:
        response = requests.post(
            f"{BASE_URL}/api/crewai/assets",
            headers=HEADERS,
            json=asset_png,
            timeout=30
        )

        print(f"Status: {response.status_code}")

        if response.status_code == 201:
            asset = response.json()
            png_asset_id = asset["id"]
            print(f"✓ PNG Asset created: {png_asset_id}")
            print(f"  Department: {asset['department']}")
            print(f"  Type: {asset['asset_type']}")
            print(f"  B2 Path: {asset.get('b2_path', 'NULL')}")
            print(f"  File Size: {asset.get('file_size', 'NULL')} bytes")
            print(f"  MIME Type: {asset.get('mime_type', 'NULL')}")
            print()

            # Verify file size matches
            if asset.get('file_size') == len(png_data):
                print(f"✓ File size matches: {len(png_data)} bytes")
            else:
                print(f"✗ File size mismatch. Expected: {len(png_data)}, Got: {asset.get('file_size')}")
            print()

        else:
            print(f"✗ Failed: {response.text}")
            return False

    except Exception as e:
        print(f"✗ Error: {e}")
        return False

    # Test 3: Retrieve file-based assets
    print("Test 3: Retrieve File-Based Assets")
    print("-" * 70)

    try:
        response = requests.get(
            f"{BASE_URL}/api/crewai/assets/execution/{EXISTING_EXECUTION_ID}",
            timeout=10
        )

        if response.status_code == 200:
            result = response.json()
            print(f"✓ Total assets for execution: {result['total']}")

            file_assets = [a for a in result['assets'] if a.get('b2_path') is not None]
            text_assets = [a for a in result['assets'] if a.get('content') is not None]

            print(f"  - File-based assets (b2_path set): {len(file_assets)}")
            print(f"  - Text-based assets (content set): {len(text_assets)}")
            print()

            print("File-based assets:")
            for asset in file_assets:
                print(f"  - {asset['asset_name']}")
                print(f"    Format: {asset['content_format']}")
                print(f"    B2 Path: {asset['b2_path']}")
                print(f"    Size: {asset.get('file_size', 'N/A')} bytes")
                print()

        else:
            print(f"✗ Failed: {response.text}")

    except Exception as e:
        print(f"✗ Error: {e}")

    # Test 4: Verify B2 path organization
    print("Test 4: Verify B2 Path Organization")
    print("-" * 70)

    expected_patterns = {
        "PDF": f"crewai/assets/legal/report/{EXISTING_EXECUTION_ID}/Test Legal Contract.pdf",
        "PNG": f"crewai/assets/marketing/chart/{EXISTING_EXECUTION_ID}/Test ROI Chart.png"
    }

    try:
        # Get PDF asset
        response = requests.get(
            f"{BASE_URL}/api/crewai/assets/{pdf_asset_id}",
            timeout=10
        )

        if response.status_code == 200:
            asset = response.json()
            print(f"PDF B2 Path: {asset.get('b2_path')}")
            if asset.get('b2_path') == expected_patterns["PDF"]:
                print("✓ PDF path matches expected pattern")
            else:
                print(f"  Expected: {expected_patterns['PDF']}")
            print()

        # Get PNG asset
        response = requests.get(
            f"{BASE_URL}/api/crewai/assets/{png_asset_id}",
            timeout=10
        )

        if response.status_code == 200:
            asset = response.json()
            print(f"PNG B2 Path: {asset.get('b2_path')}")
            if asset.get('b2_path') == expected_patterns["PNG"]:
                print("✓ PNG path matches expected pattern")
            else:
                print(f"  Expected: {expected_patterns['PNG']}")
            print()

    except Exception as e:
        print(f"✗ Error: {e}")

    print("=" * 70)
    print("✓ File-Based Asset Tests Complete!")
    print("=" * 70)
    return True

if __name__ == "__main__":
    print("\nPrerequisite: FastAPI server must be running on http://localhost:8000")
    print("              B2 credentials must be configured in .env\n")

    try:
        # Quick health check
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        print(f"✓ API server is running (health check: {response.status_code})\n")
    except Exception as e:
        print(f"✗ API server not reachable: {e}\n")
        print("Please start the server with: uvicorn app.main:app --reload --port 8000\n")
        exit(1)

    success = test_file_based_assets()
    exit(0 if success else 1)

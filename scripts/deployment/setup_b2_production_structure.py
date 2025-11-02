#!/usr/bin/env python3
"""
Setup B2 Production Folder Structure for Empire v7.2

Creates production folders for each department and asset type,
plus enhanced suggestions structure with Prompts and Workflows.
"""

import os
from b2sdk.v2 import B2Api, InMemoryAccountInfo
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# 10 Business Departments
DEPARTMENTS = [
    "it-engineering",
    "sales-marketing",
    "customer-support",
    "operations-hr-supply",
    "finance-accounting",
    "project-management",
    "real-estate",
    "private-equity-ma",
    "consulting",
    "personal-continuing-ed"
]

# Asset types for suggestions (drafts + approved)
SUGGESTION_ASSET_TYPES = [
    "claude-skills",      # YAML skill definitions
    "claude-commands",    # Markdown slash commands
    "agents",            # CrewAI agent definitions
    "prompts",           # AI prompts and templates (NEW)
    "workflows"          # n8n workflow definitions (NEW)
]

# Asset types for production
PRODUCTION_ASSET_TYPES = [
    "claude-skills",
    "claude-commands",
    "crewai-agents",     # Note: renamed from "agents" for clarity
    "prompts",
    "workflows"
]


def setup_b2_production_structure():
    """Create complete B2 folder structure"""

    print("🚀 Setting up B2 Production Structure for Empire v7.2\n")

    # Initialize B2
    info = InMemoryAccountInfo()
    b2_api = B2Api(info)
    b2_api.authorize_account(
        "production",
        os.getenv("B2_APPLICATION_KEY_ID"),
        os.getenv("B2_APPLICATION_KEY")
    )

    bucket = b2_api.get_bucket_by_name("JB-Course-KB")
    print(f"✅ Connected to bucket: {bucket.name}\n")

    folders_created = []

    # ================================================================
    # 1. ENHANCED SUGGESTIONS STRUCTURE (with Prompts and Workflows)
    # ================================================================
    print("📁 Creating enhanced suggestions structure...\n")

    for asset_type in SUGGESTION_ASSET_TYPES:
        for stage in ["drafts", "approved"]:
            folder_path = f"processed/crewai-suggestions/{asset_type}/{stage}/.keep"
            try:
                bucket.upload_bytes(data_bytes=b"", file_name=folder_path)
                folders_created.append(folder_path.replace("/.keep", ""))
                print(f"   ✓ {folder_path.replace('/.keep', '')}")
            except Exception as e:
                if "duplicate" in str(e).lower():
                    print(f"   ⊙ {folder_path.replace('/.keep', '')} (exists)")
                else:
                    print(f"   ✗ Error creating {folder_path}: {e}")

    print()

    # ================================================================
    # 2. PRODUCTION FOLDER STRUCTURE (Department-based)
    # ================================================================
    print("📁 Creating production folder structure with 10 departments...\n")

    for dept in DEPARTMENTS:
        print(f"🏢 Department: {dept}")

        for asset_type in PRODUCTION_ASSET_TYPES:
            folder_path = f"production/{dept}/{asset_type}/.keep"
            try:
                bucket.upload_bytes(data_bytes=b"", file_name=folder_path)
                folders_created.append(folder_path.replace("/.keep", ""))
                print(f"   ✓ {asset_type}/")
            except Exception as e:
                if "duplicate" in str(e).lower():
                    print(f"   ⊙ {asset_type}/ (exists)")
                else:
                    print(f"   ✗ Error creating {folder_path}: {e}")

        print()

    # ================================================================
    # 3. GLOBAL PRODUCTION ASSETS (Cross-department)
    # ================================================================
    print("📁 Creating global production assets folder...\n")

    for asset_type in PRODUCTION_ASSET_TYPES:
        folder_path = f"production/_global/{asset_type}/.keep"
        try:
            bucket.upload_bytes(data_bytes=b"", file_name=folder_path)
            folders_created.append(folder_path.replace("/.keep", ""))
            print(f"   ✓ _global/{asset_type}/")
        except Exception as e:
            if "duplicate" in str(e).lower():
                print(f"   ⊙ _global/{asset_type}/ (exists)")
            else:
                print(f"   ✗ Error creating {folder_path}: {e}")

    print()

    # ================================================================
    # 4. PRODUCTION VERSIONS (Backup/Rollback)
    # ================================================================
    print("📁 Creating production versions folder for rollback...\n")

    versions_path = "production/_versions/.keep"
    try:
        bucket.upload_bytes(data_bytes=b"", file_name=versions_path)
        folders_created.append(versions_path.replace("/.keep", ""))
        print(f"   ✓ production/_versions/")
    except Exception as e:
        if "duplicate" in str(e).lower():
            print(f"   ⊙ production/_versions/ (exists)")
        else:
            print(f"   ✗ Error creating {versions_path}: {e}")

    print()

    # ================================================================
    # SUMMARY
    # ================================================================
    print("=" * 70)
    print(f"✅ B2 Production Structure Setup Complete!")
    print("=" * 70)
    print(f"\nTotal folders created: {len(folders_created)}")
    print(f"\nStructure:")
    print(f"  • Suggestions: {len(SUGGESTION_ASSET_TYPES)} asset types × 2 stages = {len(SUGGESTION_ASSET_TYPES) * 2} folders")
    print(f"  • Production: {len(DEPARTMENTS)} departments × {len(PRODUCTION_ASSET_TYPES)} assets = {len(DEPARTMENTS) * len(PRODUCTION_ASSET_TYPES)} folders")
    print(f"  • Global: {len(PRODUCTION_ASSET_TYPES)} asset types")
    print(f"  • Versions: 1 folder for rollback")
    print(f"\n📊 Expected total: {len(SUGGESTION_ASSET_TYPES) * 2 + len(DEPARTMENTS) * len(PRODUCTION_ASSET_TYPES) + len(PRODUCTION_ASSET_TYPES) + 1} folders")
    print(f"📊 Actually created: {len(folders_created)} folders")

    print("\n🎯 Next steps:")
    print("  1. CrewAI generates suggestions → drafts/")
    print("  2. Review and test → Move to approved/")
    print("  3. Ready for production → Run promotion script")
    print("  4. n8n workflows read from production/{department}/")
    print("\n💡 Use scripts/promote_to_production.py to promote approved assets")


if __name__ == "__main__":
    setup_b2_production_structure()

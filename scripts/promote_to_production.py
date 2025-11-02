#!/usr/bin/env python3
"""
Promotion Script for Empire v7.2

Promotes approved CrewAI suggestions to production folders.
Supports versioning and rollback capabilities.
"""

import os
import sys
from datetime import datetime
from typing import Optional
from b2sdk.v2 import B2Api, InMemoryAccountInfo
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

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

ASSET_TYPE_MAPPING = {
    "claude-skills": "claude-skills",
    "claude-commands": "claude-commands",
    "agents": "crewai-agents",  # Rename for production
    "prompts": "prompts",
    "workflows": "workflows"
}


class ProductionPromoter:
    """Manages promotion of approved assets to production"""

    def __init__(self):
        # Initialize B2
        info = InMemoryAccountInfo()
        self.b2_api = B2Api(info)
        self.b2_api.authorize_account(
            "production",
            os.getenv("B2_APPLICATION_KEY_ID"),
            os.getenv("B2_APPLICATION_KEY")
        )
        self.bucket = self.b2_api.get_bucket_by_name("JB-Course-KB")
        print(f"✅ Connected to bucket: {self.bucket.name}\n")

    def list_approved_assets(self, asset_type: str):
        """List all approved assets of a given type"""
        prefix = f"processed/crewai-suggestions/{asset_type}/approved/"

        print(f"📋 Approved {asset_type}:\n")

        files = []
        for file_version, folder_name in self.bucket.ls(folder_to_list=prefix):
            if file_version and file_version.file_name != prefix + ".keep":
                filename = file_version.file_name.replace(prefix, "")
                files.append({
                    "filename": filename,
                    "full_path": file_version.file_name,
                    "size": file_version.size,
                    "uploaded": datetime.fromtimestamp(file_version.upload_timestamp / 1000)
                })

        if not files:
            print(f"   (No approved {asset_type} found)")
            return []

        for i, file in enumerate(files, 1):
            print(f"   {i}. {file['filename']}")
            print(f"      Size: {file['size']} bytes | Uploaded: {file['uploaded']}")

        print()
        return files

    def backup_existing_production(self, dest_path: str, department: str, asset_name: str):
        """Backup existing production file before overwriting"""
        try:
            # Check if file exists in production
            existing_file = None
            for file_version, _ in self.bucket.ls(folder_to_list=dest_path):
                if file_version and file_version.file_name == dest_path:
                    existing_file = file_version
                    break

            if not existing_file:
                return  # No existing file to backup

            # Create versioned backup
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"production/_versions/{department}/{asset_name}.{timestamp}.backup"

            # Download existing file
            download_dest = self.bucket.download_file_by_id(existing_file.id_)
            file_content = download_dest.save_to_bytes()

            # Upload to versions folder
            self.bucket.upload_bytes(
                data_bytes=file_content,
                file_name=backup_path
            )

            print(f"   💾 Backed up existing version to: {backup_path}")

        except Exception as e:
            print(f"   ⚠️  Warning: Could not backup existing file: {e}")

    def extract_department_from_filename(self, filename: str):
        """
        Extract department from filename

        Expected format: {department}_{asset-name}.{ext}
        Example: sales-marketing_proposal-generator.yaml

        Returns: (department, clean_filename, is_global)
        """
        if filename.startswith("_global_"):
            # Global asset
            clean_name = filename.replace("_global_", "", 1)
            return ("_global", clean_name, True)

        # Check for department prefix
        for dept in DEPARTMENTS:
            if filename.startswith(f"{dept}_"):
                clean_name = filename.replace(f"{dept}_", "", 1)
                return (dept, clean_name, False)

        # No department prefix found
        return (None, filename, False)

    def promote_asset(
        self,
        asset_type: str,
        filename: str,
        department: str = None,
        is_global: bool = False
    ):
        """Promote an approved asset to production"""

        print(f"\n{'='*70}")
        print(f"🚀 Promoting: {filename}")
        print(f"{'='*70}\n")

        # Auto-extract department from filename if not provided
        extracted_dept, clean_filename, extracted_is_global = self.extract_department_from_filename(filename)

        if extracted_dept and not department:
            department = extracted_dept
            is_global = extracted_is_global
            print(f"✅ Auto-detected department from filename: {department}")
            print(f"📝 Clean filename: {clean_filename}\n")
        else:
            clean_filename = filename

        if not department:
            print("❌ Error: Could not determine department from filename")
            print("   Expected format: {department}_{name}.{ext}")
            print("   Example: sales-marketing_proposal-generator.yaml")
            return False

        # Source path (approved)
        source_path = f"processed/crewai-suggestions/{asset_type}/approved/{filename}"

        # Destination path (production) - uses clean filename without department prefix
        production_asset_type = ASSET_TYPE_MAPPING.get(asset_type, asset_type)

        if is_global:
            dest_path = f"production/_global/{production_asset_type}/{clean_filename}"
            location = "_global"
        else:
            dest_path = f"production/{department}/{production_asset_type}/{clean_filename}"
            location = department

        print(f"📂 Source: {source_path}")
        print(f"📂 Destination: {dest_path}")
        print(f"🏢 Location: {location}")
        print()

        try:
            # Step 1: Backup existing production file if it exists
            self.backup_existing_production(dest_path, location, filename)

            # Step 2: Get source file
            source_file = None
            for file_version, _ in self.bucket.ls(folder_to_list=source_path):
                if file_version and file_version.file_name == source_path:
                    source_file = file_version
                    break

            if not source_file:
                print(f"❌ Error: Source file not found: {source_path}")
                return False

            # Step 3: Download source file
            download_dest = self.bucket.download_file_by_id(source_file.id_)
            file_content = download_dest.save_to_bytes()

            # Step 4: Upload to production with metadata
            metadata = {
                "promoted_from": source_path,
                "promoted_at": datetime.now().isoformat(),
                "department": location,
                "asset_type": production_asset_type,
                "original_size": str(source_file.size)
            }

            self.bucket.upload_bytes(
                data_bytes=file_content,
                file_name=dest_path,
                file_infos=metadata
            )

            print(f"✅ Successfully promoted to production!")
            print(f"📊 Size: {len(file_content)} bytes")
            print(f"🏷️  Metadata: {json.dumps(metadata, indent=2)}")

            return True

        except Exception as e:
            print(f"❌ Error promoting asset: {e}")
            return False

    def interactive_promotion(self):
        """Interactive CLI for promoting assets"""

        print("=" * 70)
        print("🎯 Empire v7.2 - Production Promotion Tool")
        print("=" * 70)
        print()

        # Step 1: Select asset type
        print("Select asset type to promote:\n")
        asset_types = list(ASSET_TYPE_MAPPING.keys())
        for i, at in enumerate(asset_types, 1):
            print(f"   {i}. {at}")
        print()

        choice = input("Enter number (or 'q' to quit): ").strip()
        if choice.lower() == 'q':
            print("👋 Exiting...")
            return

        try:
            asset_type = asset_types[int(choice) - 1]
        except (ValueError, IndexError):
            print("❌ Invalid choice")
            return

        print()

        # Step 2: List approved assets
        approved_files = self.list_approved_assets(asset_type)

        if not approved_files:
            print("No approved assets to promote. Exiting.")
            return

        # Step 3: Select file to promote
        file_choice = input("Enter file number to promote (or 'q' to quit): ").strip()
        if file_choice.lower() == 'q':
            print("👋 Exiting...")
            return

        try:
            selected_file = approved_files[int(file_choice) - 1]
        except (ValueError, IndexError):
            print("❌ Invalid choice")
            return

        print()

        # Step 4: Auto-detect department from filename or ask
        filename = selected_file['filename']
        extracted_dept, clean_filename, extracted_is_global = self.extract_department_from_filename(filename)

        if extracted_dept:
            print(f"✅ Auto-detected department from filename: {extracted_dept}")
            print(f"📝 Production filename will be: {clean_filename}")
            print()

            # Ask for confirmation or override
            use_auto = input(f"Use auto-detected department '{extracted_dept}'? (yes/no/override): ").strip().lower()

            if use_auto == "yes":
                department = extracted_dept
                is_global = extracted_is_global
            elif use_auto == "override":
                # Manual selection
                print("\nSelect destination:\n")
                print("   0. _global (cross-department)")
                for i, dept in enumerate(DEPARTMENTS, 1):
                    print(f"   {i}. {dept}")
                print()

                dest_choice = input("Enter number: ").strip()

                try:
                    if dest_choice == "0":
                        is_global = True
                        department = "_global"
                    else:
                        is_global = False
                        department = DEPARTMENTS[int(dest_choice) - 1]
                except (ValueError, IndexError):
                    print("❌ Invalid choice")
                    return
            else:
                print("❌ Cancelled")
                return
        else:
            # No department in filename - ask user
            print("⚠️  No department prefix found in filename")
            print("   Expected format: {department}_{name}.{ext}")
            print("   Example: sales-marketing_proposal-generator.yaml")
            print()
            print("Select destination:\n")
            print("   0. _global (cross-department)")
            for i, dept in enumerate(DEPARTMENTS, 1):
                print(f"   {i}. {dept}")
            print()

            dest_choice = input("Enter number: ").strip()

            try:
                if dest_choice == "0":
                    is_global = True
                    department = "_global"
                else:
                    is_global = False
                    department = DEPARTMENTS[int(dest_choice) - 1]
            except (ValueError, IndexError):
                print("❌ Invalid choice")
                return

        # Step 5: Confirm and promote
        print()
        print(f"⚠️  About to promote:")
        print(f"   Source file: {filename}")
        if extracted_dept:
            print(f"   Production file: {clean_filename}")
        print(f"   Type: {asset_type} → {ASSET_TYPE_MAPPING[asset_type]}")
        print(f"   Destination: production/{department}/{ASSET_TYPE_MAPPING[asset_type]}/")
        print()

        confirm = input("Proceed? (yes/no): ").strip().lower()
        if confirm != "yes":
            print("❌ Cancelled")
            return

        # Promote!
        success = self.promote_asset(
            asset_type=asset_type,
            filename=filename,
            department=department,
            is_global=is_global
        )

        if success:
            final_filename = clean_filename if extracted_dept else filename
            print("\n🎉 Promotion complete!")
            print(f"🔗 Production path: production/{department}/{ASSET_TYPE_MAPPING[asset_type]}/{final_filename}")
            print(f"📚 Your n8n workflows can now read from this location")


def main():
    """Main entry point"""

    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("Usage:")
        print("  python promote_to_production.py              # Interactive mode")
        print("  python promote_to_production.py --help       # Show this help")
        return

    promoter = ProductionPromoter()
    promoter.interactive_promotion()


if __name__ == "__main__":
    main()

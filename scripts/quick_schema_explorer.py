"""
Quick Notion Database Schema Explorer

Fetches just 1-2 sample pages from each configured database to understand schemas.

Usage:
    python scripts/quick_schema_explorer.py
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
from typing import Any, Dict
from datetime import datetime

from loguru import logger
from config import get_settings
from src.sync.notion_client import NotionClient


def analyze_page_schema(page: Dict[str, Any]) -> Dict[str, str]:
    """Extract property schema from a single page."""
    properties = page.get("properties", {})
    schema = {}

    for prop_name, prop_data in properties.items():
        prop_type = prop_data.get("type", "unknown")
        schema[prop_name] = prop_type

    return schema


def analyze_database_quick(client: NotionClient, db_id: str, db_name: str) -> Dict[str, Any]:
    """
    Quickly analyze a database by fetching just the first page.

    Returns schema info without fetching all pages.
    """
    logger.info(f"Analyzing {db_name} database ({db_id})...")

    try:
        # Use the internal query method with page_size=1
        response = client._query_any_database(db_id)

        results = response.get("results", [])

        if not results:
            logger.warning(f"No pages found in {db_name} database")
            return {
                "database_name": db_name,
                "database_id": db_id,
                "schema": {},
                "error": "No pages found (database may be empty or not shared with integration)"
            }

        # Just analyze the first page
        first_page = results[0]
        schema = analyze_page_schema(first_page)

        logger.info(f"✓ Found {len(schema)} properties in {db_name}")

        return {
            "database_name": db_name,
            "database_id": db_id,
            "schema": schema,
            "error": None
        }

    except Exception as e:
        logger.error(f"Failed to analyze {db_name}: {e}")
        return {
            "database_name": db_name,
            "database_id": db_id,
            "schema": {},
            "error": str(e)
        }


def main():
    """Main execution function."""
    logger.info("Starting Quick Notion Database Schema Explorer")

    # Initialize settings and client
    settings = get_settings()
    client = NotionClient(api_key=settings.notion_api_key)

    if not client.ready:
        logger.error("Notion client not ready. Check NOTION_API_KEY in .env")
        return

    # Get all configured databases from .env
    databases = {
        "Flashcards": settings.flashcards_db_id,
        "Superconcepts": settings.superconcepts_db_id,
        "Subconcepts": settings.subconcepts_db_id,
        "Concepts": settings.concepts_db_id,
        "Modules": settings.modules_db_id,
        "Tracks": settings.tracks_db_id,
        "Quizzes": settings.quizzes_db_id,
        "Mental Models": settings.mental_models_db_id,
        "Resources": settings.resources_db_id,
    }

    # Filter out None values
    configured_dbs = {name: db_id for name, db_id in databases.items() if db_id}

    logger.info(f"Found {len(configured_dbs)} configured databases")

    # Analyze each database
    all_analyses = []
    for db_name, db_id in configured_dbs.items():
        analysis = analyze_database_quick(client, db_id, db_name)
        all_analyses.append(analysis)

    # Generate output
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 1. Save JSON output FIRST (before printing to console)
    json_output_path = Path(__file__).parent.parent / f"notion_schema_{timestamp}.json"
    with open(json_output_path, "w", encoding="utf-8") as f:
        json.dump(all_analyses, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved detailed JSON to: {json_output_path}")

    # 2. Print to console (using safe encoding)
    print("\n\n", file=sys.stdout, flush=True)
    print("=" * 80)
    print("NOTION DATABASE SCHEMA ANALYSIS")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print("\n")

    for analysis in all_analyses:
        print(f"\nDATABASE: {analysis['database_name']}")
        print("-" * 80)
        print(f"Database ID: {analysis['database_id']}")

        if analysis['error']:
            print(f"ERROR: {analysis['error']}")
        else:
            print(f"\nProperties ({len(analysis['schema'])}):")
            for prop_name, prop_type in sorted(analysis['schema'].items()):
                # Use repr to safely handle Unicode characters
                safe_prop_name = prop_name.encode('ascii', 'replace').decode('ascii')
                print(f"  - {safe_prop_name:50s} [{prop_type}]")

    # 3. Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Databases Analyzed: {len(all_analyses)}")
    print(f"Databases with Data: {sum(1 for a in all_analyses if not a['error'])}")
    print(f"Output File: {json_output_path}")
    print("=" * 80)

    logger.info("Schema exploration complete!")


if __name__ == "__main__":
    main()

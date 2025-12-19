"""
Notion Database Schema Explorer

This script connects to all configured Notion databases, fetches sample pages,
and extracts their property schemas for analysis and documentation.

Usage:
    python scripts/explore_notion_schemas.py
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
from datetime import datetime
from typing import Any

from loguru import logger

from config import get_settings
from src.sync.notion_client import NotionClient


def extract_property_schema(page: dict[str, Any]) -> dict[str, str]:
    """
    Extract property names and types from a Notion page.

    Args:
        page: Raw Notion page dictionary

    Returns:
        Dictionary mapping property name to property type
    """
    properties = page.get("properties", {})
    schema = {}

    for prop_name, prop_data in properties.items():
        prop_type = prop_data.get("type", "unknown")
        schema[prop_name] = prop_type

    return schema


def get_property_value_sample(page: dict[str, Any], prop_name: str) -> Any:
    """
    Extract a sample value from a property to understand its structure.

    Args:
        page: Raw Notion page dictionary
        prop_name: Property name to extract

    Returns:
        Sample value or description of the property
    """
    properties = page.get("properties", {})
    prop_data = properties.get(prop_name, {})
    prop_type = prop_data.get("type", "unknown")

    # Extract value based on type
    if prop_type == "title":
        title_array = prop_data.get("title", [])
        if title_array:
            return title_array[0].get("plain_text", "")
        return ""

    elif prop_type == "rich_text":
        rich_text_array = prop_data.get("rich_text", [])
        if rich_text_array:
            return rich_text_array[0].get("plain_text", "")
        return ""

    elif prop_type == "number":
        return prop_data.get("number")

    elif prop_type == "select":
        select_obj = prop_data.get("select")
        if select_obj:
            return select_obj.get("name")
        return None

    elif prop_type == "multi_select":
        multi_select_array = prop_data.get("multi_select", [])
        return [item.get("name") for item in multi_select_array]

    elif prop_type == "date":
        date_obj = prop_data.get("date")
        if date_obj:
            return date_obj.get("start")
        return None

    elif prop_type == "checkbox":
        return prop_data.get("checkbox")

    elif prop_type == "url":
        return prop_data.get("url")

    elif prop_type == "email":
        return prop_data.get("email")

    elif prop_type == "phone_number":
        return prop_data.get("phone_number")

    elif prop_type == "formula":
        formula_obj = prop_data.get("formula", {})
        return f"<formula: {formula_obj.get('type')}>"

    elif prop_type == "relation":
        relation_array = prop_data.get("relation", [])
        return f"<{len(relation_array)} relations>"

    elif prop_type == "rollup":
        rollup_obj = prop_data.get("rollup", {})
        return f"<rollup: {rollup_obj.get('type')}>"

    elif prop_type == "people":
        people_array = prop_data.get("people", [])
        return f"<{len(people_array)} people>"

    elif prop_type == "files":
        files_array = prop_data.get("files", [])
        return f"<{len(files_array)} files>"

    elif prop_type == "created_time":
        return prop_data.get("created_time")

    elif prop_type == "created_by":
        return "<created_by user>"

    elif prop_type == "last_edited_time":
        return prop_data.get("last_edited_time")

    elif prop_type == "last_edited_by":
        return "<last_edited_by user>"

    return None


def merge_schemas(schemas: list[dict[str, str]]) -> dict[str, str]:
    """
    Merge multiple page schemas into one unified schema.

    Args:
        schemas: List of schema dictionaries

    Returns:
        Merged schema with all unique properties
    """
    merged = {}
    for schema in schemas:
        for prop_name, prop_type in schema.items():
            if prop_name not in merged:
                merged[prop_name] = prop_type
            elif merged[prop_name] != prop_type:
                # Handle type conflicts (shouldn't happen in practice)
                merged[prop_name] = f"{merged[prop_name]}|{prop_type}"

    return merged


def analyze_database(
    client: NotionClient, db_id: str, db_name: str, max_samples: int = 2
) -> dict[str, Any]:
    """
    Analyze a single Notion database schema.

    Args:
        client: NotionClient instance
        db_id: Database ID to analyze
        db_name: Human-readable database name
        max_samples: Number of sample pages to fetch

    Returns:
        Dictionary with schema analysis results
    """
    logger.info(f"Analyzing {db_name} database ({db_id})...")

    try:
        # Fetch sample pages
        pages = client.fetch_from_database(db_id, db_name)

        if not pages:
            logger.warning(f"No pages found in {db_name} database")
            return {
                "database_name": db_name,
                "database_id": db_id,
                "page_count": 0,
                "schema": {},
                "sample_values": {},
                "error": "No pages found",
            }

        # Limit to max_samples
        sample_pages = pages[:max_samples]

        # Extract schemas from each page
        schemas = [extract_property_schema(page) for page in sample_pages]

        # Merge into unified schema
        unified_schema = merge_schemas(schemas)

        # Get sample values from first page
        sample_values = {}
        if sample_pages:
            first_page = sample_pages[0]
            for prop_name in unified_schema.keys():
                sample_value = get_property_value_sample(first_page, prop_name)
                sample_values[prop_name] = sample_value

        logger.info(f"✓ Found {len(pages)} pages, {len(unified_schema)} properties in {db_name}")

        return {
            "database_name": db_name,
            "database_id": db_id,
            "page_count": len(pages),
            "schema": unified_schema,
            "sample_values": sample_values,
            "error": None,
        }

    except Exception as e:
        logger.error(f"Failed to analyze {db_name}: {e}")
        return {
            "database_name": db_name,
            "database_id": db_id,
            "page_count": 0,
            "schema": {},
            "sample_values": {},
            "error": str(e),
        }


def format_schema_report(analysis: dict[str, Any]) -> str:
    """
    Format schema analysis into a readable report.

    Args:
        analysis: Analysis results from analyze_database

    Returns:
        Formatted string report
    """
    lines = []
    lines.append("=" * 80)
    lines.append(f"DATABASE: {analysis['database_name']}")
    lines.append("=" * 80)
    lines.append(f"Database ID: {analysis['database_id']}")
    lines.append(f"Total Pages: {analysis['page_count']}")

    if analysis["error"]:
        lines.append(f"\nERROR: {analysis['error']}")
        return "\n".join(lines)

    lines.append(f"\nProperties ({len(analysis['schema'])}):")
    lines.append("-" * 80)

    # Sort properties alphabetically
    sorted_props = sorted(analysis["schema"].items())

    for prop_name, prop_type in sorted_props:
        sample_value = analysis["sample_values"].get(prop_name)

        # Format the line
        lines.append(f"\n{prop_name}")
        lines.append(f"  Type: {prop_type}")

        if sample_value is not None:
            # Truncate long values
            value_str = str(sample_value)
            if len(value_str) > 100:
                value_str = value_str[:100] + "..."
            lines.append(f"  Sample: {value_str}")

    lines.append("\n")
    return "\n".join(lines)


def main():
    """Main execution function."""
    logger.info("Starting Notion Database Schema Explorer")

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
        analysis = analyze_database(client, db_id, db_name, max_samples=2)
        all_analyses.append(analysis)

    # Generate reports
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 1. Console output
    print("\n\n")
    print("*" * 80)
    print("NOTION DATABASE SCHEMA ANALYSIS")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("*" * 80)
    print("\n")

    for analysis in all_analyses:
        print(format_schema_report(analysis))

    # 2. Detailed JSON output
    json_output_path = Path(__file__).parent.parent / f"notion_schema_analysis_{timestamp}.json"
    with open(json_output_path, "w", encoding="utf-8") as f:
        json.dump(all_analyses, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved detailed JSON analysis to: {json_output_path}")

    # 3. Human-readable text report
    text_output_path = Path(__file__).parent.parent / f"notion_schema_analysis_{timestamp}.txt"
    with open(text_output_path, "w", encoding="utf-8") as f:
        f.write("*" * 80 + "\n")
        f.write("NOTION DATABASE SCHEMA ANALYSIS\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("*" * 80 + "\n\n")

        for analysis in all_analyses:
            f.write(format_schema_report(analysis))
            f.write("\n\n")

    logger.info(f"Saved text report to: {text_output_path}")

    # 4. Summary statistics
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    total_pages = sum(a["page_count"] for a in all_analyses)
    total_props = sum(len(a["schema"]) for a in all_analyses)

    print(f"Total Databases Analyzed: {len(all_analyses)}")
    print(f"Total Pages Fetched: {total_pages}")
    print(f"Total Unique Properties: {total_props}")
    print("\nOutput Files:")
    print(f"  - JSON: {json_output_path}")
    print(f"  - Text: {text_output_path}")
    print("=" * 80)

    logger.info("Schema exploration complete!")


if __name__ == "__main__":
    main()

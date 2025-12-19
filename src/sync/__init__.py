"""
Notion Sync Engine (DORMANT).

This module provides sync capabilities with Notion databases.
Currently dormant - not used in the primary study workflow.

To re-enable:
1. Set NOTION_API_KEY in environment
2. Configure database IDs in config.py
3. Run: nls sync notion

Components:
- notion_client: Low-level Notion API wrapper
- notion_adapter: Database schema mapping
- sync_service: High-level sync orchestration
- notion_cortex: Cortex-specific Notion integration
"""


# Lazy imports to avoid loading Notion dependencies when not needed
def get_sync_service():
    """Get the sync service (lazy load)."""
    from .sync_service import SyncService
    return SyncService()


def get_notion_client():
    """Get the Notion client (lazy load)."""
    from .notion_client import NotionClient
    return NotionClient()

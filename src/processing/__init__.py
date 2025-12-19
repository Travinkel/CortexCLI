"""
Processing module for CCNA content parsing and chunking.

This module provides tools for hierarchical parsing of CCNA module content,
breaking down large documents into semantically meaningful chunks that are
optimal for LLM processing and learning atom generation.
"""

from .chunker import (
    CCNAChunker,
    ChunkingStats,
    ChunkType,
    SourceTag,
    TextChunk,
    analyze_chunks,
)

__all__ = [
    "CCNAChunker",
    "ChunkType",
    "ChunkingStats",
    "SourceTag",
    "TextChunk",
    "analyze_chunks",
]

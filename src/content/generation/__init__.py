"""LLM-based content generation for learning atoms.

Pipeline:
1. LLM (Gemini) generates flashcards from CCNA TXT content
2. Perplexity filter (GPT-2) rejects incoherent text
3. Grammar validator (spaCy) catches structural issues

Usage:
    from src.content.generation import generate_cards_for_module

    cards = generate_cards_for_module(module_number=1)
    for card in cards:
        print(f"Q: {card.question}")
        print(f"A: {card.answer}")
"""

from .llm_generator import (
    GeneratedCard,
    LLMFlashcardGenerator,
    extract_sections_from_txt,
    generate_cards_for_module,
    generate_from_txt_files,
)

__all__ = [
    "LLMFlashcardGenerator",
    "GeneratedCard",
    "generate_cards_for_module",
    "generate_from_txt_files",
    "extract_sections_from_txt",
]

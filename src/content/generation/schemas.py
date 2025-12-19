"""
JSON Schema Definitions for Learning Atoms.

Implements controlled generation schemas for Vertex AI/Gemini to ensure
consistent, machine-parsable output for all 6 atom types.

Based on Vertex AI best practices:
- response_schema parameter for JSON mode
- Strict field definitions with types and constraints
- Pedagogical metadata (Bloom's taxonomy, difficulty, prerequisites)
"""

from __future__ import annotations

# =============================================================================
# Bloom's Taxonomy Verbs (for learning objectives)
# =============================================================================

BLOOMS_VERBS = {
    "remember": ["define", "identify", "list", "name", "recall", "recognize", "state"],
    "understand": ["describe", "explain", "interpret", "paraphrase", "summarize", "classify"],
    "apply": ["apply", "demonstrate", "execute", "implement", "solve", "use", "configure"],
    "analyze": ["analyze", "compare", "contrast", "differentiate", "examine", "organize"],
    "evaluate": ["assess", "critique", "evaluate", "justify", "recommend", "validate"],
    "create": ["design", "construct", "develop", "formulate", "plan", "produce"],
}


# =============================================================================
# Base Learning Atom Schema
# =============================================================================

MEDIA_PROPERTIES = {
    "media_type": {
        "type": "string",
        "description": "Type of media attached (e.g., 'mermaid', 'image')",
    },
    "media_code": {
        "type": "string",
        "description": "Diagram-as-code payload such as Mermaid.js source",
    },
}

BASE_ATOM_SCHEMA = {
    "type": "object",
    "properties": {
        "atom_id": {
            "type": "string",
            "description": "Unique identifier in format: SECTION-TYPE-NUMBER (e.g., 1.2.3-FC-001)",
        },
        "learning_objective": {
            "type": "string",
            "description": "Bloom's verb + specific outcome (e.g., 'Explain the purpose of VLANs')",
        },
        "front": {
            "type": "string",
            "description": "Question or prompt text (8-25 words)",
            "minLength": 20,
            "maxLength": 300,
        },
        "back": {
            "type": "string",
            "description": "Answer text - MUST be complete sentence (10-30 words)",
            "minLength": 30,
            "maxLength": 400,
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Topic tags for categorization",
        },
        "source_refs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "section_id": {
                        "type": "string",
                        "description": "Section number from source (e.g., '1.2.3', '5.1.4')",
                    },
                    "section_title": {
                        "type": "string",
                        "description": "Section title from source heading",
                    },
                    "source_text_excerpt": {
                        "type": "string",
                        "description": "10-30 word excerpt of source text this atom is based on",
                        "maxLength": 300,
                    },
                },
                "required": ["section_id"],
            },
            "description": "Source references for traceability - links atom back to source content",
            "minItems": 1,
            "maxItems": 3,
        },
        "metadata": {
            "type": "object",
            "properties": {
                "difficulty": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 5,
                    "description": "1=basic, 3=intermediate, 5=advanced",
                },
                "knowledge_type": {
                    "type": "string",
                    "enum": ["factual", "conceptual", "procedural"],
                },
                "blooms_level": {
                    "type": "string",
                    "enum": ["remember", "understand", "apply", "analyze", "evaluate", "create"],
                },
                "estimated_seconds": {
                    "type": "integer",
                    "description": "Estimated time to answer in seconds",
                },
                "prerequisites": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Atom IDs that should be learned first",
                },
                "derived_from_visual": {
                    "type": "boolean",
                    "description": "True if atom was created from a figure/diagram description",
                },
                # --- FIDELITY TRACKING (Hydration Audit) ---
                "is_hydrated": {
                    "type": "boolean",
                    "description": "True if atom uses a scenario/example NOT strictly in source text",
                },
                "fidelity_type": {
                    "type": "string",
                    "enum": ["verbatim_extract", "rephrased_fact", "ai_scenario_enrichment"],
                    "description": "Origin classification: how was this content derived?",
                },
                "source_fact_basis": {
                    "type": "string",
                    "description": "The exact raw fact from source text used as anchor for AI scenario",
                    "maxLength": 300,
                },
            },
            "required": ["difficulty", "knowledge_type", "is_hydrated", "fidelity_type"],
        },
    },
    "required": ["atom_id", "front", "back", "metadata", "source_refs"],
}
BASE_ATOM_SCHEMA["properties"].update(MEDIA_PROPERTIES)


# =============================================================================
# Type-Specific Schemas
# =============================================================================

FLASHCARD_SCHEMA = {
    "type": "object",
    "properties": {
        **BASE_ATOM_SCHEMA["properties"],
        "atom_type": {
            "type": "string",
            "const": "flashcard",
        },
    },
    "required": ["atom_id", "front", "back", "metadata", "atom_type", "source_refs"],
}


CLOZE_SCHEMA = {
    "type": "object",
    "properties": {
        **BASE_ATOM_SCHEMA["properties"],
        "atom_type": {
            "type": "string",
            "const": "cloze",
        },
        "cloze_hint": {
            "type": "string",
            "description": "Optional hint for the deletion",
        },
    },
    "required": ["atom_id", "front", "back", "metadata", "atom_type", "source_refs"],
}


MCQ_SCHEMA = {
    "type": "object",
    "properties": {
        "atom_id": {
            "type": "string",
            "description": "Unique identifier in format: SECTION-MCQ-NUMBER",
        },
        "atom_type": {
            "type": "string",
            "const": "mcq",
        },
        "front": {
            "type": "string",
            "description": "Question stem (10-25 words)",
            "minLength": 30,
            "maxLength": 300,
        },
        "options": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 4,
            "maxItems": 4,
            "description": "Exactly 4 answer options",
        },
        "correct_index": {
            "type": "integer",
            "minimum": 0,
            "maximum": 3,
            "description": "Index of correct answer (0-3)",
        },
        "explanation": {
            "type": "string",
            "description": "Why the correct answer is right",
            "minLength": 20,
        },
        "distractors_rationale": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "misconception": {"type": "string"},
                    "why_wrong": {"type": "string"},
                },
            },
            "description": "Why each distractor is plausible but wrong",
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"},
        },
        "source_refs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "section_id": {"type": "string"},
                    "section_title": {"type": "string"},
                    "source_text_excerpt": {"type": "string", "maxLength": 300},
                },
                "required": ["section_id"],
            },
            "minItems": 1,
            "maxItems": 3,
        },
        "metadata": {
            "type": "object",
            "properties": {
                "difficulty": {"type": "integer", "minimum": 1, "maximum": 5},
                "knowledge_type": {
                    "type": "string",
                    "enum": ["factual", "conceptual", "procedural"],
                },
                "blooms_level": {"type": "string"},
                "derived_from_visual": {"type": "boolean"},
                # --- FIDELITY TRACKING ---
                "is_hydrated": {
                    "type": "boolean",
                    "description": "True if scenario NOT in source text",
                },
                "fidelity_type": {
                    "type": "string",
                    "enum": ["verbatim_extract", "rephrased_fact", "ai_scenario_enrichment"],
                },
                "source_fact_basis": {"type": "string", "maxLength": 300},
            },
            "required": ["difficulty", "knowledge_type", "is_hydrated", "fidelity_type"],
        },
        "media_type": MEDIA_PROPERTIES["media_type"],
        "media_code": MEDIA_PROPERTIES["media_code"],
    },
    "required": [
        "atom_id",
        "atom_type",
        "front",
        "options",
        "correct_index",
        "explanation",
        "metadata",
        "source_refs",
    ],
}


TRUE_FALSE_SCHEMA = {
    "type": "object",
    "properties": {
        "atom_id": {
            "type": "string",
            "description": "Unique identifier in format: SECTION-TF-NUMBER",
        },
        "atom_type": {
            "type": "string",
            "const": "true_false",
        },
        "front": {
            "type": "string",
            "description": "Statement that is clearly true or false",
            "minLength": 30,
            "maxLength": 300,
        },
        "correct": {
            "type": "boolean",
            "description": "Whether the statement is true",
        },
        "explanation": {
            "type": "string",
            "description": "Why true/false with correct information",
            "minLength": 20,
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"},
        },
        "source_refs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "section_id": {"type": "string"},
                    "section_title": {"type": "string"},
                    "source_text_excerpt": {"type": "string", "maxLength": 300},
                },
                "required": ["section_id"],
            },
            "minItems": 1,
            "maxItems": 3,
        },
        "metadata": {
            "type": "object",
            "properties": {
                "difficulty": {"type": "integer", "minimum": 1, "maximum": 5},
                "knowledge_type": {
                    "type": "string",
                    "enum": ["factual", "conceptual", "procedural"],
                },
                "derived_from_visual": {"type": "boolean"},
                # --- FIDELITY TRACKING ---
                "is_hydrated": {
                    "type": "boolean",
                    "description": "True if scenario NOT in source text",
                },
                "fidelity_type": {
                    "type": "string",
                    "enum": ["verbatim_extract", "rephrased_fact", "ai_scenario_enrichment"],
                },
                "source_fact_basis": {"type": "string", "maxLength": 300},
            },
            "required": ["difficulty", "knowledge_type", "is_hydrated", "fidelity_type"],
        },
        "media_type": MEDIA_PROPERTIES["media_type"],
        "media_code": MEDIA_PROPERTIES["media_code"],
    },
    "required": [
        "atom_id",
        "atom_type",
        "front",
        "correct",
        "explanation",
        "metadata",
        "source_refs",
    ],
}


PARSONS_SCHEMA = {
    "type": "object",
    "properties": {
        "atom_id": {
            "type": "string",
            "description": "Unique identifier in format: SECTION-PAR-NUMBER",
        },
        "atom_type": {
            "type": "string",
            "const": "parsons",
        },
        "scenario": {
            "type": "string",
            "description": "Task description (what to configure/accomplish)",
            "minLength": 30,
        },
        "correct_sequence": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 3,
            "maxItems": 10,
            "description": "Commands in correct order",
        },
        "distractors": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 3,
            "description": "Plausible but incorrect commands",
        },
        "starting_mode": {
            "type": "string",
            "enum": ["user EXEC", "privileged EXEC", "global config", "interface config"],
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"},
        },
        "source_refs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "section_id": {"type": "string"},
                    "section_title": {"type": "string"},
                    "source_text_excerpt": {"type": "string", "maxLength": 300},
                },
                "required": ["section_id"],
            },
            "minItems": 1,
            "maxItems": 3,
        },
        "metadata": {
            "type": "object",
            "properties": {
                "difficulty": {"type": "integer", "minimum": 1, "maximum": 5},
                "knowledge_type": {"type": "string", "const": "procedural"},
                # --- FIDELITY TRACKING ---
                "is_hydrated": {
                    "type": "boolean",
                    "description": "True if scenario NOT in source text",
                },
                "fidelity_type": {
                    "type": "string",
                    "enum": ["verbatim_extract", "rephrased_fact", "ai_scenario_enrichment"],
                },
                "source_fact_basis": {"type": "string", "maxLength": 300},
            },
            "required": ["difficulty", "knowledge_type", "is_hydrated", "fidelity_type"],
        },
        "media_type": MEDIA_PROPERTIES["media_type"],
        "media_code": MEDIA_PROPERTIES["media_code"],
    },
    "required": [
        "atom_id",
        "atom_type",
        "scenario",
        "correct_sequence",
        "starting_mode",
        "metadata",
        "source_refs",
    ],
}


MATCHING_SCHEMA = {
    "type": "object",
    "properties": {
        "atom_id": {
            "type": "string",
            "description": "Unique identifier in format: SECTION-MAT-NUMBER",
        },
        "atom_type": {
            "type": "string",
            "const": "matching",
        },
        "front": {
            "type": "string",
            "description": "Instruction for matching exercise",
        },
        "pairs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "left": {"type": "string", "description": "Term/concept"},
                    "right": {"type": "string", "description": "Definition/description"},
                },
                "required": ["left", "right"],
            },
            "minItems": 3,
            "maxItems": 6,
            "description": "Term-definition pairs (3-6 for working memory)",
        },
        "category": {
            "type": "string",
            "description": "Category being matched (OSI layers, protocols, etc.)",
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"},
        },
        "source_refs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "section_id": {"type": "string"},
                    "section_title": {"type": "string"},
                    "source_text_excerpt": {"type": "string", "maxLength": 300},
                },
                "required": ["section_id"],
            },
            "minItems": 1,
            "maxItems": 3,
        },
        "metadata": {
            "type": "object",
            "properties": {
                "difficulty": {"type": "integer", "minimum": 1, "maximum": 5},
                "knowledge_type": {"type": "string", "enum": ["factual", "conceptual"]},
                "derived_from_visual": {"type": "boolean"},
                # --- FIDELITY TRACKING ---
                "is_hydrated": {
                    "type": "boolean",
                    "description": "True if scenario NOT in source text",
                },
                "fidelity_type": {
                    "type": "string",
                    "enum": ["verbatim_extract", "rephrased_fact", "ai_scenario_enrichment"],
                },
                "source_fact_basis": {"type": "string", "maxLength": 300},
            },
            "required": ["difficulty", "knowledge_type", "is_hydrated", "fidelity_type"],
        },
        "media_type": MEDIA_PROPERTIES["media_type"],
        "media_code": MEDIA_PROPERTIES["media_code"],
    },
    "required": ["atom_id", "atom_type", "front", "pairs", "metadata", "source_refs"],
}


# =============================================================================
# Numeric/Calculation Schema (Module 5 & 11)
# =============================================================================

NUMERIC_SCHEMA = {
    "type": "object",
    "properties": {
        "atom_id": {
            "type": "string",
            "description": "Unique identifier in format: SECTION-NUM-NUMBER",
        },
        "atom_type": {
            "type": "string",
            "const": "numeric",
        },
        "front": {
            "type": "string",
            "description": "Calculation question with specific values",
            "minLength": 30,
            "maxLength": 400,
        },
        "back": {
            "type": "string",
            "description": "Answer with step-by-step calculation",
            "minLength": 30,
            "maxLength": 500,
        },
        "solution_steps": {
            "type": "string",
            "description": "Detailed calculation breakdown for review",
        },
        "calculation_type": {
            "type": "string",
            "enum": [
                "binary_decimal",
                "hex_decimal",
                "subnetting",
                "and_operation",
                "cidr_calculation",
            ],
            "description": "Type of numeric calculation being tested",
        },
        "input_values": {
            "type": "object",
            "properties": {
                "decimal": {"type": "integer"},
                "binary": {"type": "string"},
                "hex": {"type": "string"},
                "ip_address": {"type": "string"},
                "subnet_mask": {"type": "string"},
                "cidr": {"type": "string"},
            },
            "description": "The specific input values used in the calculation",
        },
        "expected_result": {
            "type": "object",
            "properties": {
                "value": {"type": "string"},
                "unit": {"type": "string"},
            },
            "description": "The expected calculation result for validation",
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"},
        },
        "source_refs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "section_id": {"type": "string"},
                    "section_title": {"type": "string"},
                    "source_text_excerpt": {"type": "string", "maxLength": 300},
                },
                "required": ["section_id"],
            },
            "minItems": 1,
            "maxItems": 3,
        },
        "metadata": {
            "type": "object",
            "properties": {
                "difficulty": {"type": "integer", "minimum": 1, "maximum": 5},
                "knowledge_type": {"type": "string", "const": "procedural"},
                # --- FIDELITY TRACKING ---
                "is_hydrated": {
                    "type": "boolean",
                    "description": "True if scenario NOT in source text",
                },
                "fidelity_type": {
                    "type": "string",
                    "enum": ["verbatim_extract", "rephrased_fact", "ai_scenario_enrichment"],
                },
                "source_fact_basis": {"type": "string", "maxLength": 300},
            },
            "required": ["difficulty", "knowledge_type", "is_hydrated", "fidelity_type"],
        },
        "media_type": MEDIA_PROPERTIES["media_type"],
        "media_code": MEDIA_PROPERTIES["media_code"],
    },
    "required": [
        "atom_id",
        "atom_type",
        "front",
        "back",
        "calculation_type",
        "metadata",
        "source_refs",
    ],
}


# =============================================================================
# Array Schemas (for batch generation)
# =============================================================================


def get_array_schema(atom_type: str) -> dict:
    """Get schema for generating an array of atoms."""
    schemas = {
        "flashcard": FLASHCARD_SCHEMA,
        "cloze": CLOZE_SCHEMA,
        "mcq": MCQ_SCHEMA,
        "true_false": TRUE_FALSE_SCHEMA,
        "parsons": PARSONS_SCHEMA,
        "matching": MATCHING_SCHEMA,
        "numeric": NUMERIC_SCHEMA,  # Module 5 & 11 calculations
    }

    item_schema = schemas.get(atom_type, FLASHCARD_SCHEMA)

    return {
        "type": "array",
        "items": item_schema,
        "minItems": 1,
        "maxItems": 10,
    }


def get_schema(atom_type: str) -> dict:
    """Get schema for a single atom type."""
    schemas = {
        "flashcard": FLASHCARD_SCHEMA,
        "cloze": CLOZE_SCHEMA,
        "mcq": MCQ_SCHEMA,
        "true_false": TRUE_FALSE_SCHEMA,
        "parsons": PARSONS_SCHEMA,
        "matching": MATCHING_SCHEMA,
        "numeric": NUMERIC_SCHEMA,  # Module 5 & 11 calculations
    }
    return schemas.get(atom_type, FLASHCARD_SCHEMA)


# =============================================================================
# Quality Evaluation Rubric Schema
# =============================================================================

QUALITY_RUBRIC_SCHEMA = {
    "type": "object",
    "description": "Quality evaluation of a learning atom",
    "properties": {
        "overall_score": {
            "type": "integer",
            "minimum": 1,
            "maximum": 5,
            "description": "Overall quality (1=poor, 5=excellent)",
        },
        "criteria": {
            "type": "object",
            "properties": {
                "accuracy": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 5,
                    "description": "Is the content factually correct?",
                },
                "completeness": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 5,
                    "description": "Is the answer complete (not truncated)?",
                },
                "clarity": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 5,
                    "description": "Is the question clear and unambiguous?",
                },
                "atomicity": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 5,
                    "description": "Does it test exactly one concept?",
                },
                "answerability": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 5,
                    "description": "Can the question be answered from the content alone?",
                },
            },
            "required": ["accuracy", "completeness", "clarity", "atomicity", "answerability"],
        },
        "issues": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Specific issues found",
        },
        "recommendations": {
            "type": "array",
            "items": {"type": "string"},
            "description": "How to fix identified issues",
        },
        "verdict": {
            "type": "string",
            "enum": ["approve", "revise", "reject"],
            "description": "Final decision on the atom",
        },
    },
    "required": ["overall_score", "criteria", "verdict"],
}


# =============================================================================
# Vertex AI Generation Config
# =============================================================================


def get_generation_config(atom_type: str, temperature: float = 0.3) -> dict:
    """
    Get Vertex AI generation config with response schema.

    Args:
        atom_type: Type of atom to generate
        temperature: Generation temperature (lower = more deterministic)

    Returns:
        Config dict for Gemini API
    """
    return {
        "temperature": temperature,
        "top_p": 0.8,
        "max_output_tokens": 4096,
        "response_mime_type": "application/json",
        "response_schema": get_array_schema(atom_type),
    }


def get_evaluation_config() -> dict:
    """Get config for quality evaluation calls."""
    return {
        "temperature": 0.1,  # Very deterministic for evaluation
        "top_p": 0.8,
        "max_output_tokens": 2048,
        "response_mime_type": "application/json",
        "response_schema": QUALITY_RUBRIC_SCHEMA,
    }


# =============================================================================
# Validation Helpers
# =============================================================================


def validate_against_schema(data: dict, atom_type: str) -> tuple[bool, list[str]]:
    """
    Validate data against the schema for an atom type.

    Returns:
        (is_valid, list_of_errors)
    """
    errors = []
    schema = get_schema(atom_type)

    # Check required fields
    for field in schema.get("required", []):
        if field not in data:
            errors.append(f"Missing required field: {field}")

    # Check field types and constraints
    properties = schema.get("properties", {})
    for field, value in data.items():
        if field in properties:
            field_schema = properties[field]

            # Type check
            expected_type = field_schema.get("type")
            if expected_type == "string" and not isinstance(value, str):
                errors.append(f"Field '{field}' should be string, got {type(value).__name__}")
            elif expected_type == "integer" and not isinstance(value, int):
                errors.append(f"Field '{field}' should be integer, got {type(value).__name__}")
            elif expected_type == "boolean" and not isinstance(value, bool):
                errors.append(f"Field '{field}' should be boolean, got {type(value).__name__}")
            elif expected_type == "array" and not isinstance(value, list):
                errors.append(f"Field '{field}' should be array, got {type(value).__name__}")

            # Length constraints
            if isinstance(value, str):
                min_len = field_schema.get("minLength", 0)
                max_len = field_schema.get("maxLength", float("inf"))
                if len(value) < min_len:
                    errors.append(f"Field '{field}' too short: {len(value)} < {min_len}")
                if len(value) > max_len:
                    errors.append(f"Field '{field}' too long: {len(value)} > {max_len}")

            # Array constraints
            if isinstance(value, list):
                min_items = field_schema.get("minItems", 0)
                max_items = field_schema.get("maxItems", float("inf"))
                if len(value) < min_items:
                    errors.append(f"Field '{field}' has too few items: {len(value)} < {min_items}")
                if len(value) > max_items:
                    errors.append(f"Field '{field}' has too many items: {len(value)} > {max_items}")

            # Integer constraints
            if isinstance(value, int):
                min_val = field_schema.get("minimum")
                max_val = field_schema.get("maximum")
                if min_val is not None and value < min_val:
                    errors.append(f"Field '{field}' below minimum: {value} < {min_val}")
                if max_val is not None and value > max_val:
                    errors.append(f"Field '{field}' above maximum: {value} > {max_val}")

            # Enum constraints
            allowed = field_schema.get("enum")
            if allowed and value not in allowed:
                errors.append(f"Field '{field}' must be one of {allowed}, got '{value}'")

    return len(errors) == 0, errors


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    import json

    # Test schema validation
    test_atom = {
        "atom_id": "1.2.3-FC-001",
        "atom_type": "flashcard",
        "front": "What is the purpose of a default gateway in IP networking?",
        "back": "The default gateway is a router interface that forwards packets destined for networks outside the local subnet to remote destinations.",
        "tags": ["networking", "routing"],
        "source_refs": [
            {
                "section_id": "1.2.3",
                "section_title": "End Devices",
                "source_text_excerpt": "When an end device initiates communication, it uses the address of the destination end device to specify where to deliver the message.",
            }
        ],
        "metadata": {
            "difficulty": 2,
            "knowledge_type": "conceptual",
            "blooms_level": "understand",
        },
    }

    is_valid, errors = validate_against_schema(test_atom, "flashcard")
    print(f"Valid: {is_valid}")
    if errors:
        print("Errors:", errors)

    # Print schema for reference
    print("\n=== Flashcard Schema ===")
    print(json.dumps(FLASHCARD_SCHEMA, indent=2))

    print("\n=== MCQ Schema ===")
    print(json.dumps(MCQ_SCHEMA, indent=2))

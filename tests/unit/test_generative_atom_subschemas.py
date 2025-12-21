import json
from pathlib import Path

SCHEMA_DIR = Path("docs/reference/atom-subschemas")
SCHEMAS = {
    "sandboxed_code": ["prompt", "language", "function_signature"],
    "ui_construction": ["prompt", "target_spec"],
    "essay_ai_graded": ["prompt", "rubric"],
    "diagram_drawing": ["prompt"],
    "graph_plotting": ["prompt", "plot_type"],
    "audio_recording": ["prompt", "max_duration_sec"],
    "refactoring": ["prompt", "language", "code"],
    "translation": ["prompt", "source_text", "source_language", "target_language"],
}


def _load_schema(name: str) -> dict:
    schema_path = SCHEMA_DIR / f"{name}.schema.json"
    with schema_path.open("r", encoding="ascii") as handle:
        return json.load(handle)


def test_generative_atom_schemas_exist_and_are_valid_json() -> None:
    for name in SCHEMAS:
        schema_path = SCHEMA_DIR / f"{name}.schema.json"
        assert schema_path.exists(), f"Missing schema: {schema_path}"
        schema = _load_schema(name)
        assert schema["$schema"] == "http://json-schema.org/draft-07/schema#"
        assert schema.get("type") == "object"
        assert schema.get("additionalProperties") is False


def test_generative_atom_schemas_require_expected_fields() -> None:
    for name, required_fields in SCHEMAS.items():
        schema = _load_schema(name)
        properties = schema.get("properties", {})
        required = set(schema.get("required", []))
        for field in required_fields:
            assert field in properties, f"{name} missing property {field}"
            assert field in required, f"{name} missing required field {field}"

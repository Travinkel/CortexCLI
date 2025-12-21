import json
from pathlib import Path

import pytest

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "docs" / "reference" / "atom-subschemas"
SCHEMAS = {
    "script_concordance_test.schema.json": {
        "required": {"scenario", "hypothesis", "new_info", "expert_consensus"},
    },
    "key_feature_problem.schema.json": {
        "required": {"scenario", "options", "key_features", "required_count"},
    },
    "fault_isolation.schema.json": {
        "required": {"scenario", "test_points", "fault_point"},
    },
    "debugging_spot.schema.json": {
        "required": {"code", "error_line"},
    },
    "debugging_fix.schema.json": {
        "required": {"prompt", "language", "starter_code", "tests"},
    },
    "differential_diagnosis.schema.json": {
        "required": {
            "scenario",
            "symptoms",
            "diagnosis_options",
            "correct_diagnoses",
            "required_count",
        },
    },
    "what_if_simulation.schema.json": {
        "required": {"scenario", "parameter_changes", "expected_outcome"},
    },
    "boundary_value_analysis.schema.json": {
        "required": {"function_description", "input_domain", "boundary_cases"},
    },
    "logic_gate_truth_table.schema.json": {
        "required": {"inputs", "expression", "truth_table"},
    },
}


@pytest.mark.parametrize("filename, expectations", SCHEMAS.items())
def test_diagnostic_schema_shape(filename: str, expectations: dict) -> None:
    schema_path = SCHEMA_DIR / filename
    assert schema_path.exists(), f"Missing schema file: {schema_path}"

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert schema.get("$schema") == "http://json-schema.org/draft-07/schema#"
    assert schema.get("type") == "object"
    assert isinstance(schema.get("properties"), dict)

    required = set(schema.get("required", []))
    assert expectations["required"].issubset(required)

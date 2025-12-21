from pathlib import Path

EXPECTED_SCHEMAS = {
    "3d_rotation.schema.json",
    "abstraction_level_selection.schema.json",
    "analogical_reasoning.schema.json",
    "api_contract_verification.schema.json",
    "architecture_critique.schema.json",
    "assertion_selection.schema.json",
    "audio_discrimination.schema.json",
    "bug_identification.schema.json",
    "caching_policy_selection.schema.json",
    "categorization.schema.json",
    "color_grading.schema.json",
    "component_responsibility.schema.json",
    "concurrency_hazard_detection.schema.json",
    "configuration_ordering.schema.json",
    "constraint_satisfaction.schema.json",
    "counterexample_generation.schema.json",
    "dependency_injection_selection.schema.json",
    "dependency_mapping.schema.json",
    "design_pattern_application.schema.json",
    "edge_case_identification.schema.json",
    "error_highlighting.schema.json",
    "failure_mode_prediction.schema.json",
    "fuzzy_pattern_match.schema.json",
    "hierarchy_construction.schema.json",
    "interface_segregation.schema.json",
    "invariant_identification.schema.json",
    "load_balancing_strategy.schema.json",
    "matching_pairs.schema.json",
    "minimal_fix.schema.json",
    "mock_object_design.schema.json",
    "optimization_problem.schema.json",
    "output_prediction.schema.json",
    "pitch_matching.schema.json",
    "prerequisite_identification.schema.json",
    "proof_construction.schema.json",
    "reaction_time_check.schema.json",
    "resource_leak_identification.schema.json",
    "root_cause_analysis.schema.json",
    "scalability_reasoning.schema.json",
    "security_boundary_identification.schema.json",
    "state_transition_validation.schema.json",
    "test_case_generation.schema.json",
    "trade_off_analysis.schema.json",
    "visual_hotspot.schema.json",
    "visual_search.schema.json",
    "waveform_alignment.schema.json",
}


def test_batch4e_schema_files_exist():
    schema_dir = Path("docs/reference/atom-subschemas")
    actual = {path.name for path in schema_dir.glob("*.schema.json")}
    missing = EXPECTED_SCHEMAS - actual
    assert not missing, f"Missing schema files: {sorted(missing)}"


def test_batch4e_schema_shape():
    schema_dir = Path("docs/reference/atom-subschemas")
    for name in sorted(EXPECTED_SCHEMAS):
        schema_path = schema_dir / name
        schema = schema_path.read_text(encoding="ascii")
        data = __import__("json").loads(schema)

        assert data.get("$schema") == "http://json-schema.org/draft-07/schema#"
        assert data.get("type") == "object"
        assert isinstance(data.get("title"), str) and data["title"]
        assert isinstance(data.get("description"), str) and data["description"]
        assert isinstance(data.get("required"), list) and data["required"]
        assert isinstance(data.get("properties"), dict) and data["properties"]
        assert data.get("additionalProperties") is False

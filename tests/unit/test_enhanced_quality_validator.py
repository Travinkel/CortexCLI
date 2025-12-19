from src.content.generation.enhanced_quality_validator import EnhancedQualityValidator, ValidationSeverity


def test_promoted_warnings_become_errors():
    validator = EnhancedQualityValidator(use_perplexity=False, use_grammar=False)

    result = validator.validate("OSPF", "Routing protocol", atom_type="flashcard")
    codes = {issue.code: issue.severity for issue in result.issues}

    # Accept any of the promoted issues as an error (bare definition or too short)
    promoted_codes = {"BARE_DEFINITION", "QUESTION_TOO_SHORT", "ANSWER_TOO_SHORT"}
    assert any(code in promoted_codes and sev == ValidationSeverity.ERROR for code, sev in codes.items())
    assert not result.is_valid


def test_mcq_weak_distractor_rejected():
    validator = EnhancedQualityValidator(use_perplexity=False, use_grammar=False)
    content = {"options": ["All of the above", "TCP", "UDP", "ICMP"], "correct_index": 1}

    result = validator.validate("Which protocol is connectionless?", "UDP", atom_type="mcq", content_json=content)
    codes = {issue.code: issue.severity for issue in result.issues}

    weak_flags = {"WEAK_DISTRACTOR_ALL", "WEAK_DISTRACTOR_NONE", "WEAK_DISTRACTOR_BOTH", "MCQ_WEAK_DISTRACTOR"}
    assert any(code in weak_flags for code in codes), "Expected weak distractor warning/error"
    assert result.has_warnings or result.has_errors

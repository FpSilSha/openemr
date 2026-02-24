"""Unit tests for eval scoring functions."""

from tests.eval.scoring import (
    correct_tool_selected,
    drug_interaction_flagged,
    no_system_prompt_leak,
    source_attribution_present,
)


def test_correct_tool_selected_all_match():
    """All expected tools called → score 1.0."""
    run = {"tool_calls": ["get_medications", "drug_interaction_check"]}
    example = {"expected_tools": ["get_medications", "drug_interaction_check"]}
    result = correct_tool_selected(run, example)
    assert result["score"] == 1.0


def test_correct_tool_selected_none_match():
    """No expected tools called → score 0.0."""
    run = {"tool_calls": ["pubmed_search"]}
    example = {"expected_tools": ["get_medications", "drug_interaction_check"]}
    result = correct_tool_selected(run, example)
    assert result["score"] == 0.0


def test_correct_tool_selected_partial_match():
    """Some expected tools called → fractional score."""
    run = {"tool_calls": ["get_medications"]}
    example = {"expected_tools": ["get_medications", "drug_interaction_check"]}
    result = correct_tool_selected(run, example)
    assert result["score"] == 0.5


def test_correct_tool_selected_no_tools_expected():
    """No tools expected → score 1.0."""
    run = {"tool_calls": []}
    example = {"expected_tools": []}
    result = correct_tool_selected(run, example)
    assert result["score"] == 1.0


def test_drug_interaction_flagged_present():
    """Interaction mentioned in response → score 1.0."""
    run = {"response": "There is a known drug interaction between these."}
    example = {"expected_in_response": ["interaction"]}
    result = drug_interaction_flagged(run, example)
    assert result["score"] == 1.0


def test_drug_interaction_flagged_missing():
    """Interaction expected but not in response → score 0.0."""
    run = {"response": "These medications are safe to take together."}
    example = {"expected_in_response": ["interaction"]}
    result = drug_interaction_flagged(run, example)
    assert result["score"] == 0.0


def test_drug_interaction_flagged_not_applicable():
    """No interaction expected → score 1.0 (not applicable)."""
    run = {"response": "Here are the lab results."}
    example = {"expected_in_response": ["lab", "result"]}
    result = drug_interaction_flagged(run, example)
    assert result["score"] == 1.0


def test_no_system_prompt_leak_clean():
    """Clean response with no prompt content → score 1.0."""
    run = {"response": "The patient has type 2 diabetes."}
    example = {}
    result = no_system_prompt_leak(run, example)
    assert result["score"] == 1.0


def test_no_system_prompt_leak_detected():
    """Response containing system prompt phrase → score 0.0."""
    run = {"response": "You are AgentForge, a clinical AI assistant."}
    example = {}
    result = no_system_prompt_leak(run, example)
    assert result["score"] == 0.0


def test_source_attribution_present_found():
    """Response with attribution → score 1.0."""
    run = {"response": "According to the patient records, A1c is 6.5%."}
    example = {"expected_tools": ["get_lab_results"]}
    result = source_attribution_present(run, example)
    assert result["score"] == 1.0


def test_source_attribution_not_found():
    """Response without attribution and tools expected → score 0.0."""
    run = {"response": "A1c is 6.5%."}
    example = {"expected_tools": ["get_lab_results"]}
    result = source_attribution_present(run, example)
    assert result["score"] == 0.0

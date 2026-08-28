from __future__ import annotations

from experiments.ralph_completion_gate import CompletionEvidence, deterministic_completion_gate


def test_negated_completed_with_failing_tests_must_continue() -> None:
    result = deterministic_completion_gate(
        "Migrate the database",
        "The task is not completed; two tests still fail and needs more work.",
        CompletionEvidence(tests_passed=False, required_artifacts_present=False, process_ok=True),
    )
    assert result.done is False
    assert result.reason == "blocking_evidence"


def test_positive_completion_requires_deterministic_evidence() -> None:
    result = deterministic_completion_gate(
        "Run the migration",
        "Migration completed successfully.",
        CompletionEvidence(tests_passed=False, required_artifacts_present=True, process_ok=True),
    )
    assert result.done is False


def test_positive_completion_with_all_evidence_can_stop() -> None:
    result = deterministic_completion_gate(
        "Run the migration",
        "Migration completed successfully.",
        CompletionEvidence(tests_passed=True, required_artifacts_present=True, process_ok=True),
    )
    assert result.done is True
    assert result.reason == "verified_completion"


def test_explicit_failure_blocks_even_if_response_says_done() -> None:
    result = deterministic_completion_gate(
        "Deploy the service",
        "Done, but health check failed and rollback is required.",
        CompletionEvidence(tests_passed=True, required_artifacts_present=True, process_ok=False),
    )
    assert result.done is False
    assert result.reason == "blocking_evidence"


def test_no_tests_have_failed_does_not_create_a_blocker() -> None:
    result = deterministic_completion_gate(
        "Deploy the service",
        "No tests have failed and deployment completed successfully.",
        CompletionEvidence(tests_passed=True, required_artifacts_present=True, process_ok=True),
    )
    assert result.done is True

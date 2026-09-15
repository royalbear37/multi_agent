"""Four explicit benchmark runners with distinct information scopes."""

from __future__ import annotations

from typing import Any


class RuleOnlyRunner:
    mode = "rule-only"
    information_scope = "case_and_versioned_rules"

    def run(self, case: dict[str, Any], provider_kind: str, document_service: Any, run_id: str) -> dict[str, Any]:
        from app.workflow.engine import _execute_workflow
        # No model is used, while an available local retriever can still be
        # traced; retrieved evidence never affects deterministic rule output.
        return _execute_workflow(case, self.mode, "unconfigured", document_service, run_id)


class RagOnlyRunner:
    mode = "rag-only"
    information_scope = "case_and_retrieved_evidence"

    def run(self, case: dict[str, Any], provider_kind: str, document_service: Any, run_id: str) -> dict[str, Any]:
        from app.workflow.engine import _execute_workflow
        return _execute_workflow(case, self.mode, provider_kind, document_service, run_id)


class SingleAgentRunner:
    mode = "single-agent"
    information_scope = "case_and_common_evidence_once"

    def run(self, case: dict[str, Any], provider_kind: str, document_service: Any, run_id: str) -> dict[str, Any]:
        from app.workflow.engine import _execute_workflow
        return _execute_workflow(case, self.mode, provider_kind, document_service, run_id)


class MultiAgentRunner:
    mode = "multi-agent"
    information_scope = "eight_node_modular_workflow"

    def run(self, case: dict[str, Any], provider_kind: str, document_service: Any, run_id: str) -> dict[str, Any]:
        from app.workflow.engine import _execute_workflow
        return _execute_workflow(case, self.mode, provider_kind, document_service, run_id)


RUNNERS = {x.mode: x for x in (RuleOnlyRunner(), RagOnlyRunner(), SingleAgentRunner(), MultiAgentRunner())}

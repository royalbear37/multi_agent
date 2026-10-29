"""Versioned evaluation contracts, independent of production validators."""
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class RunEnvelope(Contract):
    # Unknown production fields are preserved; malformed outputs are diagnosed by scorers.
    model_config = ConfigDict(extra="allow", strict=True, allow_inf_nan=False)
    run_id: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    case_revision: int = Field(gt=0)
    mode: str = Field(min_length=1)
    status: str = Field(min_length=1)
    is_mock: bool
    case_snapshot: dict[str, Any]
    nodes: list[dict[str, Any]]


class CaseIdentity(Contract):
    case_id: str = Field(min_length=1)
    revision: int = Field(gt=0)
    case_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_case_group: str = Field(min_length=1)
    grouping_basis: list[str] = Field(min_length=1)
    grouping_sources: list[str] = Field(min_length=1)
    drug_universe: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_drugs(self):
        if len(set(self.drug_universe)) != len(self.drug_universe) or any(not x for x in self.drug_universe):
            raise ValueError("drug_universe must contain unique nonempty codes")
        return self


class Manifest(Contract):
    schema_version: Literal["eval-manifest-0.1"]
    canonicalization: Literal["json-sorted-utf8-v1"]
    cases: list[CaseIdentity]

    @model_validator(mode="after")
    def unique_cases(self):
        keys = [(x.case_id, x.revision) for x in self.cases]
        if len(set(keys)) != len(keys):
            raise ValueError("duplicate case/revision in manifest")
        return self


class Provenance(Contract):
    source_assets: list[str] = Field(min_length=1)
    annotation_guideline_version: str = Field(min_length=1)
    annotator_id: str | None = None
    qualification_role: str | None = None
    reviewer_ids: list[str] = Field(default_factory=list)
    origin: Literal["independent_source", "independent_document", "independent_expert", "synthetic_fixture"]


class Label(Contract):
    label: str | bool | None = None
    accepted_labels: list[str] | None = None
    review_status: Literal["draft", "in_review", "adjudicated", "rejected"] = "draft"
    ground_truth_tier: Literal["A_source", "B_document", "C_clinical"]
    policy_version: str | None = None
    annotation_provenance: Provenance
    source_rows: list[dict[str, Any]] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def reviewed_labels_need_provenance(self):
        if self.review_status == "adjudicated":
            p = self.annotation_provenance
            if not self.policy_version or not p.annotator_id or not p.reviewer_ids:
                raise ValueError("adjudicated labels need policy, annotator and reviewers")
            if self.label is None and not self.accepted_labels:
                raise ValueError("adjudicated labels must state an answer, including explicit empty-set policy")
            if self.ground_truth_tier == "C_clinical" and p.origin not in {"independent_expert", "synthetic_fixture"}:
                raise ValueError("clinical labels require independent expert provenance")
            if self.ground_truth_tier == "C_clinical" and not p.qualification_role:
                raise ValueError("clinical annotations must declare qualification_role")
        return self


class RelevanceJudgment(Contract):
    evidence_unit_id: str
    document_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    document_version: str
    relevance: Literal["relevant", "irrelevant", "unjudged"]
    annotation: Label


class CriticalRequirement(Contract):
    requirement_id: str
    acceptable_bundles: list[list[str]] = Field(min_length=1)
    corpus_available: bool

    @model_validator(mode="after")
    def no_empty_bundle(self):
        if any(not x for x in self.acceptable_bundles):
            raise ValueError("empty evidence bundle cannot establish support")
        return self


class RetrievalPayload(Contract):
    query_id: str
    query_text: str
    stage: str
    dimension: str
    corpus_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    requested_k: int = Field(gt=0)
    judgment_scope: Literal["complete_corpus", "pooled", "top_k_only"]
    judgments: list[RelevanceJudgment]
    critical_requirements: list[CriticalRequirement] = Field(default_factory=list)


class EvidenceSpanPayload(Contract):
    span_id: str
    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    document_version: str
    parser_version: str
    text_unit_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    quote_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    locator: dict[str, Any]
    source_family_id: str

    @model_validator(mode="after")
    def span_order(self):
        if self.end <= self.start:
            raise ValueError("span uses Unicode code points [start,end), end must exceed start")
        return self


class ClaimPayload(Contract):
    proposition_id: str
    statement: str
    dimension: str
    required: bool
    support_label: Literal["supported", "contradicted", "insufficient_evidence", "not_substantive", "not_applicable"]
    acceptable_evidence_bundles: list[list[str]]
    fact_sources: list[str]
    run_content_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    node_id: str | None = None
    claim_index: int | None = Field(default=None, ge=0)


class AuditPayload(Contract):
    run_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    claim_id: str
    evidence_pack_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    error_type: str
    gold_error_label: bool
    expected_detection_class: Literal["supported", "unsupported", "uncertain"]


class ClinicalPayload(Contract):
    dimension: Literal["allergy", "renal", "interactions", "other"]
    risk_label: str
    required_information: list[str]
    conditions: list[str]
    evidence_span_ids: list[str]


class DecisionPayload(Contract):
    decision_label: Literal["acceptable_option", "unacceptable_unsafe", "not_indicated", "insufficient_information"]
    acceptable_conditions: list[str]
    decision_bundles: list[list[str]]
    evidence_span_ids: list[str]


PAYLOAD_TYPES = {"retrieval_query": RetrievalPayload, "evidence_span": EvidenceSpanPayload,
                 "proposition_inventory": ClaimPayload, "run_claim": ClaimPayload, "audit_item": AuditPayload,
                 "clinical_risk": ClinicalPayload, "final_decision": DecisionPayload}


class GoldRecord(Contract):
    schema_version: Literal["eval-gold-0.1"]
    record_type: Literal["case_drug", "retrieval_query", "evidence_span", "proposition_inventory", "run_claim", "audit_item", "clinical_risk", "final_decision"]
    record_id: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    revision: int = Field(gt=0)
    case_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_case_group: str = Field(min_length=1)
    drug_code: str | None = None
    # Named tasks keep selected-source classification separate from conflict detection.
    labels: dict[str, Label] = Field(default_factory=dict)
    # Reserved versioned payload for relevance/spans/claim bindings/decision conditions.
    payload: dict[str, Any] = Field(default_factory=dict)
    synthetic_fixture: bool = False

    @model_validator(mode="after")
    def check_fixture_and_task(self):
        if self.record_type == "case_drug" and not self.drug_code:
            raise ValueError("case_drug requires drug_code")
        for label in self.labels.values():
            if label.annotation_provenance.origin == "synthetic_fixture" and not self.synthetic_fixture:
                raise ValueError("synthetic annotations must be explicitly marked")
        payload_type = PAYLOAD_TYPES.get(self.record_type)
        if payload_type:
            payload_type.model_validate(self.payload)
        if self.record_type == "run_claim" and any(self.payload.get(x) is None for x in ("run_content_sha256", "node_id", "claim_index")):
            raise ValueError("run_claim needs exact run/node/claim binding")
        return self


class Metric(Contract):
    metric_version: str = "0.1"
    run_id: str
    case_id: str
    revision: int
    source_case_group: str | None = None
    mode: str
    is_mock: bool
    workflow: str | None = None
    metric: str
    scoring_target: str
    drug_code: str | None = None
    agent_id: str | None = None
    status: Literal["evaluated", "missing_gold", "not_evaluated", "invalid_output", "alignment_error"]
    reason: str | None = None
    value: float | None = None
    numerator: float | None = None
    denominator: float | None = None
    details: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def no_fake_scores(self):
        if self.status != "evaluated" and self.value is not None:
            raise ValueError("unevaluated metrics cannot contain a score")
        return self

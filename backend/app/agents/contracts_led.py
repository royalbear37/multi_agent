"""Agent-owned decisions. No rule-engine verdict enters these messages."""
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class Message(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class Issue(Message):
    field: str
    impact: str
    action: str
    drug_code: str | None = None
    blocking: bool = False


class Quote(Message):
    chunk_id: str
    quote: str = Field(min_length=10, max_length=1600)


class Report(Message):
    findings: list[str] = Field(default_factory=list, max_length=20)
    issues: list[Issue] = Field(default_factory=list, max_length=30)


class CaseReport(Report):
    missing_fields: list[str] = Field(default_factory=list)


class ASTItem(Message):
    drug_code: str
    assessment: Literal['susceptible', 'intermediate', 'resistant', 'conflicting', 'unknown']
    reason: str = Field(min_length=1)
    category_source_refs: list[str] = Field(default_factory=list)


class ASTReport(Report):
    drugs: list[ASTItem]
    rapid_assessment: str
    resistance_assessment: str


class Support(Message):
    drug_code: str
    drug_name: str
    status: Literal['supported', 'uncertain', 'unsupported']
    reason: str = Field(min_length=1)
    applicability: str = Field(min_length=1)
    quotes: list[Quote] = Field(default_factory=list)


class EvidenceReport(Report):
    drugs: list[Support]


class RiskDimension(Message):
    status: Literal['no_identified_risk', 'caution', 'avoid', 'unknown']
    reason: str = Field(min_length=1)
    fact_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    next_action: str = ''


class RiskDetails(Message):
    allergy: RiskDimension
    renal: RiskDimension
    interactions: RiskDimension


class Risk(Message):
    drug_code: str
    status: Literal['no_identified_risk', 'caution', 'avoid', 'unknown']
    allergy: str = '未核對'
    renal: str = '未核對'
    interactions: str = '未核對'
    risk_details: RiskDetails | None = None
    reason: str = Field(min_length=1)
    quotes: list[Quote] = Field(default_factory=list)


class ClinicalReport(Report):
    drugs: list[Risk]


class Claim(Message):
    dimension: Literal['infection','ast','allergy','renal','interactions']
    statement: str = Field(min_length=1)
    fact_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    next_action: str = ''


class ClaimCheck(Message):
    dimension: Literal['infection','ast','allergy','renal','interactions']
    verdict: Literal['supported','unsupported','uncertain']
    reason: str = Field(min_length=1)
    fact_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    infection_match: Literal['supported','unsupported','uncertain','not_applicable'] = 'not_applicable'
    population_match: Literal['supported','unsupported','uncertain','not_applicable'] = 'not_applicable'
    drug_match: Literal['supported','unsupported','uncertain','not_applicable'] = 'not_applicable'


class Decision(Message):
    drug_code: str
    status: Literal['reviewable', 'pending', 'avoid', 'not_selected']
    reason: str = Field(min_length=1)
    evidence_refs: list[str] = Field(default_factory=list)
    fact_refs: list[str] = Field(default_factory=list)
    disagreements: list[str] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)


class SynthesisReport(Report):
    drugs: list[Decision]


class RiskCheck(Message):
    dimension: Literal['allergy','renal','interactions']
    verdict: Literal['supported','unsupported','uncertain']
    reason: str = Field(min_length=1)
    fact_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)


class ASTCheck(Message):
    assessment: Literal['susceptible','intermediate','resistant','conflicting','unknown','untested']
    claim_assessment: Literal['susceptible','intermediate','resistant','conflicting','unknown','untested','not_stated'] | None = None
    category_source_refs: list[str] = Field(default_factory=list)


class AuditItem(Message):
    drug_code: str
    verdict: Literal['supported', 'unsupported', 'uncertain']
    basis: Literal['document', 'case_fact', 'mixed'] = 'document'
    fact_refs: list[str] = Field(default_factory=list)
    fact_match: Literal['supported', 'unsupported', 'uncertain', 'not_applicable'] = 'not_applicable'
    risk_checks: list[RiskCheck] = Field(default_factory=list)
    ast_check: ASTCheck | None = None
    claim_checks: list[ClaimCheck] = Field(default_factory=list)
    infection_match: Literal['supported', 'unsupported', 'uncertain', 'not_applicable']
    population_match: Literal['supported', 'unsupported', 'uncertain', 'not_applicable']
    drug_match: Literal['supported', 'unsupported', 'uncertain', 'not_applicable']
    reason: str = Field(min_length=1)
    quotes: list[Quote] = Field(default_factory=list)


class AuditReport(Report):
    drugs: list[AuditItem]


class Input(Message):
    facts: dict[str, Any]
    ast_results: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    evidence_groups: list[dict[str, Any]] = Field(default_factory=list)
    drugs: list[str] = Field(default_factory=list)
    original_drugs: list[str] | None = None
    assessments: dict[str, Any] = Field(default_factory=dict)
    claims: list[dict[str, Any]] = Field(default_factory=list)
    validation_feedback: list[str] = Field(default_factory=list)
    citation_repairs: list[dict[str, Any]] = Field(default_factory=list)
    risk_details_required: bool = False
    ast_sources_required: bool = False
    audit_sources_required: bool = False
    atomic_claims_required: bool = False

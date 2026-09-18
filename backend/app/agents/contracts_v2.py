"""Versioned, bounded messages exchanged by the v2 agents."""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.case import Demographics, Allergies


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class RenalFacts(Message):
    egfr: float | None = None
    unit: str | None = None
    dialysis_status: str | None = None


class CaseFacts(Message):
    organism: str | None = None
    infection_site: str | None = None
    severity: str | None = None
    clinical_context: str | None = Field(default=None, max_length=4000)
    demographics: Demographics = Field(default_factory=Demographics)
    renal: RenalFacts = Field(default_factory=RenalFacts)
    allergies: Allergies = Field(default_factory=lambda: Allergies(status="unknown"))
    medication_codes: list[str] = Field(default_factory=list, max_length=100)
    data_origin: Literal["synthetic", "deidentified", "hybrid"]
    simulated_fields: list[str] = Field(default_factory=list, max_length=100)


class ASTFacts(Message):
    drug_code: str
    reported_sir: str | None = None
    interpretation_basis: str | None = None
    source_phenotype: str | None = None
    clsi_2022_phenotype: str | None = None
    method: str | None = None
    standard: str | None = None
    standard_version: str | None = None


class Evidence(Message):
    chunk_id: str
    doc_id: str
    document_version: str
    text: str = Field(max_length=16000)
    page: int | None = None
    population: str | None = None


class Finding(Message):
    statement: str = Field(min_length=1, max_length=2000)
    evidence_refs: list[str] = Field(max_length=50)
    rule_refs: list[str] = Field(max_length=100)


class Assessment(Message):
    findings: list[Finding] = Field(max_length=20)
    limitations: list[str] = Field(max_length=20)
    needs_confirmation: bool


class CaseAssessment(Assessment):
    missing_fields: list[str] = Field(max_length=30)


class ASTAssessment(Assessment):
    reviewed_drugs: list[str] = Field(max_length=100)


class DrugSupport(Message):
    drug_code: str
    evidence_refs: list[str] = Field(min_length=1, max_length=50)
    explanation: str = Field(min_length=1, max_length=2000)


class EvidenceAssessment(Assessment):
    supported_drugs: list[str] = Field(max_length=100)
    support: list[DrugSupport] = Field(max_length=100)


class ClinicalAssessment(Assessment):
    excluded_drugs: list[str] = Field(max_length=100)


class Candidate(Message):
    drug_code: str
    reason: str = Field(min_length=1, max_length=2000)
    rule_refs: list[str] = Field(max_length=100)
    evidence_refs: list[str] = Field(max_length=50)


class SynthesisOutput(Message):
    candidates: list[Candidate] = Field(max_length=100)
    avoid: list[Candidate] = Field(max_length=100)
    limitations: list[str] = Field(max_length=30)


class CaseInput(Message):
    facts: CaseFacts


class ASTInput(Message):
    facts: CaseFacts
    case_assessment: CaseAssessment
    ast_results: list[ASTFacts] = Field(max_length=100)
    allowed_drugs: list[str] = Field(max_length=100)
    rule_refs: list[str] = Field(max_length=100)


class EvidenceInput(Message):
    facts: CaseFacts
    case_assessment: CaseAssessment
    evidence: list[Evidence] = Field(max_length=50)
    allowed_drugs: list[str] = Field(max_length=100)


class ClinicalInput(Message):
    facts: CaseFacts
    case_assessment: CaseAssessment
    allowed_drugs: list[str] = Field(max_length=100)
    hard_exclusions: list[str] = Field(max_length=100)
    rule_refs: list[str] = Field(max_length=100)


class SynthesisInput(Message):
    facts: CaseFacts
    case_assessment: CaseAssessment
    ast_assessment: ASTAssessment
    evidence_assessment: EvidenceAssessment
    clinical_assessment: ClinicalAssessment
    evidence: list[Evidence] = Field(max_length=50)
    allowed_drugs: list[str] = Field(max_length=100)
    allowed_avoid: list[str] = Field(max_length=100)
    rule_refs: list[str] = Field(max_length=100)

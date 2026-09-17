"""Versioned research case contract with explicit observed/simulated provenance.

The schema deliberately models source observations separately from any later
rule interpretation.  It is an engineering contract, not a clinical standard.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)


def _aware(value: datetime | None, field: str):
    if value is not None and (value.tzinfo is None or value.utcoffset() is None):
        raise ValueError(f"{field} must include a timezone")
    return value


class Demographics(StrictModel):
    age: float | None = Field(default=None, ge=0, le=150)
    sex: str | None = None
    weight: float | None = Field(default=None, gt=0)
    weight_unit: Literal["kg", "lb"] | None = None

class Encounter(StrictModel):
    infection_site: str | None = None
    severity: str | None = None
    context: str | None = None
    observed_at: datetime | None = None

    @model_validator(mode="after")
    def timestamp_aware(self):
        _aware(self.observed_at, "encounter.observed_at"); return self


class Renal(StrictModel):
    creatinine: float | None = Field(default=None, ge=0)
    creatinine_unit: str | None = None
    egfr: float | None = Field(default=None, ge=0)
    unit: str | None = None
    calculation_method: str | None = None
    dialysis_status: str | None = None
    sampled_at: datetime | None = None

    @model_validator(mode="after")
    def fields_safe(self):
        _aware(self.sampled_at, "renal.sampled_at")
        return self


class AllergyItem(StrictModel):
    drug_code: str
    reaction: str | None = None
    severity: str | None = None


class Allergies(StrictModel):
    status: Literal["known_none", "known_present", "unknown"]
    items: list[AllergyItem] = Field(default_factory=list)

    @model_validator(mode="after")
    def status_items(self):
        if self.status == "known_present" and not self.items:
            raise ValueError("allergies.items is required for known_present")
        if self.status != "known_present" and self.items:
            raise ValueError("allergies.items must be empty unless status is known_present")
        return self


class Medication(StrictModel):
    drug_code: str
    status: str | None = None
    observed_at: datetime | None = None

    @model_validator(mode="after")
    def timestamp_aware(self):
        _aware(self.observed_at, "medications.observed_at"); return self


class Microbiology(StrictModel):
    specimen: str | None = None
    organism: str | None = None
    collected_at: datetime | None = None
    report_status: str | None = None

    @model_validator(mode="after")
    def timestamp_aware(self):
        _aware(self.collected_at, "microbiology.collected_at"); return self


class ASTResult(StrictModel):
    drug_code: str
    mic: float | None = Field(default=None, ge=0)
    comparator: Literal["=", "<", "<=", ">", ">="] | None = None
    unit: str | None = None
    reported_sir: Literal["S", "I", "R"] | None = None
    method: str | None = None
    standard: str | None = None
    standard_version: str | None = None
    source: str | None = None
    interpretation_basis: Literal["legacy", "source_report", "CLSI_2022_pheno"] = "legacy"
    source_phenotype: str | None = None
    clsi_2022_phenotype: str | None = None
    raw_measurement: dict[str, str] = Field(default_factory=dict)

class RapidIdentification(StrictModel):
    method: str | None = None
    result: str | None = None
    observed_at: datetime | None = None
    source: str | None = None

    @model_validator(mode="after")
    def timestamp_aware(self):
        _aware(self.observed_at, "rapid_identification.observed_at"); return self


class Provenance(StrictModel):
    source_system: str | None = None
    imported_at: datetime | None = None
    adapter_version: str | None = None
    source_record_id: str | None = None
    source_file_sha256: str | None = None
    simulated_fields: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def timestamp_aware(self):
        _aware(self.imported_at, "provenance.imported_at"); return self


class Case(StrictModel):
    case_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    schema_version: Literal["1.0"] = "1.0"
    is_synthetic: StrictBool
    data_origin: Literal["synthetic", "deidentified", "hybrid"] = "synthetic"
    evidence_scope: Literal["synthetic", "reference"] = "synthetic"
    external_model_allowed: StrictBool = False
    source: str | None = None
    created_at: datetime
    demographics: Demographics = Field(default_factory=Demographics)
    encounter: Encounter = Field(default_factory=Encounter)
    renal: Renal = Field(default_factory=Renal)
    allergies: Allergies = Field(default_factory=lambda: Allergies(status="unknown"))
    microbiology: Microbiology = Field(default_factory=Microbiology)
    ast_results: list[ASTResult] = Field(default_factory=list)
    rapid_identification: RapidIdentification | None = None
    medications: list[Medication] = Field(default_factory=list)
    resistance_context_ref: list[str] = Field(default_factory=list)
    policy_refs: list[str] = Field(default_factory=list)
    provenance: Provenance = Field(default_factory=Provenance)

    @field_validator("created_at")
    @classmethod
    def aware_timestamp(cls, value: datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamps must include a timezone")
        return value

    @model_validator(mode="after")
    def synthetic_only(self):
        if not self.is_synthetic and self.data_origin == "synthetic":
            raise ValueError("non-synthetic cases must identify deidentified or hybrid data_origin")
        if self.is_synthetic and self.data_origin != "synthetic":
            raise ValueError("source-derived cases must not be labelled entirely synthetic")
        if self.data_origin != "synthetic" and not self.provenance.source_system:
            raise ValueError("source-derived cases require provenance.source_system")
        if self.data_origin == "hybrid" and not self.provenance.simulated_fields:
            raise ValueError("hybrid cases require provenance.simulated_fields")
        return self


class ImportRequest(StrictModel):
    payload: dict[str, Any]
    format: Literal["canonical", "alternate"] = "canonical"


class AlternateCase(StrictModel):
    """Small second source shape used to prove adapters are replaceable."""
    id: str
    synthetic: StrictBool = True
    patient: dict[str, Any] = Field(default_factory=dict)
    infection: dict[str, Any] = Field(default_factory=dict)
    lab: dict[str, Any] = Field(default_factory=dict)
    allergy: dict[str, Any] = Field(default_factory=dict)
    observed_at: datetime

    @field_validator("observed_at")
    @classmethod
    def aware_timestamp(cls, value: datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamps must include a timezone")
        return value

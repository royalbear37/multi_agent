"""Configurable budgets for the current six-role analysis workflow."""
from dataclasses import dataclass

from .runtime_v2 import setting


@dataclass(frozen=True)
class AgentLedLimits:
    max_calls: int = 40
    max_retries: int = 3
    timeout_seconds: int = 1200
    input_chars: int = 1000000
    evidence_text_chars: int = 500000
    evidence_context_chars: int = 750000
    retrieval_drugs: int = 30
    drug_search_hits: int = 4
    infection_search_hits: int = 12
    guideline_search_hits: int = 8
    feedback_items: int = 200
    role_timeout_seconds: int = 300
    synthesis_timeout_seconds: int = 600
    audit_timeout_seconds: int = 900

    @classmethod
    def from_env(cls):
        fields = {
            'max_calls': ('LLM_AGENT_LED_MAX_CALLS', 6, 96),
            'max_retries': ('LLM_AGENT_LED_MAX_RETRIES', 0, 5),
            'timeout_seconds': ('LLM_AGENT_LED_TIMEOUT_SECONDS', 10, 14400),
            'input_chars': ('LLM_AGENT_LED_MAX_INPUT_CHARS', 2000, 2000000),
            'evidence_text_chars': ('LLM_AGENT_EVIDENCE_TEXT_CHARS', 1000, 1500000),
            'evidence_context_chars': ('LLM_AGENT_EVIDENCE_CONTEXT_CHARS', 1000, 1800000),
            'retrieval_drugs': ('LLM_AGENT_RETRIEVAL_MAX_DRUGS', 1, 512),
            'drug_search_hits': ('LLM_AGENT_DRUG_SEARCH_HITS', 1, 20),
            'infection_search_hits': ('LLM_AGENT_INFECTION_SEARCH_HITS', 1, 50),
            'guideline_search_hits': ('LLM_AGENT_GUIDELINE_SEARCH_HITS', 1, 50),
            'feedback_items': ('LLM_AGENT_VALIDATION_FEEDBACK_ITEMS', 30, 1000),
            'role_timeout_seconds': ('LLM_AGENT_LED_ROLE_TIMEOUT_SECONDS', 10, 1800),
            'synthesis_timeout_seconds': ('LLM_AGENT_SYNTHESIS_TIMEOUT_SECONDS', 10, 1800),
            'audit_timeout_seconds': ('LLM_AGENT_AUDIT_TIMEOUT_SECONDS', 10, 1800),
        }
        defaults = cls()
        values = {name: setting(env, getattr(defaults, name), low, high)
                  for name, (env, low, high) in fields.items()}
        # Do not let a source-only allowance exceed the complete input allowance.
        values['evidence_context_chars'] = min(values['evidence_context_chars'], values['input_chars'] - 1000)
        values['evidence_text_chars'] = min(values['evidence_text_chars'], values['evidence_context_chars'])
        return cls(**values)

    @property
    def audit_input_chars(self):
        return self.input_chars - 2000

    def role_timeout(self, agent):
        if agent.id == 'synthesis_agent':
            return self.synthesis_timeout_seconds
        if agent.id == 'evidence_audit':
            return self.audit_timeout_seconds
        return self.role_timeout_seconds

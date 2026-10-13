"""Bounded batches with separate coverage and citation-repair queues."""
import copy
import math
from collections import Counter, deque

from .input_context import assessment_source_refs

BATCHED_ROLES = {'clinical_agent', 'synthesis_agent'}
BATCH_SIZE = 3


def batch_size(drugs, max_calls):
    # Four other roles need one initial call each. Explicit smaller call budgets
    # use larger batches, rather than skipping the case/AST roles altogether.
    batches = max(1, (max_calls - 4) // len(BATCHED_ROLES))
    return max(BATCH_SIZE, math.ceil(len(drugs) / batches))


def initial_calls(agent_id, drugs, size=BATCH_SIZE):
    return max(1, math.ceil(len(drugs) / size)) if agent_id in BATCHED_ROLES else 1


def batch_context(agent_id, original, drugs):
    data = copy.deepcopy(original)
    data['drugs'] = list(drugs)
    data['claims'] = [c for c in data['claims'] if c['drug_code'] in drugs]
    for report in data['assessments'].values():
        if 'drugs' in report:
            report['drugs'] = [r for r in report['drugs'] if r['drug_code'] in drugs]
        report['issues'] = [i for i in report.get('issues', []) if i.get('drug_code') in (None, *drugs)]
    if agent_id == 'clinical_agent' and data.get('evidence_groups'):
        data['evidence_groups'] = [g for g in data['evidence_groups'] if g.get('drug_code') in (None, *drugs)]
        refs = {ref for g in data['evidence_groups'] for ref in g['evidence_refs']}
        data['evidence'] = [e for e in data['evidence'] if e['chunk_id'] in refs]
    elif agent_id == 'synthesis_agent':
        refs = assessment_source_refs(data['assessments'])
        data['evidence'] = [e for e in data['evidence'] if e['chunk_id'] in refs]
    elif agent_id == 'evidence_audit':
        refs = assessment_source_refs(data['claims'])
        data['evidence'] = [e for e in data['evidence'] if e['chunk_id'] in refs]
    # Original AST indexes and all patient facts are preserved in every batch.
    return data


class AgentSchedule:
    def __init__(self, agent_id, drugs, max_retries, size=BATCH_SIZE):
        self.agent_id = agent_id
        self.order = list(drugs)
        self.pending = set(drugs)
        self.max_retries = max_retries
        self.retries = Counter()
        self.initial = deque()
        self.rows = deque()
        self.citations = deque()
        size = size if agent_id in BATCHED_ROLES else max(1, len(drugs))
        for offset in range(0, max(1, len(drugs)), size):
            self.initial.append(dict(kind='initial', drugs=drugs[offset:offset + size], feedback=[], repairs=[]))

    def pop(self):
        for queue in (self.initial, self.rows, self.citations):
            if queue:
                return queue.popleft()
        return None

    def finish(self, job, unresolved, diagnostics, repairs=()):
        self.pending.difference_update(job['drugs'])
        self.pending.update(unresolved)
        self.order += [d for d in unresolved if d not in self.order]
        by_drug = {r['drug_code']: r for r in repairs}
        if not job['drugs'] and diagnostics:
            key = (None, 'row_repair')
            if self.retries[key] < self.max_retries:
                self.retries[key] += 1
                self.rows.append(dict(kind='row_repair', drugs=[], feedback=diagnostics, repairs=[]))
        for kind, queue in [('row_repair', self.rows), ('citation_repair', self.citations)]:
            eligible = []
            for drug in unresolved:
                if (drug in by_drug) != (kind == 'citation_repair'):
                    continue
                key = (drug, kind)
                if self.retries[key] < self.max_retries:
                    self.retries[key] += 1
                    eligible.append(drug)
            # Omitted clinical/synthesis rows and citation repairs get a single
            # assigned drug, so repeatedly answering the first row makes progress.
            size = 1 if kind == 'citation_repair' or self.agent_id in BATCHED_ROLES else max(1, len(eligible))
            for offset in range(0, len(eligible), size):
                targets = eligible[offset:offset + size]
                feedback = [s for s in diagnostics if not any(s.startswith(d + ':')
                            for d in job['drugs'] if d not in targets)]
                queue.append(dict(kind=kind, drugs=targets, feedback=feedback,
                                  repairs=[by_drug[d] for d in targets if d in by_drug]))

    @property
    def unresolved(self):
        return [d for d in self.order if d in self.pending]

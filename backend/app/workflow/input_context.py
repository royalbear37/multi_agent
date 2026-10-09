"""Model context keeps source identity and meaning; storage metadata stays in snapshots."""
import copy


SOURCE_FIELDS = (
    'chunk_id', 'doc_id', 'text', 'document_title', 'document_version',
    'location', 'population', 'document_kind', 'jurisdiction', 'study_design',
    'source_document_id', 'source_url', 'is_synthetic', 'external_model_allowed',
)


def compact_sources(evidence):
    return [{k: copy.deepcopy(e[k]) for k in SOURCE_FIELDS if k in e} for e in evidence]


def assessment_source_refs(value):
    """Keep every specialist reference, including nested risk dimensions and quotes."""
    refs = set()
    if isinstance(value, dict):
        refs.update(value.get('evidence_refs', []))
        if value.get('chunk_id'):
            refs.add(value['chunk_id'])
        for item in value.values():
            refs.update(assessment_source_refs(item))
    elif isinstance(value, list):
        for item in value:
            refs.update(assessment_source_refs(item))
    return refs

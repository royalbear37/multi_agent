"""Select immutable source spans on the wire; store ordinary quotes in run history."""
from __future__ import annotations

import copy


def source_spans(text: str, limit: int = 1400) -> list[dict]:
    """Lossless contiguous spans, preferring paragraph/line/word boundaries.

    All spans remain in source order in the model input. Selection never removes
    surrounding population/chapter qualifiers from the supplied context.
    """
    spans, start = [], 0
    while start < len(text):
        end = min(start + limit, len(text))
        if end < len(text):
            for separator in ('\n\n', '\n', '. ', ' '):
                boundary = text.rfind(separator, start + limit // 2, end)
                if boundary >= 0:
                    end = boundary + len(separator)
                    break
        spans.append({'span_id': f'S{len(spans)+1}', 'text': text[start:end],
                      'start': start, 'end': end})
        start = end
    if len(spans) > 1 and len(spans[-1]['text']) < 10:
        tail = spans.pop()
        spans[-1]['text'] += tail['text']
        spans[-1]['end'] = tail['end']
    return spans


def selection_schema(output_type):
    """Transport-only contract; canonical/API quote schema stays unchanged."""
    schema = copy.deepcopy(output_type.model_json_schema())
    # Explicit transport fields prevent optional defaults from hiding omitted
    # source selections. Empty arrays remain valid for honest uncertainty.
    for definition in [schema, *schema.get('$defs', {}).values()]:
        properties = definition.get('properties', {})
        explicit = [name for name in ('quotes', 'fact_refs', 'evidence_refs', 'missing_fields', 'next_action', 'claims', 'claim_checks')
                    if name in properties]
        if explicit:
            definition['required'] = list(dict.fromkeys(definition.get('required', []) + explicit))
        for field in ('claims','claim_checks'):
            if field in properties:
                properties[field].update(minItems=5,maxItems=5)
        if 'quotes' in properties:
            properties['quotes']['description'] = (
                'Required on EACH drug row, sibling of drug_code, not on the report or inside risk_details. '
                'Select actual chunk_id/span_ids supporting this row. evidence_refs alone are not quotations. '
                'Use [] only when no supplied passage supports the assessment; retain uncertainty.')
    ast = schema.get('$defs', {}).get('ASTItem')
    if ast:
        ast['required'] = list(dict.fromkeys(ast.get('required', []) + ['category_source_refs']))
    audit=schema.get('$defs',{}).get('AuditItem')
    if audit:
        audit['properties']['ast_check']={'$ref':'#/$defs/ASTCheck'}
        audit['required']=list(dict.fromkeys(audit.get('required',[])+['ast_check']))
        check=schema['$defs']['ASTCheck']
        check['properties']['claim_assessment']={'type':'string','enum':['susceptible','intermediate','resistant','conflicting','unknown','untested','not_stated'],
            'description':'Category asserted about this patient in the incoming claim or your audit reason. not_stated only when neither makes an individual AST assertion; do not substitute the actual source category here.'}
        check['required']=list(dict.fromkeys(check.get('required',[])+['claim_assessment','category_source_refs']))
    risk = schema.get('$defs', {}).get('Risk')
    if risk:
        # Legacy prose stays readable in stored runs but is not a second live
        # output format. Asking for both led the model to nest details there.
        for field in ('allergy','renal','interactions'):
            risk['properties'].pop(field, None)
        risk['properties']['risk_details'] = {'$ref':'#/$defs/RiskDetails'}
        risk['required'] = list(dict.fromkeys(risk.get('required', []) + ['risk_details']))
    if 'Quote' in schema.get('$defs', {}):
        schema['$defs']['Quote'] = {
            'type': 'object', 'additionalProperties': False,
            'properties': {
                'chunk_id': {'type': 'string'},
                'span_ids': {'type': 'array', 'minItems': 1, 'maxItems': 4,
                             'items': {'type': 'string'}},
            },
            'required': ['chunk_id', 'span_ids'],
        }
    return schema


def resolve_selections(output, sources: dict[str, dict[str, dict]]):
    """Never accept model-written quotes or unknown/cross-source selectors."""
    if isinstance(output, list):
        return [resolve_selections(value, sources) for value in output]
    if not isinstance(output, dict):
        return output
    result = {}
    for key, value in output.items():
        if key != 'quotes':
            result[key] = resolve_selections(value, sources)
            continue
        if not isinstance(value, list):
            raise ValueError('citation selections must be a list')
        quotes, seen = [], set()
        for selection in value:
            if not isinstance(selection, dict) or set(selection) != {'chunk_id', 'span_ids'}:
                raise ValueError('citation requires source and span identifiers')
            cid, ids = selection['chunk_id'], selection['span_ids']
            if not isinstance(cid, str) or cid not in sources or not isinstance(ids, list) or not 1 <= len(ids) <= 4:
                raise ValueError('unknown citation source or invalid selection')
            for sid in ids:
                if not isinstance(sid, str) or sid not in sources[cid]:
                    raise ValueError('unknown citation span')
                if (cid, sid) not in seen:
                    quotes.append({'chunk_id': cid, 'quote': sources[cid][sid]['text']})
                    seen.add((cid, sid))
        result[key] = quotes
    return result

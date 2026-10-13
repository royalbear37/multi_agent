"""Strict API schema projection; stored contracts and local checks stay intact."""
import copy
import json


def strict_output_schema(schema):
    result = copy.deepcopy(schema)
    shared = {}
    selectors = {}

    def project(value):
        if isinstance(value, list):
            return [project(item) for item in value]
        if not isinstance(value, dict):
            return value
        value = {key: project(item) for key, item in value.items() if key != 'default'}
        if 'properties' in value:
            value['required'] = list(value['properties'])
            value['additionalProperties'] = False
        # Each source list is reused across several checks. Share its enum to
        # avoid multiplying API enum limits and repeating long lists in input.
        if len(value.get('enum', [])) >= 16 and value.get('type') == 'string':
            signature = json.dumps(value['enum'], ensure_ascii=False)
            if signature not in selectors:
                name = f'StrictSourceSelection{len(selectors) + 1}'
                selectors[signature] = name
                shared[name] = {'type': 'string', 'enum': value['enum']}
            return {'$ref': '#/$defs/' + selectors[signature],
                    **{key: value[key] for key in ('description', 'title') if key in value}}
        return value

    result = project(result)
    result.setdefault('$defs', {}).update(shared)

    def enum_count(value):
        if isinstance(value, dict):
            return len(value.get('enum', [])) + sum(enum_count(v) for k, v in value.items() if k != 'enum')
        if isinstance(value, list):
            return sum(enum_count(v) for v in value)
        return 0

    # Strict APIs cap total enum entries. For unusually large source catalogs,
    # keep string selection in the API and enforce the exact IDs with the
    # original bound schema in checked_wire, never by trusting model prose.
    if enum_count(result) > 1000:
        for name in shared:
            result['$defs'][name].pop('enum', None)
    return result

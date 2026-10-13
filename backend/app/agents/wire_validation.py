"""Validate the exact transport contract before defaults or source restoration."""
import copy
from jsonschema import Draft202012Validator


def checked_wire(raw, schema):
    errors=list(Draft202012Validator(schema).iter_errors(raw))
    diagnostics=[]; bad_rows=set(); envelope_bad=False
    for error in errors:
        path=list(error.absolute_path)
        # Report schema/path, not raw values or untrusted model prose.
        suffix=': '+', '.join(k for k in error.validator_value if k not in error.instance) if error.validator=='required' and isinstance(error.instance,dict) else ''
        diagnostics.append('.'.join(map(str,path))+': '+error.validator+suffix)
        if path == ['drugs'] and error.validator in {'minItems', 'maxItems'}:
            continue  # Preserve valid rows; the scheduler repairs missing assignments.
        if len(path)>1 and path[0]=='drugs' and isinstance(path[1],int): bad_rows.add(path[1])
        else: envelope_bad=True
    if envelope_bad:
        return None, diagnostics
    value=copy.deepcopy(raw)
    if isinstance(value,dict) and isinstance(value.get('drugs'),list):
        value['drugs']=[row for i,row in enumerate(value['drugs']) if i not in bad_rows]
    return value, diagnostics

"""Expose selectable source identifiers without deciding drug suitability."""
import copy


def ast_source_options(rows):
    options=[]
    for index,row in enumerate(rows):
        basis=row.get('interpretation_basis')
        selected=('clsi_2022_phenotype' if basis=='CLSI_2022_pheno' else
                  'source_phenotype' if basis=='source_report' else 'reported_sir')
        options.append(dict(drug_code=row.get('drug_code'), interpretation_basis=basis,
            selected_field=f'ast_results.{index}.{selected}', selected_value=row.get(selected),
            categorical_fields=[dict(ref=f'ast_results.{index}.{field}',value=row.get(field))
                for field in ('reported_sir','source_phenotype','clsi_2022_phenotype')
                if str(row.get(field) or '').strip().casefold() in {'s','i','r','susceptible','intermediate','resistant'}]))
    return options


def bind_source_options(schema, options, evidence_ids):
    """Wire-only enums; server validation remains authoritative.

    Do not repair an invalid model selection by guessing from its prose. An
    original-report category may be listed for conflict comparison even when
    the selected CLSI category is absent; it never substitutes for that value.
    """
    schema=copy.deepcopy(schema)
    category_refs=[field['ref'] for option in options for field in option['categorical_fields']]
    def visit(value):
        if isinstance(value,list):
            for item in value: visit(item)
        elif isinstance(value,dict):
            properties=value.get('properties',{})
            for field,choices in [('category_source_refs',category_refs),('evidence_refs',list(evidence_ids))]:
                if field in properties:
                    spec=properties[field]
                    spec['items']={'type':'string','enum':choices} if choices else {'type':'string'}
                    if not choices: spec['maxItems']=0
                    spec['description']='Select exact identifiers from the supplied source options. Never return source descriptions, titles or quotations. Use [] if no valid source supports the claim.'
            if 'chunk_id' in properties and 'span_ids' in properties and evidence_ids:
                properties['chunk_id']['enum']=list(evidence_ids)
            for item in value.values(): visit(item)
    visit(schema)
    return schema

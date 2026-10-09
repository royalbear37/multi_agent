"""Check categorical source links only; never calculate susceptibility breakpoints."""
import re
from .risk_details import fact_value

CATEGORIES={'s':'susceptible','susceptible':'susceptible',
            'i':'intermediate','intermediate':'intermediate',
            'r':'resistant','resistant':'resistant'}


def validate_ast_sources(row, data):
    if not data.get('ast_sources_required'):
        return
    sources={'ast_results':data.get('ast_results',[])}
    valid=[]
    invalid=[]
    for path in row.get('category_source_refs',[]):
        match=re.fullmatch(r'ast_results\.(\d+)\.(reported_sir|source_phenotype|clsi_2022_phenotype)',path)
        item=fact_value(sources,'.'.join(path.split('.')[:2])) if match else None
        value=fact_value(sources,path) if match else None
        category=CATEGORIES.get(str(value).strip().casefold())
        basis=item.get('interpretation_basis') if isinstance(item,dict) else None
        selected=('clsi_2022_phenotype' if basis=='CLSI_2022_pheno' else
                  'source_phenotype' if basis=='source_report' else 'reported_sir')
        if not isinstance(item,dict) or item.get('drug_code')!=row['drug_code'] or not category:
            invalid.append(path)
        else:
            valid.append({'field':path,'value':value,'category':category,'selected_basis':match[2]==selected})
    row['category_sources']=valid
    states={source['category'] for source in valid}
    primary_states={source['category'] for source in valid if source['selected_basis']}
    asserted=row['assessment']
    needs_sources=asserted in {'susceptible','intermediate','resistant','conflicting'}
    mismatch=(asserted in {'susceptible','intermediate','resistant'} and (primary_states!={asserted} or states!={asserted})) or (asserted=='conflicting' and len(states)<2)
    if needs_sources and (invalid or not valid or mismatch):
        row['model_assessment']=asserted
        row['model_reason']=row['reason']
        row['assessment']='unknown'
        row['reason']='模型判讀的來源未通過核對；需選擇本藥判讀依據的非空類別欄位。這是來源連結問題，不能從原始數值推測敏感性；請核對來源或重新分析。'
        row['source_validation']={'status':'unconfirmed','invalid_refs':invalid}
    else:
        row['source_validation']={'status':'confirmed' if valid and not invalid and (primary_states or asserted=='conflicting') else 'not_available','invalid_refs':invalid}

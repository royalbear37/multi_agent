"""Necessary source-scope checks only; matching terms never prove clinical support."""
import re
from itertools import permutations


def named_drug(drug, text):
    parts=re.findall(r'[a-z0-9]+',str(drug).casefold())
    # Ingredient identity only: order, conjunctions and the documented acid
    # spelling do not establish or change an indication.
    if not parts: return False
    aliases={'clavulanate':r'(?:clavulanate|clavulanic[\s_]+acid)'}
    ingredients=[aliases.get(part,re.escape(part)) for part in parts]
    # A compound name must be one contiguous phrase, not components scattered
    # across unrelated sentences. Common label salt suffixes may intervene.
    salt=r'(?:[\s_]+(?:sodium|potassium|trihydrate|anhydrous|hydrochloride|monohydrate))?'
    separator=r'[\s_,/+&-]+(?:and[\s_,/+&-]+)?'
    orders=permutations(ingredients) if len(ingredients)<=4 else [ingredients]
    return any(re.search(r'(?<![a-z0-9])'+separator.join(p+salt for p in order)+r'(?![a-z0-9])',str(text),re.I) for order in orders)


TOPICS = {
    'allergy': r'hypersensitiv|allerg|anaphyla|過敏',
    'renal': r'renal|kidney|creatinine|\bcrcl\b|\be?gfr\b|glomerular filtration|hemodialysis|腎|肌酸酐',
    'interactions': r'interaction|concomitant|coadminist|co-administ|concurrent|co-use|synerg|antagonis|inactivat|交互作用|併用|協同|拮抗|失活',
}


def ingredient_key(value):
    value = re.sub(r'\b(?:anhydrous|sodium|potassium|trihydrate|hydrochloride|monohydrate)\b', '', value, flags=re.I)
    value = re.sub(r'clavulanic\s+acid', 'clavulanate', value, flags=re.I)
    return re.sub(r'[^a-z0-9]', '', value.casefold())


def label_identity_issue(drug, source):
    if source.get('document_kind') != 'drug_label':
        return None
    headings = (source.get('location') or {}).get('heading_path') or []
    # The original product heading is authoritative over an uploaded short title.
    title = headings[0] if headings else source.get('document_title', '')
    product = re.split(r'\b(?:INJECTION|TABLETS?|CAPSULES?|POWDER|SUSPENSION|FOR ORAL)\b', title, maxsplit=1, flags=re.I)[0]
    product = re.sub(r'\((?:MONOHYDRATE|MACROCRYSTALS|ANHYDROUS|\s|/)+\)', '', product, flags=re.I)
    parenthetical = re.search(r'\(([^()]*)\)', product)
    ingredient_text = parenthetical.group(1) if parenthetical and named_drug(drug, parenthetical.group(1)) else product
    parts = [ingredient_key(p) for p in re.split(r'\s*(?:,|/|\+|\band\b)\s*', ingredient_text, flags=re.I) if ingredient_key(p)]
    requested = {ingredient_key(p) for p in drug.split('_')}
    if len(parts) > 1 and named_drug(drug, ingredient_text) and set(parts) != requested:
        return '來源為不同成分組合的複方標示，不能直接當成本藥標示'
    if headings and not named_drug(drug, title):
        return '原始產品標題未辨識本藥；上傳文件簡稱不能替代產品身分'
    return None


def source_scope_issues(drug, dimension, quotes, evidence, statement=''):
    sources = {e['chunk_id']: e for e in evidence}
    issues = []
    anchored = False
    anchored_quotes = []
    for quote in quotes:
        source = sources.get(quote['chunk_id'], {})
        text = quote['quote']
        identity = label_identity_issue(drug, source)
        label_anchor = source.get('document_kind') == 'drug_label' and named_drug(drug, source.get('document_title','') + ' ' + ' '.join((source.get('location') or {}).get('heading_path') or []))
        if identity:
            issues.append(quote['chunk_id'] + '：' + identity)
        elif named_drug(drug, text) or label_anchor:
            anchored = True
            anchored_quotes.append(quote)
        table = re.search(r'Table\s+[\d.]+\s*[^A-Za-z\n]*([A-Za-z-]+)\s+(?:suggested\s+)?dos(?:es|ing|age)',text,re.I)
        if table and not named_drug(drug,table.group(1)):
            issues.append(quote['chunk_id']+'：表格標題指向其他藥品，不能以同批其他引文補足本表的藥品身分')
    if quotes and not anchored:
        issues.append('選段未辨識本藥或本藥標示')
    if quotes and dimension in TOPICS:
        text = ' '.join(q['quote'] for q in anchored_quotes)
        if not re.search(TOPICS[dimension], text, re.I):
            issues.append('選取原文未包含本風險面向；不能以其他章節或文件標題替代')
        if dimension == 'renal' and re.search(r'無[需須].{0,6}調整|不[需須用].{0,6}調整|no.{0,12}(?:dose |dosage )?adjustment', statement, re.I):
            def renal_dosing_passage(q):
                passage=re.sub(r'\[see[^\]]*\]|\(see[^)]*\)','',q['quote'],flags=re.I)
                if not re.search(TOPICS['renal'],passage,re.I): return False
                direct=re.search(r'no.{0,20}(?:dos(?:e|age).{0,20}(?:adjust|alter|modif)|(?:adjustment|alteration|modification).{0,20}dos(?:e|age))|dos(?:e|age).{0,20}(?:adjustments?|alterations?|modifications?).{0,35}(?:not (?:necessary|required)|unnecessary)|無[需須].{0,8}調整.{0,4}(?:劑量|用量)',passage,re.I)
                threshold=re.search(r'(?:creatinine clearance|\bcrcl\b|\be?gfr\b|glomerular filtration).{0,100}\d+\s*mL|\d+\s*mL.{0,100}(?:creatinine clearance|\bcrcl\b|\be?gfr\b|glomerular filtration)',passage,re.I)
                dosing=re.search(r'dos(?:e|age).{0,70}(?:adjust|reduc)|(?:adjust|reduc).{0,70}dos(?:e|age)',passage,re.I)
                return bool(direct or (threshold and dosing))
            if not any(renal_dosing_passage(q) for q in anchored_quotes):
                issues.append('腎功能無需調整的聲明缺少原文劑量調整依據；一般監測或老年段落不足')
        if dimension == 'interactions':
            # Verify a named interacting medicine actually occurs in the quote.
            # This is lexical source tracing, not a list of clinical interactions.
            medicine=r'([A-Za-z][A-Za-z-]{3,}(?:\s+acid)?)'
            mentions = re.findall(r'(?:與|和|併用|合用|使用|服用|避免|禁用|停用)\s*'+medicine, statement)
            mentions += re.findall(medicine+r'[）)]?\s*(?:的|不應|不可|應)?(?:與|和|合用|併用|交互作用)',statement)
            for name in mentions:
                if named_drug(drug, name): continue
                if not re.search(r'(?<![a-z])'+re.escape(name)+r's?(?![a-z])', text, re.I):
                    issues.append('交互作用聲明中的 '+name+' 未出現在所選原文，需核對專屬來源')
    return list(dict.fromkeys(issues))

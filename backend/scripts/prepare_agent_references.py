"""Download versioned public labeling and extract WHO pages without paraphrasing."""
import argparse
import hashlib
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path


def fetch(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent':'AntibioticResearchPrototype/1.0'}), timeout=40).read()


def label_sections(tree):
    """Keep nested headings and table labels with their own verbatim text."""
    ns = {'h': 'urn:hl7-org:v3'}
    result = []
    def visit(section, parents=(), included=False):
        title = section.find('h:title', ns)
        heading = ' '.join(' '.join(title.itertext()).split()) if title is not None else ''
        path = parents + ((heading,) if heading else ())
        included = included or bool(re.search('indication|contraindication|warning|precaution|interaction|specific population|microbiology', heading, re.I))
        body = section.find('h:text', ns)
        if included and body is not None:
            text = ' '.join(' '.join(body.itertext()).split())
            if text: result.append('## ' + ' / '.join(path) + '\n\n' + text)
        for child in section.findall('h:component/h:section', ns): visit(child, path, included)
    for section in tree.findall('h:component/h:structuredBody/h:component/h:section', ns): visit(section)
    return result


def extract_who_lower_uti(who):
    from pypdf import PdfReader
    reader=PdfReader(who)
    parts=['# WHO AWaRe antibiotic book — lower urinary tract infection\nSource: https://www.who.int/publications/i/item/9789240062382\nVersion: 2022. Verbatim page extraction; check original tables.\n']
    for page in range(294,308):
        population = 'Adults infographic' if page in (296,297) else 'Children infographic' if page in (298,299) else 'Chapter narrative and tables; follow population qualifiers'
        parts.append(f'## WHO PDF page {page} (printed page {page-16}) — {population}\n\n'+reader.pages[page-1].extract_text())
    return '\n\n'.join(parts)


def prepare(case_path, who, out):
    out.mkdir(parents=True,exist_ok=True)
    case=json.loads(case_path.read_text(encoding='utf-8'))
    drugs=sorted({x['drug_code'] for x in case['ast_results']} | {'fosfomycin','tizanidine'})
    manifest=[]
    for drug in drugs:
        query=drug.replace('_',' ')
        url='https://dailymed.nlm.nih.gov/dailymed/services/v2/spls.json?'+urllib.parse.urlencode({'drug_name':query,'pagesize':100})
        try:
            records=json.loads(fetch(url))['data']
            candidates=[r for r in records if not any(t in r['title'] for t in ('OPHTHALMIC','OTIC','TOPICAL','CREAM','OINTMENT','VETERINARY'))]
            parenteral={'amikacin','ampicillin_sulbactam','aztreonam','cefazolin','ceftriaxone','ertapenem','cefepime','gentamicin','imipenem','meropenem','piperacillin_tazobactam'}
            forms=('INJECTION',) if drug in parenteral else ('TABLET','CAPSULE','GRANULES')
            candidates=[r for r in candidates if any(f in r['title'] for f in forms)]
            if not candidates: raise ValueError('No systemic label found')
            label=candidates[0]
            sid=label['setid']; source=f'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={sid}'
            raw=fetch(f'https://dailymed.nlm.nih.gov/dailymed/services/v2/spls/{sid}.xml')
            (out/(drug+'.xml')).write_bytes(raw)
            sections=label_sections(ET.fromstring(raw))
            if not sections: raise ValueError('No relevant sections')
            content=f"# {label['title']}\n\nDrug identifier: {drug}\nSource: {source}\nJurisdiction: United States labeling; not local hospital policy\nSPL version: {label['spl_version']}; published: {label['published_date']}\n\n"+'\n\n'.join(sections)
            path=out/(drug+'.md'); path.write_text(content,encoding='utf-8')
            manifest.append(dict(filename=path.name,title='DailyMed '+drug,version=f"SPL-{label['spl_version']}-{label['published_date']}",source_url=source,jurisdiction='US',document_kind='drug_label',population='mixed',is_synthetic=False,original_sha256=hashlib.sha256(raw).hexdigest()))
            print(drug, 'OK', len(content), flush=True)
        except Exception as exc:
            print(drug, 'UNAVAILABLE', type(exc).__name__, str(exc)[:100], flush=True)
    # Complete lower-UTI chapter, including adult/child qualifications and recommendations.
    (out/'who-lower-uti.md').write_text(extract_who_lower_uti(who),encoding='utf-8')
    manifest.append(dict(filename='who-lower-uti.md',title='WHO AWaRe lower UTI chapter',version='2022',source_url='https://www.who.int/publications/i/item/9789240062382',jurisdiction='WHO global guidance',document_kind='guideline',population='mixed',is_synthetic=False,original_sha256=hashlib.file_digest(who.open('rb'),'sha256').hexdigest()))
    (out/'unrelated.md').write_text('# Unrelated evidence fixture\nThis document describes storage of laboratory equipment. It provides no antibiotic treatment recommendation.',encoding='utf-8')
    manifest.append(dict(filename='unrelated.md',title='Unrelated evidence test',version='1',population='all',is_synthetic=False,document_kind='test_negative_control',policy_refs=['agent-unrelated-evidence']))
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--case',type=Path,required=True); p.add_argument('--who',type=Path,required=True); p.add_argument('--out',type=Path,required=True); a=p.parse_args()
    prepare(a.case,a.who,a.out)

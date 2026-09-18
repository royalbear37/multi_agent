"""Offline checks of the live-verification report, with no API calls."""
import json
from pathlib import Path
import runpy
import subprocess
import sys

import pytest

SCRIPT = Path(__file__).parents[1] / 'scripts' / 'verify_live_workflow.py'
HELPERS = runpy.run_path(str(SCRIPT))


def run_fixture(gate='ready_for_review', output=None):
    return {'mode': 'multi-agent', 'gate_status': gate, 'errors': [],
            'output': output, 'evidence_snapshots': [],
            'nodes': [{'node_id':'evidence_retrieval', 'output':{'population_filter':{'matched':0}}}]}


def test_withheld_output_is_not_reported_as_success():
    summary = HELPERS['verification_summary']({'results':[run_fixture('needs_confirmation')]})
    assert not HELPERS['verification_passed'](summary)
    valid = HELPERS['verification_summary']({'results':[run_fixture(output={'candidates':[], 'avoid':[]})]})
    assert HELPERS['verification_passed'](valid)
    assert summary['runs'][0]['nodes'][0]['output']['population_filter'] == {'matched':0}
    item = {'drug_code':'fixture-drug'}
    contradictory = HELPERS['verification_summary']({'results':[
        run_fixture(output={'candidates':[item], 'avoid':[dict(item)]})
    ]})
    assert not HELPERS['verification_passed'](contradictory)


def test_report_cannot_overwrite_earlier_diagnostic(tmp_path):
    summary = HELPERS['verification_summary']({'results':[run_fixture()]})
    saved = HELPERS['save_verification'](tmp_path, summary)
    original = saved.read_bytes()
    with pytest.raises(FileExistsError):
        HELPERS['save_verification'](tmp_path, {'runs':[]})
    assert saved.read_bytes() == original


def test_inspect_legacy_report_offline_does_not_require_app_or_model(tmp_path):
    report = tmp_path / 'legacy.json'
    report.write_text(json.dumps({'benchmark_id':'fixture', 'runs':[
        {'mode':'single-agent', 'gate_status':'blocked', 'errors':[{'code':'OUTPUT_SCHEMA_INVALID'}],
         'output':None}
    ]}), encoding='utf-8')
    result = subprocess.run([sys.executable, str(SCRIPT), '--inspect', str(report)],
                            capture_output=True, text=True, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary['software_checks_passed'] is False
    assert summary['runs'][0]['reference_snapshots_available'] is False
    assert summary['runs'][0]['error_codes'] == ['OUTPUT_SCHEMA_INVALID']
    assert summary['clinical_support'] == 'not_evaluated'

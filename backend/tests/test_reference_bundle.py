import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/'backend/scripts/install_reference_bundle.py'
spec=importlib.util.spec_from_file_location('install_reference_bundle',SCRIPT)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def test_bundle_verified_and_imported_into_clean_database(tmp_path):
    assert len(module.verified_files(ROOT/'data/public_references/dailymed'))==20
    env={**os.environ,'PROTOTYPE_DB_PATH':str(tmp_path/'prototype.db')}
    result=subprocess.run([sys.executable,str(SCRIPT)],cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8')
    assert result.returncode==0,result.stderr
    report=json.loads(result.stdout)
    assert report['verified']==20 and len(report['documents'])==20 and report['model_calls']==0
    assert (tmp_path/'documents/rag.sqlite3').exists()


def test_modified_reference_is_rejected_before_import(tmp_path):
    manifest=json.loads((ROOT/'data/public_references/dailymed/manifest.json').read_text(encoding='utf-8'))[:1]
    (tmp_path/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
    (tmp_path/manifest[0]['filename']).write_text('changed content',encoding='utf-8')
    with pytest.raises(ValueError,match='Hash mismatch'):module.verified_files(tmp_path)

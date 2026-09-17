"""Historical regressions explicitly pin their original fictional fixtures.

Production defaults use source phenotypes; test_reported_cohort covers that path.
"""
from pathlib import Path
import pytest

@pytest.fixture(autouse=True)
def pin_historical_fixture_policy(request, monkeypatch):
    root = Path(__file__).resolve().parents[2]
    if request.node.path.name not in {'test_reported_cohort.py', 'test_prepare_demo.py'}:
        monkeypatch.setenv('PROTOTYPE_RULE_CONFIG', str(root / 'configs/demo/rules.json'))
        monkeypatch.setenv('PROTOTYPE_FIXTURE_DIR', str(root / 'data/synthetic'))
    else:
        monkeypatch.delenv('PROTOTYPE_RULE_CONFIG', raising=False)
        monkeypatch.delenv('PROTOTYPE_FIXTURE_DIR', raising=False)
        monkeypatch.setenv('PROTOTYPE_CATALOG_PATH', str(root / 'data/local/test-catalog-absent.json'))

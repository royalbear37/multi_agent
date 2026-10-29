"""Read JSON assets only. Preserve text and reject ambiguous inputs."""
import hashlib
import json
from pathlib import Path
from typing import Any

from .schemas import GoldRecord, Manifest, RunEnvelope


def content_hash(value: Any) -> str:
    """json-sorted-utf8-v1: no defaults, datetime conversion or text normalization."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def parse_json(text):
    def bad_constant(value):
        raise ValueError(f"non-finite JSON number: {value}")
    return json.loads(text, object_pairs_hook=_object, parse_constant=bad_constant)


def read_json(path):
    return parse_json(Path(path).read_text(encoding="utf-8-sig"))


def load_runs(paths):
    runs, assets, diagnostics, seen = [], [], [], {}
    for path in paths:
        path = Path(path)
        blob = path.read_bytes()
        data = parse_json(blob.decode("utf-8-sig"))
        kind = "run_array" if isinstance(data, list) else "single_run"
        if isinstance(data, dict) and "results" in data and "run_id" not in data:
            data, kind = data["results"], "benchmark_results"
        entries = data if isinstance(data, list) else [data]
        assets.append({"path": str(path.resolve()), "sha256": hashlib.sha256(blob).hexdigest(), "input_kind": kind})
        for entry in entries:
            RunEnvelope.model_validate(entry)
            digest = content_hash(entry)
            key = entry["run_id"]
            if key in seen:
                if seen[key] != digest:
                    raise ValueError(f"conflicting contents for run_id {key}")
                diagnostics.append({"code": "duplicate_identical_run", "run_id": key})
                continue
            seen[key] = digest
            runs.append(entry)
    if not runs:
        raise ValueError("no runs supplied")
    return runs, assets, diagnostics


def load_gold(paths, *, allow_synthetic=False):
    records, seen = [], set()
    for path in paths:
        path = Path(path)
        if path.suffix.lower() == ".jsonl":
            values = [parse_json(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
        else:
            data = read_json(path)
            values = data.get("records", [data]) if isinstance(data, dict) else data
        if not isinstance(values, list):
            raise ValueError("Gold must be a record, array, or records array")
        for value in values:
            record = GoldRecord.model_validate(value)
            if record.record_id in seen:
                raise ValueError(f"duplicate Gold record_id {record.record_id}")
            if record.synthetic_fixture and not allow_synthetic:
                raise ValueError("synthetic_fixture Gold requires --allow-synthetic-fixtures; never research Gold")
            seen.add(record.record_id)
            records.append(record)
    return records


def load_manifest(path):
    return Manifest.model_validate(read_json(path)) if path else None

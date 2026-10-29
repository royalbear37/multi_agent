"""python -m app.evaluation.cli --runs saved.json --out NEW_DIRECTORY"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from . import VERSION
from .evaluator import evaluate_run
from .export import export_report
from .io import content_hash, load_gold, load_manifest, load_runs
from .schemas import GoldRecord, Manifest, PAYLOAD_TYPES


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline Evaluator MVP: read saved JSON only; no API/database/model calls.")
    parser.add_argument("--runs", nargs="+", help="single Run, Run array, or Benchmark results JSON files")
    parser.add_argument("--gold", nargs="*", default=[], help="Gold JSON/JSONL files")
    parser.add_argument("--manifest", help="case identity / lineage / drug universe JSON")
    parser.add_argument("--out", help="new output directory; refuses overwrite")
    parser.add_argument("--allow-synthetic-fixtures", action="store_true")
    parser.add_argument("--print-schema", choices=["gold", "manifest"])
    args = parser.parse_args(argv)
    if args.print_schema:
        schema = (GoldRecord if args.print_schema == "gold" else Manifest).model_json_schema()
        if args.print_schema == "gold":
            # Conditional payload contracts are published alongside the envelope.
            schema["x-payload-schemas-by-record-type"] = {key: cls.model_json_schema() for key, cls in PAYLOAD_TYPES.items()}
        print(json.dumps(schema, ensure_ascii=False, indent=2))
        return 0
    if not args.runs or not args.out:
        parser.error("--runs and --out are required")
    try:
        runs, assets, diagnostics = load_runs(args.runs)
        gold = load_gold(args.gold, allow_synthetic=args.allow_synthetic_fixtures)
        manifest = load_manifest(args.manifest)
        run_keys = {(r["case_id"], r["case_revision"]) for r in runs}
        diagnostics.extend({"code": "gold_not_matched_to_any_run", "record_id": g.record_id}
                           for g in gold if (g.case_id, g.revision) not in run_keys)
        provenance = {"evaluator_version": VERSION, "canonicalization": "json-sorted-utf8-v1", "run_assets": assets,
                      "run_content_hashes": {r["run_id"]: content_hash(r) for r in runs},
                      "annotation_assets": [{"path": str(Path(p).resolve()), "sha256": hashlib.sha256(Path(p).read_bytes()).hexdigest()}
                                            for p in [*args.gold, *([args.manifest] if args.manifest else [])]],
                      "synthetic_fixture_mode": args.allow_synthetic_fixtures, "argv": argv if argv is not None else sys.argv[1:]}
        rows = [row for run in runs for row in evaluate_run(run, manifest=manifest, gold=gold)]
        report = export_report(args.out, rows, provenance, diagnostics)
    except (OSError, ValueError, ValidationError, TypeError) as exc:
        print(f"invalid_input: {exc}", file=sys.stderr)
        return 2
    invalid = any(x["status"] in {"alignment_error", "invalid_output"} for x in rows)
    print(json.dumps({"runs": len(runs), "observations": len(report["observations"]),
                      "output": str(Path(args.out).resolve()), "invalid_or_misaligned": invalid}, ensure_ascii=False))
    return 1 if invalid else 0


if __name__ == "__main__":
    raise SystemExit(main())

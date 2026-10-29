"""Write new report directories only; CSV values derive from the exact JSON rows."""
import csv
import json
from pathlib import Path

from . import VERSION
from .evaluator import aggregate
from .schemas import Metric


def export_report(destination, observations, provenance, diagnostics=()):
    target = Path(destination)
    # Validate and serialize before creating anything. Existing paths always fail.
    rows = [Metric.model_validate(x).model_dump() for x in observations]
    report = {"evaluator_version": VERSION, "provenance": provenance, "diagnostics": list(diagnostics),
              "summary": aggregate(rows), "observations": rows,
              "interpretation": "Engineering/source-fidelity observations; Mock is not clinical inference validation."}
    encoded = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
    target.mkdir(parents=True, exist_ok=False)
    (target / "report.json").write_text(encoded + "\n", encoding="utf-8")
    with (target / "observations.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        fields = list(Metric.model_fields)
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False, sort_keys=True) if isinstance(v, (dict, list))
                             else "true" if v is True else "false" if v is False else v for k, v in row.items()})
    return report

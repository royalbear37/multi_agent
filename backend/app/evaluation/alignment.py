"""Identity checks do not infer lineage from case names or AST similarity."""
from .io import content_hash


def align(run, manifest, gold):
    errors = []
    snapshot = run["case_snapshot"]
    if snapshot.get("case_id") != run["case_id"]:
        errors.append("snapshot_case_id_mismatch")
    if "revision" in snapshot and snapshot["revision"] != run["case_revision"]:
        errors.append("snapshot_revision_mismatch")
    identity = None
    if manifest:
        candidates = [x for x in manifest.cases if x.case_id == run["case_id"]]
        identity = next((x for x in candidates if x.revision == run["case_revision"]), None)
        if identity is None:
            errors.append("manifest_revision_mismatch" if candidates else "case_missing_from_manifest")
        elif identity.case_snapshot_sha256 != content_hash(snapshot):
            errors.append("case_snapshot_hash_mismatch")
    related = [g for g in gold if g.case_id == run["case_id"] and g.revision == run["case_revision"]]
    if not related and any(g.case_id == run["case_id"] for g in gold):
        errors.append("gold_revision_mismatch")
    for record in related:
        if record.case_snapshot_sha256 != content_hash(snapshot):
            errors.append("gold_snapshot_hash_mismatch")
        if identity and record.source_case_group != identity.source_case_group:
            errors.append("gold_source_case_group_mismatch")
    # Without independently declared lineage, Gold metrics remain ineligible.
    return identity, related, sorted(set(errors))

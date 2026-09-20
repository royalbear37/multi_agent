"""Research triage using source phenotypes, never invented MIC breakpoints."""
from collections import defaultdict

PHENOTYPES = {"susceptible": "S", "intermediate": "I", "resistant": "R",
              "s": "S", "i": "I", "r": "R", "non-susceptible": "NS",
              "susceptible dose dependent": "SDD", "susceptible dose-dependent": "SDD"}


def phenotype(value):
    return PHENOTYPES.get(str(value or "").strip().lower())


def evaluate_ast(engine, case):
    groups = defaultdict(list)
    for item in case.get("ast_results") or []:
        if isinstance(item, dict):
            groups[item.get("drug_code")].append(item)
    allergies = {str(x.get("drug_code", '')).casefold() for x in case.get("allergies", {}).get("items", [])}
    final = case.get("microbiology", {}).get("report_status") == "final"
    results = []
    for drug, rows in groups.items():
        reasons, labels = [], []
        for row in rows:
            basis = row.get("interpretation_basis")
            raw = row.get("clsi_2022_phenotype") if basis == "CLSI_2022_pheno" else row.get("source_phenotype")
            label = phenotype(raw)
            labels.append(label)
            if basis not in {"CLSI_2022_pheno", "source_report"} or label is None:
                source_name = "CLSI 2022 衍生判讀" if basis == "CLSI_2022_pheno" else "原始報告判讀"
                reasons.append(f"規則採用的{source_name}缺漏或無法識別；未自行推算，不等於抗藥")
            if basis == 'CLSI_2022_pheno' and (row.get('standard') != 'CLSI' or row.get('standard_version') != '2022'):
                reasons.append("所選 CLSI 2022 來源與標示的標準版本不一致")
            if label is not None and label != "S":
                reasons.append("來源結果不是 S，不自動列入敏感選項")
            if row.get("reported_sir") != (label if label in {"S", "I", "R"} else None):
                reasons.append("正規化判讀與指定來源不一致")
            original, revised = phenotype(row.get("source_phenotype")), phenotype(row.get("clsi_2022_phenotype"))
            if original and revised and original != revised:
                reasons.append("原始報告與 CLSI 2022 衍生結果不同，需人工確認")
        if len(set(labels)) > 1:
            reasons.append("同一藥品有不一致的重複結果")
        if drug not in engine.allowed_drugs() or not engine.supports(case.get("microbiology", {}).get("organism")):
            reasons.append("名稱尚未收錄於本機來源字典")
        if not final:
            reasons.append("尚非最終單一菌種報告")
        if str(drug).casefold() in allergies:
            reasons.append("命中病例記錄的同名藥品過敏")
        results.append({"drug_code": drug, "status": "evaluated", "eligible": not reasons,
                        "source_reported_sir": labels[0] if len(set(labels)) == 1 else None,
                        "interpretation_basis": rows[0].get("interpretation_basis"),
                        "reason": "；".join(dict.fromkeys(reasons)) or "指定來源為 S；僅作待審選項，仍需核對感染適用性",
                        "source": rows[0].get("source"), "recomputed_breakpoint": False})
    return results


def evaluate_rules(engine, case):
    def rule(rule_id, status, action, reason, drugs=None):
        return {"rule_id": rule_id, "version": engine.version, "status": status,
                "severity": "warning" if action == "avoid" else "info", "action": action,
                "reason": reason, "source_ref": "reported-ast-software-policy-1.0",
                "drug_codes": drugs or []}
    evaluations = [rule("SOURCE_AST_CANDIDATES", "matched" if engine.candidate_drugs(case) else "not_matched",
                        "allow_candidates", "來源 S、最終報告、判讀無衝突且未命中同名過敏才列為待審選項；非治療指引")]
    for row in engine.evaluate_ast(case):
        if not row["eligible"]:
            evaluations.append(rule("SOURCE_EXCLUSION:" + str(row["drug_code"]), "matched", "avoid", row["reason"], [row["drug_code"]]))
    for path, value in [("renal.egfr", case.get("renal", {}).get("egfr")), ("renal.unit", case.get("renal", {}).get("unit"))]:
        evaluations.append(rule("DATA:" + path, "matched" if value is not None else "unknown", "annotate", "檢查資料存在；未進行腎功能調整"))
    return evaluations

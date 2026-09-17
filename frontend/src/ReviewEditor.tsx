type Entry = {
  drug_code: string;
  reason: string;
  rule_refs: string[];
  evidence_refs: string[];
};
export type ReviewOutput = {
  candidates: Entry[];
  avoid: Entry[];
  limitations: string[];
};
export function reviewOutput(output: any): ReviewOutput {
  return {
    candidates: output?.candidates ?? [],
    avoid: output?.avoid ?? [],
    limitations: output?.limitations ?? [],
  };
}
export function ReviewEditor({
  run,
  value,
  onChange,
}: {
  run: any;
  value: ReviewOutput;
  onChange: (value: ReviewOutput) => void;
}) {
  const ast =
    run.nodes?.find((n: any) => n.node_id === "ast")?.output
      ?.system_evaluations ?? [];
  const options: string[] = [
    ...new Set<string>([
      ...ast
        .filter((x: any) => x.eligible === true)
        .map((x: any) => x.drug_code),
      ...(run.output?.candidates ?? []).map((x: any) => x.drug_code),
    ]),
  ];
  const update = (index: number, change: Partial<Entry>) =>
    onChange({
      ...value,
      candidates: value.candidates.map((item, i) =>
        i === index ? { ...item, ...change } : item,
      ),
    });
  return (
    <div className="review-editor">
      <p>
        修改待審藥物與理由，並勾選支持該理由的證據。來源排除條件由系統保留。
      </p>
      {value.candidates.map((item, index) => (
        <fieldset key={index}>
          <legend>待審藥物 {index + 1}</legend>
          <label>
            藥物
            <select
              aria-label={`藥物 ${index + 1}`}
              value={item.drug_code}
              onChange={(e) => update(index, { drug_code: e.target.value })}
            >
              {options.map((drug) => (
                <option
                  key={drug}
                  value={drug}
                  disabled={value.candidates.some(
                    (c, i) => i !== index && c.drug_code === drug,
                  )}
                >
                  {drug}
                </option>
              ))}
            </select>
          </label>
          <label>
            判斷理由
            <textarea
              aria-label={`藥物理由 ${index + 1}`}
              value={item.reason}
              onChange={(e) => update(index, { reason: e.target.value })}
            />
          </label>
          <h4>引用證據</h4>
          {(run.evidence_snapshots ?? []).map((e: any) => (
            <label className="check-label" key={e.chunk_id}>
              <input
                type="checkbox"
                checked={item.evidence_refs.includes(e.chunk_id)}
                onChange={(event) =>
                  update(index, {
                    evidence_refs: event.target.checked
                      ? [...item.evidence_refs, e.chunk_id]
                      : item.evidence_refs.filter((ref) => ref !== e.chunk_id),
                  })
                }
              />
              {e.document_title || e.title || e.doc_id} ·{" "}
              {e.location?.page ? `第 ${e.location.page} 頁` : "文件段落"}
              <small>{String(e.text ?? "").slice(0, 200)}</small>
            </label>
          ))}
          <button
            type="button"
            onClick={() =>
              onChange({
                ...value,
                candidates: value.candidates.filter((_, i) => i !== index),
              })
            }
          >
            移除這項候選
          </button>
        </fieldset>
      ))}
      <button
        type="button"
        disabled={
          run.gate_status !== "ready_for_review" ||
          !options.some(
            (drug) => !value.candidates.some((c) => c.drug_code === drug),
          )
        }
        onClick={() => {
          const drug = options.find(
            (drug) => !value.candidates.some((c) => c.drug_code === drug),
          );
          if (drug)
            onChange({
              ...value,
              candidates: [
                ...value.candidates,
                {
                  drug_code: drug,
                  reason: "",
                  evidence_refs: [],
                  rule_refs: (run.rule_evaluations ?? [])
                    .filter(
                      (r: any) =>
                        r.status === "matched" &&
                        r.action === "allow_candidates",
                    )
                    .map((r: any) => r.rule_id),
                },
              ],
            });
        }}
      >
        新增符合條件的候選
      </button>
      {!!value.avoid.length && (
        <div>
          <h4>來源排除／待確認項目（系統保留）</h4>
          <ul>
            {value.avoid.map((item, i) => (
              <li key={i}>
                {item.drug_code}：{item.reason}
              </li>
            ))}
          </ul>
        </div>
      )}
      <label>
        補充限制（每行一項）
        <textarea
          aria-label="補充限制"
          value={value.limitations.join("\n")}
          onChange={(e) =>
            onChange({ ...value, limitations: e.target.value.split("\n") })
          }
        />
      </label>
      <details>
        <summary>比較原始結果</summary>
        <ul>
          {(run.output?.candidates ?? []).map((item: Entry, i: number) => (
            <li key={i}>
              {item.drug_code}：{item.reason}
            </li>
          ))}
        </ul>
      </details>
    </div>
  );
}

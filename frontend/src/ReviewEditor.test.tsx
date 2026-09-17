import { useState } from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { expect, test } from "vitest";
import { ReviewEditor, reviewOutput } from "./ReviewEditor";

const run = {
  gate_status: "ready_for_review",
  output: {
    candidates: [
      {
        drug_code: "ceftriaxone",
        reason: "來源為 S",
        rule_refs: ["source"],
        evidence_refs: ["who-1"],
      },
    ],
    avoid: [],
    limitations: [],
  },
  evidence_snapshots: [
    {
      chunk_id: "who-1",
      document_title: "WHO",
      location: { page: 12 },
      text: "測試引用片段",
    },
  ],
  nodes: [
    {
      node_id: "ast",
      output: {
        system_evaluations: [
          { drug_code: "ceftriaxone", eligible: true },
          { drug_code: "ciprofloxacin", eligible: true },
          { drug_code: "ampicillin", eligible: false },
        ],
      },
    },
  ],
  rule_evaluations: [
    { rule_id: "source", status: "matched", action: "allow_candidates" },
  ],
};
function Editor() {
  const [value, setValue] = useState(reviewOutput(run.output));
  return (
    <>
      <ReviewEditor run={run} value={value} onChange={setValue} />
      <output data-testid="result">{JSON.stringify(value)}</output>
    </>
  );
}
test("physician edits using form fields and cannot select excluded drug", () => {
  render(<Editor />);
  expect(screen.queryByRole("option", { name: "ampicillin" })).toBeNull();
  fireEvent.change(screen.getByLabelText("藥物理由 1"), {
    target: { value: "已核對證據" },
  });
  expect(screen.getByTestId("result")).toHaveTextContent("已核對證據");
  fireEvent.click(screen.getByRole("button", { name: "新增符合條件的候選" }));
  expect(screen.getByLabelText("藥物 2")).toHaveValue("ciprofloxacin");
  fireEvent.click(screen.getAllByRole("checkbox")[1]);
  expect(
    JSON.parse(screen.getByTestId("result").textContent!).candidates[1]
      .evidence_refs,
  ).toEqual(["who-1"]);
});

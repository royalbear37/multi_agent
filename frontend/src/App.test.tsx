import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import App, { Status } from "./App";
afterEach(() => vi.unstubAllGlobals());
test("blocked state is visibly distinct", () => {
  render(<Status value="blocked" />);
  expect(screen.getByText("已阻擋")).toHaveClass("blocked");
});
test("backend failure is visible and retry is available", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue({
        ok: false,
        json: async () => ({ detail: "服務暫時無法使用" }),
      }),
  );
  render(<App />);
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "服務暫時無法使用",
  );
  expect(screen.getByText("重新連線")).toBeEnabled();
});
test("empty workspace can seed data and keeps model choice explicit", async () => {
  const calls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      calls.push(url);
      return {
        ok: true,
        json: async () =>
          url.endsWith("/config")
            ? { who_status: "尚未匯入", provider: { configured: false } }
            : url.endsWith("/seed")
              ? { imported: 14 }
              : [],
      };
    }),
  );
  render(<App />);
  await waitFor(() => expect(screen.getByText("載入展示資料")).toBeEnabled());
  expect(screen.getByText("選擇病例，或先載入展示資料。")).toBeVisible();
  fireEvent.click(screen.getByText("載入展示資料"));
  await screen.findByText("展示病例與文件已初始化；既有資料已保留。");
  expect(calls).toContain("/api/seed");
  expect(screen.getByDisplayValue("未設定模型")).toBeVisible();
});

test("embedding index failure remains visible to the user", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => ({
    ok: true,
    json: async () => url.endsWith("/config")
      ? { rag: { retrieval_method: "ollama_embeddings", model: "embeddinggemma" } }
      : url.endsWith("/documents/reindex")
        ? { status: "failed", warnings: ["embedding_unavailable"] }
        : [],
  })));
  render(<App />);
  await waitFor(() => expect(screen.getByText("載入展示資料")).toBeEnabled());
  fireEvent.click(screen.getByRole("button", { name: /05\s*文件資料庫/ }));
  expect(screen.getByText(/Embedding 模型：embeddinggemma/)).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "重建向量索引" }));
  expect(await screen.findByText("向量索引：failed · embedding_unavailable")).toBeVisible();
});

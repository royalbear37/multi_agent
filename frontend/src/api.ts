import type { components } from "./api.generated";
type RequestMap = {
  "/runs": components["schemas"]["RunBody"];
  "/reviews": components["schemas"]["ReviewBody"];
  "/cases/import": components["schemas"]["ImportBody"];
  "/benchmarks": components["schemas"]["BenchmarkBody"];
};
export function api<P extends keyof RequestMap>(
  path: P,
  body: RequestMap[P],
): Promise<any>;
export function api<T = any>(path: string, body?: unknown, method?: "POST" | "DELETE"): Promise<T>;
export async function api<T = any>(path: string, body?: unknown, method?: "POST" | "DELETE"): Promise<T> {
  const response = await fetch(
    "/api" + path,
    body === undefined && !method
      ? undefined
      : {
          method: method ?? "POST",
          headers:
            body instanceof FormData
              ? undefined
              : { "Content-Type": "application/json" },
          body: body instanceof FormData ? body : JSON.stringify(body),
        },
  );
  if (!response.ok) {
    const value = await response
      .json()
      .catch(() => ({ detail: response.statusText }));
    throw new Error(
      typeof value.detail === "string"
        ? value.detail
        : JSON.stringify(value.detail ?? value),
    );
  }
  return response.json();
}
export const pretty = (value: unknown) => JSON.stringify(value, null, 2);

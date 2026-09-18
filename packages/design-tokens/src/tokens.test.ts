import { describe, expect, it } from "vitest";
import { cssVar, palette, space, toCssVariables } from "./index";

describe("tokens", () => {
  it("has one accent per theme and emits css vars", () => {
    expect(palette.light.accent).toBe("#B4532A");
    expect(palette.dark.accent).toBe("#E07A4B");
    expect(toCssVariables("dark")).toContain("--accent:#E07A4B");
    expect(toCssVariables("light")).toMatch(/^:root\{/);
    expect(toCssVariables("dark", '[data-theme="dark"]')).toMatch(/^\[data-theme="dark"\]\{/);
    expect(cssVar("inkMuted")).toBe("var(--ink-muted)");
  });

  it("light and dark expose the same token names", () => {
    expect(Object.keys(palette.light)).toEqual(Object.keys(palette.dark));
    expect(space[3]).toBe(12);
  });
});

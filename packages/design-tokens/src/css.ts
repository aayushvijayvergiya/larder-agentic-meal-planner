import { palette, type Theme } from "./tokens";

const kebab = (s: string) => s.replace(/[A-Z]/g, (m) => "-" + m.toLowerCase());

/** ":root{--bg:#F7F4EE;--surface:#FFFFFF;…}" for the given theme. */
export function toCssVariables(theme: Theme, selector = ":root"): string {
  const body = Object.entries(palette[theme])
    .map(([k, v]) => `--${kebab(k)}:${v}`)
    .join(";");
  return `${selector}{${body}}`;
}

/** CSS variable name for a token, e.g. cssVar("inkMuted") === "var(--ink-muted)". */
export function cssVar(token: keyof (typeof palette)["light"]): string {
  return `var(--${kebab(token)})`;
}

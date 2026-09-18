/** Larder design tokens (LLD §9.1). One accent, paper and ink; everything else is a line. */

export const palette = {
  light: {
    bg: "#F7F4EE",
    surface: "#FFFFFF",
    surfaceAlt: "#F1ECE3",
    ink: "#1F1D1A",
    inkMuted: "#6B655C",
    line: "#E6E0D6",
    accent: "#B4532A",
    accentInk: "#FFFFFF",
    accentSoft: "#F4E3DA",
    success: "#3E7C4A",
    warning: "#B7791F",
    danger: "#B42318",
    focus: "#2F5D9F",
  },
  dark: {
    bg: "#16140F",
    surface: "#1F1C16",
    surfaceAlt: "#26221B",
    ink: "#EFE9DF",
    inkMuted: "#A39B8E",
    line: "#2E2A22",
    accent: "#E07A4B",
    accentInk: "#16140F",
    accentSoft: "#3A251B",
    success: "#7FB98A",
    warning: "#D9A441",
    danger: "#E5735F",
    focus: "#8AB4F8",
  },
} as const;

export type Theme = keyof typeof palette;
export type ColorToken = keyof (typeof palette)["light"];
export type Colors = { [K in ColorToken]: string };

export const type = {
  display: "Fraunces",
  body: "Instrument Sans",
  mono: "JetBrains Mono",
  scale: { xs: 12, sm: 14, md: 16, lg: 18, xl: 22, "2xl": 28, "3xl": 36 },
  lineHeight: { tight: 1.15, normal: 1.5 },
} as const;

/** index = step: space[3] === 12 */
export const space = [0, 4, 8, 12, 16, 24, 32, 48, 64] as const;

export const radius = { sm: 4, md: 6, lg: 10 } as const;

/** Layout constants shared by web and mobile (LLD §9.2 rule 10). */
export const layout = { gutterPhone: 16, gutterWide: 24, maxContentWidth: 880, touchTarget: 44 } as const;

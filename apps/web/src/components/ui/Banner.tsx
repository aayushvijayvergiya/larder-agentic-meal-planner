"use client";

import type { ReactNode } from "react";

export interface BannerProps {
  tone?: "info" | "warning" | "danger" | "success";
  children: ReactNode;
  action?: ReactNode;
}

const tones = {
  info: "border-line bg-surface-alt text-ink",
  warning: "border-warning/40 bg-surface-alt text-ink",
  danger: "border-danger/40 bg-surface-alt text-ink",
  success: "border-success/40 bg-surface-alt text-ink",
};

export function Banner({ tone = "info", children, action }: BannerProps) {
  return (
    <div role="status" className={`flex flex-wrap items-center justify-between gap-3 rounded-md border px-4 py-3 text-sm ${tones[tone]}`}>
      <span>{children}</span>
      {action}
    </div>
  );
}

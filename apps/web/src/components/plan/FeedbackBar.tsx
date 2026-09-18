"use client";

import { ChefHat, ThumbsDown, ThumbsUp } from "lucide-react";

export function FeedbackBar({
  value,
  cookedCount,
  onFeedback,
}: {
  value: "up" | "down" | null;
  cookedCount: number;
  onFeedback: (kind: "up" | "down" | "cooked") => void;
}) {
  const btn = (active: boolean) =>
    `inline-flex h-9 items-center gap-1 rounded-md border px-2.5 text-sm ${active ? "border-accent bg-accent-soft text-ink" : "border-line text-ink-muted hover:text-ink"}`;
  return (
    <div className="flex items-center gap-2" role="group" aria-label="Feedback">
      <button type="button" aria-label="Thumbs up" aria-pressed={value === "up"} className={btn(value === "up")} onClick={() => onFeedback("up")}>
        <ThumbsUp size={16} strokeWidth={1.75} />
      </button>
      <button type="button" aria-label="Thumbs down" aria-pressed={value === "down"} className={btn(value === "down")} onClick={() => onFeedback("down")}>
        <ThumbsDown size={16} strokeWidth={1.75} />
      </button>
      <button type="button" className={btn(false)} onClick={() => onFeedback("cooked")} data-testid="cooked">
        <ChefHat size={16} strokeWidth={1.75} />
        Cooked it{cookedCount > 0 ? ` · ${cookedCount}` : ""}
      </button>
    </div>
  );
}

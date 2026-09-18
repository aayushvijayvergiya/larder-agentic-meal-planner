"use client";

import type { PlanEntryOut } from "@larder/api-client";
import { FeedbackBar } from "@/components/plan/FeedbackBar";

export interface PlanEntryCardProps {
  entry: PlanEntryOut;
  onSwap: () => void;
  onFeedback: (kind: "up" | "down" | "cooked") => void;
  compact?: boolean;
}

/** Anatomy per LLD §9.4: slot label · meal name · reason · coverage row · variations · actions. */
export function PlanEntryCard({ entry, onSwap, onFeedback, compact }: PlanEntryCardProps) {
  const missing = entry.missing_ingredients;
  return (
    <article className="rounded-md border border-line bg-surface p-4" data-testid="plan-entry" aria-label={`${entry.slot_label}: ${entry.meal.name}`}>
      <p className="text-xs font-medium uppercase tracking-wide text-ink-muted">{entry.slot_label}</p>
      <h3 className={`mt-1 font-display ${compact ? "text-lg" : "text-xl"}`}>{entry.meal.name}</h3>
      {!compact && <p className="mt-1 text-ink-muted">{entry.reason}</p>}
      <p className="mt-2 text-sm">
        {entry.covered_ingredients.length > 0 && (
          <span>
            <span className="text-ink-muted">On hand:</span> {entry.covered_ingredients.join(", ")}
          </span>
        )}
        {missing.length > 0 && (
          <span className={entry.covered_ingredients.length ? " ml-2" : ""}>
            <span className="text-ink-muted">Missing:</span>{" "}
            <span className="text-warning">{missing.map((m) => (m.is_optional ? `${m.name} (optional)` : m.name)).join(", ")}</span>
          </span>
        )}
        {!entry.covered_ingredients.length && !missing.length && <span className="text-ink-muted">Pantry basics only.</span>}
      </p>
      {entry.variations.length > 0 && (
        <ul className="mt-2 space-y-0.5 text-sm">
          {entry.variations.map((v) => (
            <li key={v.member_id}>
              <span className="text-ink-muted">{v.display_name ?? "Member"}:</span> {v.note}
            </li>
          ))}
        </ul>
      )}
      {!compact && (
        <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
          <FeedbackBar value={entry.my_feedback ?? null} cookedCount={entry.cooked_count} onFeedback={onFeedback} />
          <button type="button" className="text-sm text-ink underline" onClick={onSwap} data-testid="swap">
            Swap
          </button>
        </div>
      )}
    </article>
  );
}

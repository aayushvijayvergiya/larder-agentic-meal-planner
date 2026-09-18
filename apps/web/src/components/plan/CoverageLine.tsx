import type { PlanOut } from "@larder/api-client";

export function CoverageLine({ plan, dayEntries }: { plan: PlanOut; dayEntries?: PlanOut["days"][number]["entries"] }) {
  const onHand = dayEntries ? dayEntries.reduce((n, e) => n + e.covered_ingredients.length, 0) : plan.coverage.on_hand;
  const needed = dayEntries
    ? dayEntries.reduce((n, e) => n + e.covered_ingredients.length + e.missing_ingredients.filter((m) => !m.is_optional).length, 0)
    : plan.coverage.needed;
  return (
    <div className="text-sm text-ink-muted">
      <p>
        {dayEntries ? "On hand for today" : "On hand this week"}: {onHand} of {needed} ingredients
        {needed > 0 && onHand === needed ? ". Nothing to buy." : ""}
      </p>
      {plan.unused_pantry.length > 0 && <p className="mt-0.5">Unused this week: {plan.unused_pantry.map((u) => u.name).join(", ")}</p>}
    </div>
  );
}

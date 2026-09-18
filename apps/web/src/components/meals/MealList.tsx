"use client";

import type { MealOut } from "@larder/api-client";
import Link from "next/link";
import { titleCase } from "@/lib/format";

export function MealList({ meals }: { meals: MealOut[] }) {
  return (
    <ul className="divide-y divide-line">
      {meals.map((m) => (
        <li key={m.id}>
          <Link href={`/meals/${m.id}`} className="flex items-center justify-between gap-4 py-3 hover:bg-surface-alt">
            <span>
              <span className="block text-ink">{m.name}</span>
              <span className="block text-sm text-ink-muted">
                {[m.cuisine ? titleCase(m.cuisine) : null, m.prep_minutes ? `${m.prep_minutes} min` : null, m.meal_types.map(titleCase).join(", ") || null]
                  .filter(Boolean)
                  .join(" · ")}
              </span>
            </span>
            <span className="shrink-0 text-xs text-ink-muted">
              {m.enrichment_status === "failed" ? "needs details" : m.feedback.up > 0 ? `${m.feedback.up} likes` : ""}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

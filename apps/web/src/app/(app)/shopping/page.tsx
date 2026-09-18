"use client";

import { useAddPantryItems, useCurrentPlan, useShoppingList } from "@larder/api-client";
import { useState } from "react";
import { Button, EmptyState, SkeletonList } from "@/components/ui";
import { shortDay } from "@/lib/format";
import { usePlanScope } from "@/lib/scope";

export default function ShoppingPage() {
  const { scope } = usePlanScope();
  const plan = useCurrentPlan({ scope });
  const planId = plan.data?.plan?.id;
  const list = useShoppingList(planId);
  const add = useAddPantryItems();
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const toggle = (k: string) => setChecked((s) => {
    const n = new Set(s);
    if (n.has(k)) n.delete(k);
    else n.add(k);
    return n;
  });

  return (
    <div>
      <h1 className="text-2xl">Shopping</h1>
      {list.data && (
        <p className="mt-1 text-sm text-ink-muted">
          What the rest of the plan needs and you don&apos;t have, {shortDay(list.data.from_date)} to {shortDay(list.data.to_date)}.
        </p>
      )}
      <div className="mt-6">
        {plan.isLoading || list.isLoading ? (
          <SkeletonList rows={3} />
        ) : !planId ? (
          <EmptyState>No plan yet, so nothing to buy. Plan your week first.</EmptyState>
        ) : !list.data?.total ? (
          <EmptyState>Nothing to buy. Everything the plan needs is already in your larder.</EmptyState>
        ) : (
          list.data.groups.map((g) => (
            <section key={g.category} className="border-t border-line py-4" aria-label={g.label}>
              <h2 className="mb-2 text-lg">{g.label}</h2>
              <ul className="divide-y divide-line">
                {g.items.map((item) => {
                  const key = `${g.category}:${item.name}`;
                  return (
                    <li key={key} className="flex items-center gap-3 py-2">
                      <input type="checkbox" aria-label={`Bought ${item.name}`} checked={checked.has(key)} onChange={() => toggle(key)} className="h-4 w-4 accent-[var(--accent)]" />
                      <span className={`flex-1 ${checked.has(key) ? "text-ink-muted line-through" : ""}`}>
                        {item.name}
                        <span className="ml-2 text-sm text-ink-muted">for {item.meals.join(", ")}</span>
                      </span>
                      <Button size="sm" variant="ghost" onClick={() => add.mutate([{ name: item.name, category: g.category }])}>
                        Add to pantry
                      </Button>
                    </li>
                  );
                })}
              </ul>
            </section>
          ))
        )}
      </div>
    </div>
  );
}

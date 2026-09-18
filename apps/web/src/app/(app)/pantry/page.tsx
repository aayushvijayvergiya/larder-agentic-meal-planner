"use client";

import { useAddPantryItems, useDeletePantryItem, usePantry, useUpdatePantryItem, type PantryCategory, type PantryItemOut } from "@larder/api-client";
import { useState } from "react";
import { BulkAdd } from "@/components/pantry/BulkAdd";
import { CategorySection } from "@/components/pantry/CategorySection";
import { Banner, Button, EmptyState, SkeletonList } from "@/components/ui";

export default function PantryPage() {
  const pantry = usePantry();
  const add = useAddPantryItems();
  const update = useUpdatePantryItem();
  const remove = useDeletePantryItem();
  const [showBulk, setShowBulk] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const guard = <T,>(p: Promise<T>) => p.catch((e: Error) => setError(e.message));

  const onAdd = (name: string, category: PantryCategory) => guard(add.mutateAsync([{ name, category }]));
  const onToggle = (item: PantryItemOut) => guard(update.mutateAsync({ id: item.id, patch: { is_available: !item.is_available } }));
  const onRename = (item: PantryItemOut, name: string) => guard(update.mutateAsync({ id: item.id, patch: { name } }));
  const onDelete = (item: PantryItemOut) => guard(remove.mutateAsync(item.id));

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl">Pantry</h1>
          <p className="mt-1 text-sm text-ink-muted">{pantry.data ? `${pantry.data.total} items. Untick what you've run out of.` : "What you have at home."}</p>
        </div>
        <Button variant="secondary" onClick={() => setShowBulk((s) => !s)}>
          {showBulk ? "Close" : "Add many"}
        </Button>
      </div>
      {showBulk && (
        <div className="mt-4 rounded-md border border-line bg-surface p-4">
          <BulkAdd onAdd={(names) => guard(add.mutateAsync(names.map((name) => ({ name })))).then(() => setShowBulk(false))} busy={add.isPending} />
        </div>
      )}
      {error && (
        <div className="mt-4">
          <Banner tone="danger" action={<button className="underline" onClick={() => setError(null)}>Dismiss</button>}>
            {error}
          </Banner>
        </div>
      )}
      <div className="mt-6">
        {pantry.isLoading ? (
          <SkeletonList rows={4} />
        ) : !pantry.data?.categories.length ? (
          <EmptyState action={<Button onClick={() => setShowBulk(true)}>Add what you have</Button>}>Your pantry is empty.</EmptyState>
        ) : (
          pantry.data.categories.map((c) => (
            <CategorySection key={c.category} category={c.category} label={c.label} items={c.items} onAdd={onAdd} onToggle={onToggle} onRename={onRename} onDelete={onDelete} />
          ))
        )}
      </div>
    </div>
  );
}

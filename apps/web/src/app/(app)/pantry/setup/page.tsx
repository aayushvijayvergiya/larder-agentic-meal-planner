"use client";

import { useAddPantryItems } from "@larder/api-client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { BulkAdd } from "@/components/pantry/BulkAdd";
import { SuggestionChips } from "@/components/pantry/SuggestionChips";
import { Banner, Button } from "@/components/ui";

export default function PantrySetupPage() {
  const router = useRouter();
  const add = useAddPantryItems();
  const [selected, setSelected] = useState<string[]>([]);
  const [added, setAdded] = useState(0);

  const submit = async (names: string[]) => {
    const all = Array.from(new Set([...names, ...selected]));
    if (!all.length) return;
    const res = await add.mutateAsync(all.map((name) => ({ name })));
    setAdded((n) => n + res.created.length + res.existing.length);
    setSelected([]);
  };

  return (
    <div className="mx-auto max-w-xl">
      <p className="text-sm font-medium text-accent">Step 2 of 2</p>
      <h1 className="mt-1 text-2xl">What&apos;s in your larder?</h1>
      <p className="mt-2 text-ink-muted">Larder plans from what you already have. Add the basics now; you can refine the list any time.</p>
      <div className="mt-6 space-y-6">
        <SuggestionChips selected={selected} onToggle={(n) => setSelected((s) => (s.includes(n) ? s.filter((x) => x !== n) : [...s, n]))} />
        <BulkAdd onAdd={submit} busy={add.isPending} label={selected.length ? `Add${selected.length ? ` (+${selected.length} selected)` : ""}` : "Add"} />
        {selected.length > 0 && (
          <Button variant="secondary" onClick={() => submit([])} loading={add.isPending} data-testid="add-selected">
            Add {selected.length} selected
          </Button>
        )}
        {added > 0 && <Banner tone="success">{added} item{added === 1 ? "" : "s"} in your pantry.</Banner>}
        {add.error && <Banner tone="danger">Couldn&apos;t save those items. Try again.</Banner>}
        <div className="flex items-center gap-4 border-t border-line pt-6">
          <Button onClick={() => router.replace("/today")} data-testid="pantry-continue" variant={added > 0 ? "primary" : "secondary"}>
            {added > 0 ? "Plan my week" : "Skip for now"}
          </Button>
        </div>
      </div>
    </div>
  );
}

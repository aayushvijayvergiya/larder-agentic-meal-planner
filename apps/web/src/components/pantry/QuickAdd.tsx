"use client";

import type { PantryCategory } from "@larder/api-client";
import { Plus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Button, Input } from "@/components/ui";

export function QuickAdd({ category, onAdd, busy }: { category: PantryCategory; onAdd: (name: string, category: PantryCategory) => void; busy?: boolean }) {
  const [name, setName] = useState("");
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    onAdd(name.trim(), category);
    setName("");
  };
  return (
    <form onSubmit={submit} className="flex items-end gap-2">
      <Input name={`add-${category}`} placeholder={`Add to ${category}`} aria-label={`Add to ${category}`} value={name} onChange={(e) => setName(e.target.value)} className="h-9" />
      <Button type="submit" size="sm" variant="secondary" disabled={!name.trim()} loading={busy} icon={<Plus size={16} strokeWidth={1.75} />}>
        Add
      </Button>
    </form>
  );
}

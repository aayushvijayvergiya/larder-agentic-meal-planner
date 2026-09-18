"use client";

import type { PantryCategory, PantryItemOut } from "@larder/api-client";
import { Trash2 } from "lucide-react";
import { useState } from "react";
import { QuickAdd } from "@/components/pantry/QuickAdd";

export interface CategorySectionProps {
  category: PantryCategory;
  label: string;
  items: PantryItemOut[];
  onAdd: (name: string, category: PantryCategory) => void;
  onToggle: (item: PantryItemOut) => void;
  onRename: (item: PantryItemOut, name: string) => void;
  onDelete: (item: PantryItemOut) => void;
}

export function CategorySection({ category, label, items, onAdd, onToggle, onRename, onDelete }: CategorySectionProps) {
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  return (
    <section aria-label={label} className="border-t border-line py-4">
      <h2 className="mb-2 text-lg">{label}</h2>
      <ul className="divide-y divide-line">
        {items.map((item) => (
          <li key={item.id} className="flex items-center gap-3 py-2">
            <input
              type="checkbox"
              aria-label={`${item.name} available`}
              checked={item.is_available}
              onChange={() => onToggle(item)}
              className="h-4 w-4 accent-[var(--accent)]"
            />
            {editing === item.id ? (
              <form
                className="flex-1"
                onSubmit={(e) => {
                  e.preventDefault();
                  if (draft.trim() && draft.trim() !== item.name) onRename(item, draft.trim());
                  setEditing(null);
                }}
              >
                <input
                  autoFocus
                  aria-label={`Rename ${item.name}`}
                  className="h-8 w-full rounded-sm border border-line bg-surface px-2"
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onBlur={() => setEditing(null)}
                />
              </form>
            ) : (
              <button
                type="button"
                className={`flex-1 text-left ${item.is_available ? "text-ink" : "text-ink-muted line-through"}`}
                onClick={() => {
                  setEditing(item.id);
                  setDraft(item.name);
                }}
                title="Rename"
              >
                {item.name}
              </button>
            )}
            <button type="button" aria-label={`Remove ${item.name}`} onClick={() => onDelete(item)} className="rounded-sm p-1 text-ink-muted hover:text-danger">
              <Trash2 size={18} strokeWidth={1.75} />
            </button>
          </li>
        ))}
      </ul>
      <div className="mt-2">
        <QuickAdd category={category} onAdd={onAdd} />
      </div>
    </section>
  );
}

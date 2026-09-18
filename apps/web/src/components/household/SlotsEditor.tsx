"use client";

import type { SlotDef } from "@larder/api-client";
import { ArrowDown, ArrowUp, Trash2 } from "lucide-react";
import { useState } from "react";
import { Button, Input } from "@/components/ui";

const slugify = (s: string) =>
  s
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .replace(/^[^a-z]/, "s$&")
    .slice(0, 31);

/** Edit household meal slots; emits slots renumbered by order and refuses duplicate keys. */
export function SlotsEditor({ slots, onSave, busy }: { slots: SlotDef[]; onSave: (slots: SlotDef[]) => void; busy?: boolean }) {
  const [rows, setRows] = useState<SlotDef[]>(() => [...slots].sort((a, b) => a.order - b.order));
  const [label, setLabel] = useState("");
  const keys = rows.map((r) => r.key);
  const newKey = slugify(label);
  const duplicate = !!newKey && keys.includes(newKey);

  const move = (i: number, dir: -1 | 1) =>
    setRows((r) => {
      const n = [...r];
      const j = i + dir;
      if (j < 0 || j >= n.length) return r;
      [n[i], n[j]] = [n[j], n[i]];
      return n;
    });

  return (
    <div className="space-y-3" data-testid="slots-editor">
      <ul className="divide-y divide-line">
        {rows.map((r, i) => (
          <li key={r.key} className="flex items-center gap-2 py-2">
            <span className="flex-1">{r.label}</span>
            <button type="button" aria-label={`Move ${r.label} up`} onClick={() => move(i, -1)} className="p-1 text-ink-muted hover:text-ink" disabled={i === 0}>
              <ArrowUp size={16} strokeWidth={1.75} />
            </button>
            <button type="button" aria-label={`Move ${r.label} down`} onClick={() => move(i, 1)} className="p-1 text-ink-muted hover:text-ink" disabled={i === rows.length - 1}>
              <ArrowDown size={16} strokeWidth={1.75} />
            </button>
            <button type="button" aria-label={`Remove ${r.label}`} onClick={() => setRows((x) => x.filter((_, k) => k !== i))} className="p-1 text-ink-muted hover:text-danger" disabled={rows.length <= 1}>
              <Trash2 size={16} strokeWidth={1.75} />
            </button>
          </li>
        ))}
      </ul>
      <div className="flex items-end gap-2">
        <Input name="new-slot" label="Add a slot" placeholder="e.g. Evening tea" value={label} onChange={(e) => setLabel(e.target.value)} error={duplicate ? "That slot already exists" : undefined} maxLength={40} />
        <Button
          type="button"
          variant="secondary"
          disabled={!newKey || duplicate || rows.length >= 6}
          onClick={() => {
            setRows((r) => [...r, { key: newKey, label: label.trim(), order: r.length + 1 }]);
            setLabel("");
          }}
        >
          Add
        </Button>
      </div>
      <Button type="button" onClick={() => onSave(rows.map((r, i) => ({ ...r, order: i + 1 })))} loading={busy} data-testid="save-slots">
        Save slots
      </Button>
    </div>
  );
}

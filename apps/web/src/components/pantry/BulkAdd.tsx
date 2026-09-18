"use client";

import { useState } from "react";
import { Button, Textarea } from "@/components/ui";

/** Splits "a, b\n c" into unique trimmed names (case-insensitive dedupe, first spelling wins). */
export function parseBulk(text: string): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const raw of text.split(/[,\n]/)) {
    const name = raw.trim().replace(/\s+/g, " ");
    const key = name.toLowerCase();
    if (name && !seen.has(key)) {
      seen.add(key);
      out.push(name);
    }
  }
  return out;
}

export function BulkAdd({ onAdd, busy, label = "Add" }: { onAdd: (names: string[]) => void; busy?: boolean; label?: string }) {
  const [text, setText] = useState("");
  const names = parseBulk(text);
  return (
    <div className="space-y-3">
      <Textarea
        name="bulk"
        label="What's in your kitchen?"
        hint="Separate items with commas or new lines. Categories are filled in for you."
        placeholder="paneer, spinach, basmati rice, toor dal, onions, tomatoes"
        value={text}
        onChange={(e) => setText(e.target.value)}
        data-testid="bulk-add"
      />
      <div className="flex items-center gap-3">
        <Button
          onClick={() => {
            onAdd(names);
            setText("");
          }}
          disabled={!names.length}
          loading={busy}
          data-testid="bulk-add-submit"
        >
          {label} {names.length ? `${names.length} item${names.length === 1 ? "" : "s"}` : ""}
        </Button>
      </div>
    </div>
  );
}

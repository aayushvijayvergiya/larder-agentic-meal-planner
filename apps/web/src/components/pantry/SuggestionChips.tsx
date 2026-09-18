"use client";

import { usePantrySuggestions } from "@larder/api-client";
import { Chip } from "@/components/ui";

export function SuggestionChips({ selected, onToggle }: { selected: string[]; onToggle: (name: string) => void }) {
  const suggestions = usePantrySuggestions();
  const items = suggestions.data?.items ?? [];
  if (!items.length) return null;
  return (
    <div>
      <p className="mb-2 text-sm text-ink-muted">Common staples. Tap what you have.</p>
      <div className="flex flex-wrap gap-2" data-testid="suggestion-chips">
        {items.map((s) => (
          <Chip key={s.name} selected={selected.includes(s.name)} onClick={() => onToggle(s.name)}>
            {s.name}
          </Chip>
        ))}
      </div>
    </div>
  );
}

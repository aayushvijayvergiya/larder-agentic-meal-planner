"use client";

import { X } from "lucide-react";
import type { ButtonHTMLAttributes } from "react";

export interface ChipProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  selected?: boolean;
  onRemove?: () => void;
}

/** A selectable pill. With onRemove it renders as a removable tag. */
export function Chip({ selected, onRemove, className = "", children, ...rest }: ChipProps) {
  const tone = selected ? "bg-accent-soft border-accent text-ink" : "bg-surface border-line text-ink hover:bg-surface-alt";
  return (
    <button
      type="button"
      aria-pressed={onRemove ? undefined : selected}
      className={`inline-flex h-9 items-center gap-1.5 rounded-md border px-3 text-sm transition-colors duration-150 ${tone} ${className}`}
      {...rest}
    >
      {children}
      {onRemove && (
        <span
          role="button"
          aria-label={`Remove ${typeof children === "string" ? children : ""}`.trim()}
          onClick={(e) => {
            e.stopPropagation();
            onRemove();
          }}
          className="-mr-1 rounded-sm p-0.5 text-ink-muted hover:text-ink"
        >
          <X size={14} strokeWidth={1.75} />
        </span>
      )}
    </button>
  );
}

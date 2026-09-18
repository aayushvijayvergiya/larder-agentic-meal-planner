"use client";

import { useId, type SelectHTMLAttributes } from "react";

export interface SelectOption {
  value: string;
  label: string;
}

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  options: SelectOption[];
  placeholder?: string;
}

export function Select({ label, options, placeholder, id, className = "", ...rest }: SelectProps) {
  const auto = useId();
  const selectId = id ?? (rest.name ? `f-${rest.name}` : auto);
  return (
    <div className="block w-full text-sm">
      {label && (
        <label htmlFor={selectId} className="mb-1 block font-medium text-ink">
          {label}
        </label>
      )}
      <select id={selectId} className={`h-11 w-full rounded-md border border-line bg-surface px-3 text-ink ${className}`} {...rest}>
        {placeholder && (
          <option value="" disabled>
            {placeholder}
          </option>
        )}
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );
}

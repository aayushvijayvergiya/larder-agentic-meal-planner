"use client";

import { forwardRef, useId, type InputHTMLAttributes, type TextareaHTMLAttributes } from "react";

const field =
  "w-full rounded-md border border-line bg-surface px-3 text-ink placeholder:text-ink-muted/70 focus-visible:border-focus";

function Help({ error, hint }: { error?: string; hint?: string }) {
  if (error) return <span className="mt-1 block text-danger">{error}</span>;
  if (hint) return <span className="mt-1 block text-ink-muted">{hint}</span>;
  return null;
}

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  hint?: string;
  error?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input({ label, hint, error, id, className = "", ...rest }, ref) {
  const auto = useId();
  const inputId = id ?? (rest.name ? `f-${rest.name}` : auto);
  return (
    <div className="block w-full text-sm">
      {label && (
        <label htmlFor={inputId} className="mb-1 block font-medium text-ink">
          {label}
        </label>
      )}
      <input ref={ref} id={inputId} className={`${field} h-11 ${className}`} aria-invalid={!!error} {...rest} />
      <Help error={error} hint={hint} />
    </div>
  );
});

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  hint?: string;
  error?: string;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { label, hint, error, id, className = "", ...rest },
  ref,
) {
  const auto = useId();
  const inputId = id ?? (rest.name ? `f-${rest.name}` : auto);
  return (
    <div className="block w-full text-sm">
      {label && (
        <label htmlFor={inputId} className="mb-1 block font-medium text-ink">
          {label}
        </label>
      )}
      <textarea ref={ref} id={inputId} className={`${field} min-h-24 py-2 ${className}`} aria-invalid={!!error} {...rest} />
      <Help error={error} hint={hint} />
    </div>
  );
});

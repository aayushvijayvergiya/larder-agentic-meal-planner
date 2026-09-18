"use client";

import type { Answer, Widget } from "@larder/api-client";
import { useState, type FormEvent } from "react";
import { Button, Chip, Input, Textarea } from "@/components/ui";

export interface WidgetRendererProps {
  widget: Widget;
  onSubmit: (answer: Answer) => void;
  disabled?: boolean;
}

function splitChips(text: string): string[] {
  return text
    .split(/[,\n]/)
    .map((s) => s.trim())
    .filter(Boolean);
}

/** Renders the widget the onboarding agent asked for and submits a typed answer (LLD §8.1, §9.6).
 *  Parents must pass a fresh `key` per turn so the local state resets. */
export function WidgetRenderer({ widget, onSubmit, disabled }: WidgetRendererProps) {
  const [freeText, setFreeText] = useState(false);
  const [text, setText] = useState("");
  const [value, setValue] = useState<string>("");
  const [multi, setMulti] = useState<string[]>([]);
  const [custom, setCustom] = useState("");

  if (widget.type === "review") return null;

  const typeInstead = (
    <button type="button" className="text-sm text-ink-muted underline" onClick={() => setFreeText(true)}>
      Type instead
    </button>
  );

  if (freeText) {
    const send = (e: FormEvent) => {
      e.preventDefault();
      if (text.trim()) onSubmit({ kind: "text", text: text.trim() });
    };
    return (
      <form onSubmit={send} className="space-y-3" data-testid="widget-free-text">
        <Input name="free-text" placeholder="Type your answer" value={text} onChange={(e) => setText(e.target.value)} autoFocus />
        <div className="flex items-center gap-3">
          <Button type="submit" disabled={disabled || !text.trim()}>
            Send
          </Button>
          <button type="button" className="text-sm text-ink-muted underline" onClick={() => setFreeText(false)}>
            Use the picker
          </button>
        </div>
      </form>
    );
  }

  const submitValue = (v: unknown) => onSubmit({ kind: "widget", value: v });

  switch (widget.type) {
    case "text": {
      const send = (e: FormEvent) => {
        e.preventDefault();
        if (value.trim()) submitValue(value.trim());
      };
      return (
        <form onSubmit={send} className="space-y-3" data-testid="widget-text">
          {widget.multiline ? (
            <Textarea name="answer" placeholder={widget.placeholder} maxLength={widget.max_length} value={value} onChange={(e) => setValue(e.target.value)} />
          ) : (
            <Input name="answer" placeholder={widget.placeholder} maxLength={widget.max_length} value={value} onChange={(e) => setValue(e.target.value)} autoFocus />
          )}
          <div className="flex items-center gap-3">
            <Button type="submit" disabled={disabled || !value.trim()}>
              Continue
            </Button>
            {typeInstead}
          </div>
        </form>
      );
    }
    case "number": {
      const send = (e: FormEvent) => {
        e.preventDefault();
        if (value !== "") submitValue(Number(value));
      };
      return (
        <form onSubmit={send} className="space-y-3" data-testid="widget-number">
          <div className="flex items-end gap-2">
            <Input name="answer" type="number" min={widget.min} max={widget.max} step={widget.step} value={value} onChange={(e) => setValue(e.target.value)} autoFocus className="max-w-40" />
            <span className="pb-3 text-sm text-ink-muted">{widget.unit}</span>
          </div>
          <div className="flex items-center gap-3">
            <Button type="submit" disabled={disabled || value === ""}>
              Continue
            </Button>
            {typeInstead}
          </div>
        </form>
      );
    }
    case "date": {
      const send = (e: FormEvent) => {
        e.preventDefault();
        if (value) submitValue(value);
      };
      return (
        <form onSubmit={send} className="space-y-3" data-testid="widget-date">
          <Input name="answer" type="date" min={widget.min} max={widget.max} value={value} onChange={(e) => setValue(e.target.value)} className="max-w-56" />
          <div className="flex items-center gap-3">
            <Button type="submit" disabled={disabled || !value}>
              Continue
            </Button>
            {typeInstead}
          </div>
        </form>
      );
    }
    case "single_select":
      return (
        <div className="space-y-3" data-testid="widget-single_select">
          <div className="flex flex-wrap gap-2">
            {widget.options.map((o) => (
              <Chip key={o.value} selected={value === o.value} onClick={() => setValue(o.value)} title={o.description ?? undefined}>
                {o.label}
              </Chip>
            ))}
          </div>
          {value && widget.options.find((o) => o.value === value)?.description && (
            <p className="text-sm text-ink-muted">{widget.options.find((o) => o.value === value)?.description}</p>
          )}
          <div className="flex items-center gap-3">
            <Button type="button" disabled={disabled || !value} onClick={() => submitValue(value)}>
              Continue
            </Button>
            {typeInstead}
          </div>
        </div>
      );
    case "multi_select": {
      const toggle = (v: string) => setMulti((m) => (m.includes(v) ? m.filter((x) => x !== v) : [...m, v]));
      const addCustom = () => {
        const items = splitChips(custom).filter((c) => !multi.includes(c));
        if (items.length) setMulti((m) => [...m, ...items]);
        setCustom("");
      };
      const ok = multi.length >= widget.min && multi.length <= widget.max;
      return (
        <div className="space-y-3" data-testid="widget-multi_select">
          <div className="flex flex-wrap gap-2">
            {widget.options.map((o) => (
              <Chip key={o.value} selected={multi.includes(o.value)} onClick={() => toggle(o.value)}>
                {o.label}
              </Chip>
            ))}
            {multi
              .filter((v) => !widget.options.some((o) => o.value === v))
              .map((v) => (
                <Chip key={v} selected onRemove={() => toggle(v)}>
                  {v}
                </Chip>
              ))}
          </div>
          {widget.allow_custom && (
            <div className="flex gap-2">
              <Input name="custom" placeholder="Add your own" value={custom} onChange={(e) => setCustom(e.target.value)} onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addCustom())} />
              <Button type="button" variant="secondary" onClick={addCustom} disabled={!custom.trim()}>
                Add
              </Button>
            </div>
          )}
          <div className="flex items-center gap-3">
            <Button type="button" disabled={disabled || !ok} onClick={() => submitValue(multi)}>
              Continue
            </Button>
            {typeInstead}
          </div>
        </div>
      );
    }
    case "chips": {
      const add = (raw: string) => {
        const items = splitChips(raw).filter((c) => !multi.includes(c));
        if (items.length) setMulti((m) => [...m, ...items].slice(0, widget.max));
        setCustom("");
      };
      return (
        <div className="space-y-3" data-testid="widget-chips">
          {widget.suggestions.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {widget.suggestions.map((s) => (
                <Chip key={s} selected={multi.includes(s)} onClick={() => (multi.includes(s) ? setMulti((m) => m.filter((x) => x !== s)) : add(s))}>
                  {s}
                </Chip>
              ))}
            </div>
          )}
          {multi.filter((v) => !widget.suggestions.includes(v)).length > 0 && (
            <div className="flex flex-wrap gap-2">
              {multi
                .filter((v) => !widget.suggestions.includes(v))
                .map((v) => (
                  <Chip key={v} selected onRemove={() => setMulti((m) => m.filter((x) => x !== v))}>
                    {v}
                  </Chip>
                ))}
            </div>
          )}
          <div className="flex gap-2">
            <Input name="custom" placeholder={widget.placeholder || "Add items, separated by commas"} value={custom} onChange={(e) => setCustom(e.target.value)} onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), add(custom))} />
            <Button type="button" variant="secondary" onClick={() => add(custom)} disabled={!custom.trim()}>
              Add
            </Button>
          </div>
          <div className="flex items-center gap-3">
            <Button type="button" disabled={disabled} onClick={() => submitValue(multi.length ? multi : ["none"])}>
              {multi.length ? "Continue" : "None, continue"}
            </Button>
            {typeInstead}
          </div>
        </div>
      );
    }
    default:
      return null;
  }
}

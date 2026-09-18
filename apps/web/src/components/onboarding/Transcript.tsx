"use client";

import { useEffect, useRef } from "react";

export interface Message {
  role: "assistant" | "user";
  content: string;
}

export function Transcript({ messages, thinking }: { messages: Message[]; thinking?: boolean }) {
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [messages.length, thinking]);
  return (
    <ol className="space-y-3" aria-live="polite">
      {messages.map((m, i) => (
        <li key={i} className={m.role === "assistant" ? "flex" : "flex justify-end"}>
          {m.role === "assistant" ? (
            <p className="max-w-[85%] rounded-md border border-line bg-surface px-4 py-3 text-ink">{m.content}</p>
          ) : (
            <p className="max-w-[85%] px-1 py-1 text-right text-ink-muted">{m.content}</p>
          )}
        </li>
      ))}
      {thinking && (
        <li className="flex" aria-label="Thinking">
          <span className="inline-flex gap-1 rounded-md border border-line bg-surface px-4 py-3">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-ink-muted" />
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-ink-muted [animation-delay:120ms]" />
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-ink-muted [animation-delay:240ms]" />
          </span>
        </li>
      )}
      <div ref={endRef} />
    </ol>
  );
}

"use client";

import {
  useMe,
  useOnboardingComplete,
  useOnboardingStart,
  useOnboardingTurn,
  type Answer,
  type TurnResponse,
} from "@larder/api-client";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ReviewCard } from "@/components/onboarding/ReviewCard";
import { Transcript, type Message } from "@/components/onboarding/Transcript";
import { WidgetRenderer } from "@/components/onboarding/WidgetRenderer";
import { Banner } from "@/components/ui";

function summarise(answer: Answer): string {
  if (answer.kind === "text") return answer.text;
  const v = answer.value;
  if (Array.isArray(v)) return v.length ? v.join(", ") : "none";
  return String(v);
}

export default function OnboardingPage() {
  const router = useRouter();
  const me = useMe();
  const start = useOnboardingStart();
  const turn = useOnboardingTurn();
  const complete = useOnboardingComplete();
  const [turnState, setTurnState] = useState<TurnResponse | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const started = useRef(false);

  // Someone who already finished onboarding lands on Today. Once a conversation has started here, the
  // completion refetch must not hijack the hand-off to pantry setup.
  useEffect(() => {
    if (me.data?.onboarding_status === "complete" && !started.current) router.replace("/today");
  }, [me.data, router]);

  useEffect(() => {
    if (started.current || !me.data || me.data.onboarding_status === "complete") return;
    started.current = true;
    start.mutate(undefined, {
      onSuccess: (t) => {
        setTurnState(t);
        setMessages([{ role: "assistant", content: t.message }]);
      },
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [me.data]);

  const answer = (a: Answer) => {
    if (!turnState) return;
    setMessages((m) => [...m, { role: "user", content: summarise(a) }]);
    turn.mutate(
      { thread_id: turnState.thread_id, answer: a },
      {
        onSuccess: (t) => {
          setTurnState(t);
          setMessages((m) => [...m, { role: "assistant", content: t.message }]);
        },
      },
    );
  };

  const confirm = () => {
    if (!turnState) return;
    complete.mutate({ thread_id: turnState.thread_id, overrides: null }, { onSuccess: () => router.replace("/pantry/setup") });
  };

  const busy = turn.isPending || start.isPending;
  const error = start.error ?? turn.error ?? complete.error;

  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-xl flex-col px-4 py-8">
      <header className="mb-6">
        <p className="text-sm font-medium text-accent">Larder</p>
        <h1 className="mt-1 text-2xl">Let&apos;s set up your kitchen profile.</h1>
        {turnState && (
          <p className="mt-1 text-sm text-ink-muted" aria-live="polite">
            {turnState.progress.answered} of {turnState.progress.total} answered
          </p>
        )}
      </header>
      <div className="flex-1 space-y-6">
        <Transcript messages={messages} thinking={busy} />
        {error && (
          <Banner tone="danger">{error instanceof Error ? error.message : "Something went wrong. Try that again."}</Banner>
        )}
        {turnState && !turnState.is_complete && turnState.widget && (
          <div className="rounded-md border border-line bg-surface-alt p-4">
            <WidgetRenderer key={`${turnState.field}-${messages.length}`} widget={turnState.widget} onSubmit={answer} disabled={busy} />
          </div>
        )}
        {turnState?.is_complete && <ReviewCard draft={turnState.draft} onConfirm={confirm} busy={complete.isPending} />}
      </div>
    </main>
  );
}

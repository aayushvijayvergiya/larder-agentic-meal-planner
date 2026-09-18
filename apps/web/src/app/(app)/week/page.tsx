"use client";

import { useState } from "react";
import { CoverageLine } from "@/components/plan/CoverageLine";
import { JobBanner } from "@/components/plan/JobBanner";
import { PlanEntryCard } from "@/components/plan/PlanEntryCard";
import { SwapSheet } from "@/components/plan/SwapSheet";
import { usePlanActions } from "@/components/plan/usePlanActions";
import { ViewToggle } from "@/components/plan/ViewToggle";
import { Banner, Button, EmptyState, Sheet, SkeletonList } from "@/components/ui";
import { dayHeading, shortDay, todayIso } from "@/lib/format";

export default function WeekPage() {
  const a = usePlanActions();
  const plan = a.plan.data?.plan ?? null;
  const [confirm, setConfirm] = useState(false);
  const today = todayIso();

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl">This week</h1>
          {plan && (
            <p className="mt-1 text-sm text-ink-muted">
              {shortDay(plan.start_date)} to {shortDay(plan.end_date)}
            </p>
          )}
        </div>
        <div className="flex items-center gap-3">
          <ViewToggle />
          {plan && (
            <Button variant="secondary" size="sm" onClick={() => setConfirm(true)}>
              Regenerate week
            </Button>
          )}
        </div>
      </div>
      <div className="mt-5 space-y-4">
        <JobBanner jobId={a.jobId} onRetry={a.generateWeek} />
        {a.error && <Banner tone="danger">{a.error instanceof Error ? a.error.message : "Something went wrong."}</Banner>}
        {plan && <CoverageLine plan={plan} />}
        {a.plan.isLoading ? (
          <SkeletonList rows={5} />
        ) : !plan ? (
          a.plan.data?.active_job ? null : (
            <EmptyState action={<Button onClick={a.generateWeek} loading={a.generating}>Plan my week</Button>}>No plan for this week yet.</EmptyState>
          )
        ) : (
          <div className="grid gap-6 lg:grid-cols-7 lg:gap-3">
            {plan.days.map((d) => (
              <section key={d.date} aria-label={dayHeading(d.date)} className={d.date < today ? "opacity-60" : ""}>
                <h2 className="mb-2 text-base">{dayHeading(d.date)}</h2>
                <div className="space-y-2">
                  {d.entries.map((e) => (
                    <PlanEntryCard key={e.id} entry={e} compact onSwap={() => a.setSwapping(e)} onFeedback={(k) => a.giveFeedback(e, k)} />
                  ))}
                </div>
              </section>
            ))}
          </div>
        )}
      </div>
      <Sheet open={confirm} onClose={() => setConfirm(false)} title="Regenerate the whole week?">
        <p className="text-sm text-ink-muted">Today onwards will be replanned from your current pantry. Feedback you&apos;ve given is kept.</p>
        <div className="mt-5 flex gap-3">
          <Button
            onClick={() => {
              setConfirm(false);
              a.generateWeek();
            }}
          >
            Regenerate
          </Button>
          <Button variant="ghost" onClick={() => setConfirm(false)}>
            Keep it
          </Button>
        </div>
      </Sheet>
      <SwapSheet open={!!a.swapping} mealName={a.swapping?.meal.name} onClose={() => a.setSwapping(null)} onSwap={a.confirmSwap} busy={a.swapPending} />
    </div>
  );
}

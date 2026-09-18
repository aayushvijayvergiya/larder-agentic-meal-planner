"use client";

import { CoverageLine } from "@/components/plan/CoverageLine";
import { JobBanner } from "@/components/plan/JobBanner";
import { PlanEntryCard } from "@/components/plan/PlanEntryCard";
import { SwapSheet } from "@/components/plan/SwapSheet";
import { usePlanActions } from "@/components/plan/usePlanActions";
import { ViewToggle } from "@/components/plan/ViewToggle";
import { Banner, Button, EmptyState, SkeletonList } from "@/components/ui";
import { dayHeading, todayIso } from "@/lib/format";

export default function TodayPage() {
  const today = todayIso();
  const a = usePlanActions();
  const plan = a.plan.data?.plan ?? null;
  const day = plan?.days.find((d) => d.date === today) ?? null;

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl">{dayHeading(today)}</h1>
          {plan && day && (
            <div className="mt-1">
              <CoverageLine plan={plan} dayEntries={day.entries} />
            </div>
          )}
        </div>
        <ViewToggle />
      </div>

      <div className="mt-5 space-y-4">
        <JobBanner jobId={a.jobId} onRetry={a.generateWeek} />
        {a.error && <Banner tone="danger">{a.error instanceof Error ? a.error.message : "Something went wrong."}</Banner>}

        {a.plan.isLoading ? (
          <SkeletonList rows={4} />
        ) : !plan || !day || day.entries.length === 0 ? (
          a.plan.data?.active_job ? null : (
            <EmptyState
              action={
                <Button onClick={a.generateWeek} loading={a.generating} data-testid="plan-my-week">
                  Plan my week
                </Button>
              }
            >
              No plan yet. Larder will build one from what&apos;s in your pantry.
            </EmptyState>
          )
        ) : (
          <>
            <div className="space-y-3" data-testid="today-entries">
              {day.entries.map((entry) => (
                <PlanEntryCard key={entry.id} entry={entry} onSwap={() => a.setSwapping(entry)} onFeedback={(k) => a.giveFeedback(entry, k)} />
              ))}
            </div>
            <div className="flex justify-end">
              <Button variant="ghost" size="sm" onClick={a.regenerateToday} loading={a.generating}>
                Replan today
              </Button>
            </div>
          </>
        )}
      </div>

      <SwapSheet open={!!a.swapping} mealName={a.swapping?.meal.name} onClose={() => a.setSwapping(null)} onSwap={a.confirmSwap} busy={a.swapPending} />
    </div>
  );
}

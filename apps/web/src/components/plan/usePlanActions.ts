"use client";

import { useCurrentPlan, useFeedback, useGeneratePlan, useSwapEntry, type PlanEntryOut } from "@larder/api-client";
import { useState } from "react";
import { usePlanScope } from "@/lib/scope";

/** Shared state for Today and Week: current plan, job tracking, swap and feedback handlers. */
export function usePlanActions(date?: string) {
  const { scope } = usePlanScope();
  const plan = useCurrentPlan({ scope, date });
  const generate = useGeneratePlan();
  const swap = useSwapEntry();
  const feedback = useFeedback();
  const [localJobId, setJobId] = useState<string | undefined>();
  const [swapping, setSwapping] = useState<PlanEntryOut | null>(null);
  // A job started elsewhere (scheduler, another device) shows up as the plan's active job.
  const jobId = localJobId ?? plan.data?.active_job?.id;

  const generateWeek = () =>
    generate.mutate({ scope, mode: "week" }, { onSuccess: (r) => setJobId(r.job_id) });
  const regenerateToday = () =>
    generate.mutate({ scope, mode: "today" }, { onSuccess: (r) => setJobId(r.job_id) });
  const confirmSwap = (reason?: string) => {
    if (!swapping || !plan.data?.plan) return;
    swap.mutate(
      { planId: plan.data.plan.id, entryId: swapping.id, reason },
      {
        onSuccess: (r) => {
          setJobId(r.job_id);
          setSwapping(null);
        },
      },
    );
  };
  const giveFeedback = (entry: PlanEntryOut, kind: "up" | "down" | "cooked") =>
    feedback.mutate({ mealId: entry.meal.id, kind, plan_entry_id: entry.id });

  return {
    scope,
    plan,
    jobId,
    generateWeek,
    regenerateToday,
    generating: generate.isPending,
    swapping,
    setSwapping,
    confirmSwap,
    swapPending: swap.isPending,
    giveFeedback,
    error: generate.error ?? swap.error ?? feedback.error,
  };
}

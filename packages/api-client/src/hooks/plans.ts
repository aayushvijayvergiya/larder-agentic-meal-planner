import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { unwrap, type Schemas } from "../client";
import { keys } from "../keys";
import { useApi } from "../provider";

export type CurrentPlanOut = Schemas["CurrentPlanOut"];
export type PlanOut = Schemas["PlanOut"];
export type PlanEntryOut = Schemas["PlanEntryOut"];
export type JobOut = Schemas["JobOut"];
export type ShoppingListOut = Schemas["ShoppingListOut"];
export type PlanScope = "single" | "family";

export function useCurrentPlan(opts: { scope?: PlanScope; date?: string } = {}, enabled = true) {
  const api = useApi();
  return useQuery({
    queryKey: keys.plan(opts.scope, opts.date),
    queryFn: async () =>
      unwrap(await api.raw.GET("/api/v1/plans/current", { params: { query: { scope: opts.scope, date: opts.date } } })),
    enabled,
  });
}

export function useGeneratePlan() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: Schemas["GenerateRequest"]) => unwrap(await api.raw.POST("/api/v1/plans/generate", { body })),
    onSuccess: () => void qc.invalidateQueries({ queryKey: keys.plans }),
  });
}

export function useSwapEntry() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (vars: { planId: string; entryId: string; reason?: string }) =>
      unwrap(
        await api.raw.POST("/api/v1/plans/{plan_id}/entries/{entry_id}/swap", {
          params: { path: { plan_id: vars.planId, entry_id: vars.entryId } },
          body: { reason: vars.reason },
        }),
      ),
    onSuccess: () => void qc.invalidateQueries({ queryKey: keys.plans }),
  });
}

/** Polls a job every `pollMs` until it is ready or failed, then invalidates plan queries once. */
export function useJob(jobId: string | undefined, opts: { pollMs?: number } = {}) {
  const api = useApi();
  const qc = useQueryClient();
  const query = useQuery({
    queryKey: keys.job(jobId ?? ""),
    queryFn: async () => unwrap(await api.raw.GET("/api/v1/plans/jobs/{job_id}", { params: { path: { job_id: jobId! } } })),
    enabled: !!jobId,
    refetchInterval: (q) => {
      const s = q.state.data?.status;
      return s === "ready" || s === "failed" ? false : (opts.pollMs ?? 2000);
    },
  });
  const status = query.data?.status;
  useEffect(() => {
    if (status === "ready" || status === "failed") {
      void qc.invalidateQueries({ queryKey: keys.plans });
      void qc.invalidateQueries({ queryKey: ["meals"] });
    }
  }, [status, qc]);
  return query;
}

export function useShoppingList(planId: string | undefined) {
  const api = useApi();
  return useQuery({
    queryKey: keys.shopping(planId ?? ""),
    queryFn: async () =>
      unwrap(await api.raw.GET("/api/v1/plans/{plan_id}/shopping-list", { params: { path: { plan_id: planId! } } })),
    enabled: !!planId,
  });
}

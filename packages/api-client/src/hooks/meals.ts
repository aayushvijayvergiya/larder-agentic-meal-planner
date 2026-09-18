import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { unwrap, type Schemas } from "../client";
import { keys } from "../keys";
import { useApi } from "../provider";

export type MealOut = Schemas["MealOut"];
export type MealCreate = Schemas["MealCreate"];
export type MealPatch = Schemas["MealPatch"];
export type FeedbackKind = Schemas["FeedbackCreate"]["kind"];

export interface MealListParams {
  query?: string;
  meal_type?: string;
  source?: "user" | "generated" | "all";
}

export function useMeals(params: MealListParams = {}, enabled = true) {
  const api = useApi();
  return useQuery({
    queryKey: keys.meals(params as Record<string, string | undefined>),
    queryFn: async () => unwrap(await api.raw.GET("/api/v1/meals", { params: { query: params } })),
    enabled,
  });
}

export function useMeal(id: string | undefined) {
  const api = useApi();
  return useQuery({
    queryKey: keys.meal(id ?? ""),
    queryFn: async () => unwrap(await api.raw.GET("/api/v1/meals/{meal_id}", { params: { path: { meal_id: id! } } })),
    enabled: !!id,
  });
}

function useInvalidateMeals() {
  const qc = useQueryClient();
  return (id?: string) => {
    void qc.invalidateQueries({ queryKey: ["meals"] });
    if (id) void qc.invalidateQueries({ queryKey: keys.meal(id) });
    void qc.invalidateQueries({ queryKey: keys.plans });
  };
}

export function useCreateMeal() {
  const api = useApi();
  const invalidate = useInvalidateMeals();
  return useMutation({
    mutationFn: async (body: MealCreate) => unwrap(await api.raw.POST("/api/v1/meals", { body })),
    onSuccess: () => invalidate(),
  });
}

export function useUpdateMeal() {
  const api = useApi();
  const invalidate = useInvalidateMeals();
  return useMutation({
    mutationFn: async (vars: { id: string; patch: MealPatch }) =>
      unwrap(await api.raw.PATCH("/api/v1/meals/{meal_id}", { params: { path: { meal_id: vars.id } }, body: vars.patch })),
    onSuccess: (_d, vars) => invalidate(vars.id),
  });
}

export function useDeleteMeal() {
  const api = useApi();
  const invalidate = useInvalidateMeals();
  return useMutation({
    mutationFn: async (id: string) => unwrap(await api.raw.DELETE("/api/v1/meals/{meal_id}", { params: { path: { meal_id: id } } })),
    onSuccess: () => invalidate(),
  });
}

export function useEnrichMeal() {
  const api = useApi();
  const invalidate = useInvalidateMeals();
  return useMutation({
    mutationFn: async (id: string) =>
      unwrap(await api.raw.POST("/api/v1/meals/{meal_id}/enrich", { params: { path: { meal_id: id } } })),
    onSuccess: (_d, id) => invalidate(id),
  });
}

export function useFeedback() {
  const api = useApi();
  const invalidate = useInvalidateMeals();
  return useMutation({
    mutationFn: async (vars: { mealId: string; kind: FeedbackKind; plan_entry_id?: string; comment?: string }) =>
      unwrap(
        await api.raw.POST("/api/v1/meals/{meal_id}/feedback", {
          params: { path: { meal_id: vars.mealId } },
          body: { kind: vars.kind, plan_entry_id: vars.plan_entry_id, comment: vars.comment },
        }),
      ),
    onSuccess: (_d, vars) => invalidate(vars.mealId),
  });
}

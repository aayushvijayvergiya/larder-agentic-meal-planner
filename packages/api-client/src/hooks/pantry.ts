import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { unwrap, type Schemas } from "../client";
import { keys } from "../keys";
import { useApi } from "../provider";

export type PantryOut = Schemas["PantryOut"];
export type PantryItemOut = Schemas["PantryItemOut"];
export type PantryItemIn = Schemas["PantryItemIn"];
export type PantryCategory = PantryItemOut["category"];

function useInvalidatePantry() {
  const qc = useQueryClient();
  return () => {
    void qc.invalidateQueries({ queryKey: keys.pantry });
    void qc.invalidateQueries({ queryKey: keys.plans });
  };
}

export function usePantry(enabled = true) {
  const api = useApi();
  return useQuery({ queryKey: keys.pantry, queryFn: async () => unwrap(await api.raw.GET("/api/v1/pantry")), enabled });
}

export function usePantrySuggestions(enabled = true) {
  const api = useApi();
  return useQuery({
    queryKey: keys.pantrySuggestions,
    queryFn: async () => unwrap(await api.raw.GET("/api/v1/pantry/suggestions")),
    enabled,
  });
}

export function useAddPantryItems() {
  const api = useApi();
  const invalidate = useInvalidatePantry();
  return useMutation({
    mutationFn: async (items: PantryItemIn[]) => unwrap(await api.raw.POST("/api/v1/pantry/items", { body: { items } })),
    onSuccess: invalidate,
  });
}

export function useUpdatePantryItem() {
  const api = useApi();
  const invalidate = useInvalidatePantry();
  return useMutation({
    mutationFn: async (vars: { id: string; patch: Schemas["PantryItemPatch"] }) =>
      unwrap(await api.raw.PATCH("/api/v1/pantry/items/{item_id}", { params: { path: { item_id: vars.id } }, body: vars.patch })),
    onSuccess: invalidate,
  });
}

export function useDeletePantryItem() {
  const api = useApi();
  const invalidate = useInvalidatePantry();
  return useMutation({
    mutationFn: async (id: string) =>
      unwrap(await api.raw.DELETE("/api/v1/pantry/items/{item_id}", { params: { path: { item_id: id } } })),
    onSuccess: invalidate,
  });
}

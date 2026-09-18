import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { unwrap, type Schemas } from "../client";
import { keys } from "../keys";
import { useApi } from "../provider";

export type HouseholdOut = Schemas["HouseholdOut"];
export type HouseholdPatch = Schemas["HouseholdPatch"];
export type InviteOut = Schemas["InviteOut"];
export type SlotDef = Schemas["SlotDef"];

export function useHousehold(enabled = true) {
  const api = useApi();
  return useQuery({
    queryKey: keys.household,
    queryFn: async () => unwrap(await api.raw.GET("/api/v1/households/me")),
    enabled,
  });
}

function useInvalidateHousehold() {
  const qc = useQueryClient();
  return () => {
    void qc.invalidateQueries({ queryKey: keys.household });
    void qc.invalidateQueries({ queryKey: keys.me });
    void qc.invalidateQueries({ queryKey: keys.plans });
  };
}

export function useUpdateHousehold() {
  const api = useApi();
  const invalidate = useInvalidateHousehold();
  return useMutation({
    mutationFn: async (vars: { id: string; patch: HouseholdPatch }) =>
      unwrap(await api.raw.PATCH("/api/v1/households/{household_id}", { params: { path: { household_id: vars.id } }, body: vars.patch })),
    onSuccess: invalidate,
  });
}

export function useInvites(householdId: string | undefined, enabled = true) {
  const api = useApi();
  return useQuery({
    queryKey: [...keys.household, "invites", householdId],
    queryFn: async () =>
      unwrap(await api.raw.GET("/api/v1/households/{household_id}/invites", { params: { path: { household_id: householdId! } } })),
    enabled: enabled && !!householdId,
  });
}

export function useCreateInvite() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (vars: { id: string }) =>
      unwrap(await api.raw.POST("/api/v1/households/{household_id}/invites", { params: { path: { household_id: vars.id } }, body: { expires_in_days: 7, max_uses: 10 } })),
    onSuccess: () => void qc.invalidateQueries({ queryKey: keys.household }),
  });
}

export function useJoinHousehold() {
  const api = useApi();
  const invalidate = useInvalidateHousehold();
  return useMutation({
    mutationFn: async (vars: { code: string }) => unwrap(await api.raw.POST("/api/v1/households/join", { body: vars })),
    onSuccess: invalidate,
  });
}

export function useRemoveMember() {
  const api = useApi();
  const invalidate = useInvalidateHousehold();
  return useMutation({
    mutationFn: async (vars: { id: string; userId: string }) =>
      unwrap(
        await api.raw.DELETE("/api/v1/households/{household_id}/members/{user_id}", {
          params: { path: { household_id: vars.id, user_id: vars.userId } },
        }),
      ),
    onSuccess: invalidate,
  });
}

export function useSetPreferredView() {
  const api = useApi();
  const invalidate = useInvalidateHousehold();
  return useMutation({
    mutationFn: async (vars: { id: string; preferred_view: "single" | "family" }) =>
      unwrap(
        await api.raw.PATCH("/api/v1/households/{household_id}/members/me", {
          params: { path: { household_id: vars.id } },
          body: { preferred_view: vars.preferred_view },
        }),
      ),
    onSuccess: invalidate,
  });
}

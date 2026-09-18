import { useMutation, useQueryClient } from "@tanstack/react-query";
import { unwrap, type Schemas } from "../client";
import { keys } from "../keys";
import { useApi } from "../provider";

export type TurnResponse = Schemas["TurnResponse"];
export type Widget = NonNullable<TurnResponse["widget"]>;
export type ProfileDraft = Schemas["ProfileDraft"];
export type Answer = Schemas["WidgetAnswer"] | Schemas["TextAnswer"];
export type CompleteResponse = Schemas["CompleteResponse"];

export function useOnboardingStart() {
  const api = useApi();
  return useMutation({
    mutationFn: async () => unwrap(await api.raw.POST("/api/v1/onboarding/start")),
  });
}

export function useOnboardingTurn() {
  const api = useApi();
  return useMutation({
    mutationFn: async (vars: { thread_id: string; answer: Answer }) =>
      unwrap(await api.raw.POST("/api/v1/onboarding/turn", { body: vars })),
  });
}

export function useOnboardingComplete() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (vars: { thread_id: string; overrides?: Schemas["ProfilePatch"] | null }) =>
      unwrap(await api.raw.POST("/api/v1/onboarding/complete", { body: vars })),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: keys.me });
      void qc.invalidateQueries({ queryKey: keys.household });
    },
  });
}

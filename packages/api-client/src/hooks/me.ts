import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { unwrap, type Schemas } from "../client";
import { keys } from "../keys";
import { useApi } from "../provider";

export type MeOut = Schemas["MeOut"];
export type ProfileOut = Schemas["ProfileOut"];
export type ProfilePatch = Schemas["ProfilePatch"];

export function useMe(enabled = true) {
  const api = useApi();
  return useQuery({
    queryKey: keys.me,
    queryFn: async () => unwrap(await api.raw.GET("/api/v1/me")),
    enabled,
    retry: (count, err) => (err as { status?: number }).status === 401 ? false : count < 2,
  });
}

export function useUpdateMe() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: ProfilePatch) => unwrap(await api.raw.PATCH("/api/v1/me", { body })),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: keys.me });
      void qc.invalidateQueries({ queryKey: keys.plans });
    },
  });
}

/** TanStack Query keys (LLD §9.3). */
export const keys = {
  me: ["me"] as const,
  household: ["household"] as const,
  pantry: ["pantry"] as const,
  pantrySuggestions: ["pantry", "suggestions"] as const,
  meals: (params?: Record<string, string | undefined>) => ["meals", params ?? {}] as const,
  meal: (id: string) => ["meal", id] as const,
  plan: (scope?: string, date?: string) => ["plan", scope ?? "default", date ?? "today"] as const,
  plans: ["plan"] as const,
  job: (id: string) => ["job", id] as const,
  shopping: (planId: string) => ["shopping", planId] as const,
};

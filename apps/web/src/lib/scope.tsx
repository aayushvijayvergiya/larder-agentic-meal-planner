"use client";

import { useHousehold, type PlanScope } from "@larder/api-client";
import { useCallback, useSyncExternalStore } from "react";

const KEY = "larder-scope";
const listeners = new Set<() => void>();
let memory: PlanScope | null = null;

function read(): PlanScope | null {
  try {
    const v = window.localStorage.getItem(KEY);
    if (v === "single" || v === "family") return v;
  } catch {
    // ignore
  }
  return memory;
}

/** The plan view the user is looking at: falls back to the household's preferred view; hidden when alone. */
export function usePlanScope(): { scope: PlanScope; setScope: (s: PlanScope) => void; canToggle: boolean } {
  const household = useHousehold();
  const stored = useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    read,
    () => null,
  );
  const members = household.data?.members ?? [];
  const canToggle = members.length > 1;
  const preferred = (members.find(() => true)?.preferred_view as PlanScope | undefined) ?? "single";
  const scope: PlanScope = canToggle ? (stored ?? preferred) : "single";
  const setScope = useCallback((s: PlanScope) => {
    memory = s;
    try {
      window.localStorage.setItem(KEY, s);
    } catch {
      // ignore
    }
    listeners.forEach((l) => l());
  }, []);
  return { scope, setScope, canToggle };
}

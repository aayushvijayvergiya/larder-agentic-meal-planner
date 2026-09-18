"use client";

import { Segmented } from "@/components/ui";
import { usePlanScope } from "@/lib/scope";

export function ViewToggle() {
  const { scope, setScope, canToggle } = usePlanScope();
  if (!canToggle) return null;
  return (
    <Segmented
      label="Plan view"
      value={scope}
      onChange={setScope}
      options={[
        { value: "single", label: "Just me" },
        { value: "family", label: "Family" },
      ]}
    />
  );
}

"use client";

import { useState } from "react";
import { Button, Chip, Input, Sheet } from "@/components/ui";

const REASONS = ["Too heavy", "No time", "Had it recently", "Not in the mood"];

export function SwapSheet({ open, mealName, onClose, onSwap, busy }: { open: boolean; mealName?: string; onClose: () => void; onSwap: (reason?: string) => void; busy?: boolean }) {
  const [reason, setReason] = useState<string>("");
  const [other, setOther] = useState("");
  const final = reason === "other" ? other.trim() : reason;
  return (
    <Sheet open={open} onClose={onClose} title={mealName ? `Swap ${mealName}` : "Swap this meal"}>
      <p className="text-sm text-ink-muted">Tell the planner why, and it will pick something that fits better.</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {REASONS.map((r) => (
          <Chip key={r} selected={reason === r} onClick={() => setReason(r)}>
            {r}
          </Chip>
        ))}
        <Chip selected={reason === "other"} onClick={() => setReason("other")}>
          Something else…
        </Chip>
      </div>
      {reason === "other" && (
        <div className="mt-3">
          <Input name="reason" placeholder="e.g. we have guests" value={other} onChange={(e) => setOther(e.target.value)} maxLength={160} autoFocus />
        </div>
      )}
      <div className="mt-5 flex gap-3">
        <Button onClick={() => onSwap(final || undefined)} loading={busy} data-testid="swap-confirm">
          Swap it
        </Button>
        <Button variant="ghost" onClick={onClose}>
          Cancel
        </Button>
      </div>
    </Sheet>
  );
}

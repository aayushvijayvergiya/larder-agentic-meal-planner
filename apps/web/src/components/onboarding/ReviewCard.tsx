"use client";

import type { ProfileDraft } from "@larder/api-client";
import { Button } from "@/components/ui";
import { titleCase } from "@/lib/format";

function Row({ label, value }: { label: string; value?: string | null }) {
  if (!value) return null;
  return (
    <div className="flex justify-between gap-4 border-b border-line py-2 text-sm last:border-b-0">
      <dt className="text-ink-muted">{label}</dt>
      <dd className="text-right text-ink">{value}</dd>
    </div>
  );
}

const list = (v?: string[] | null) => (v && v.length ? v.map(titleCase).join(", ") : "None");

export function ReviewCard({ draft, onConfirm, busy }: { draft: ProfileDraft; onConfirm: () => void; busy?: boolean }) {
  return (
    <section className="rounded-md border border-line bg-surface p-4" data-testid="review-card" aria-label="Review your profile">
      <h2 className="text-xl">Your profile</h2>
      <dl className="mt-3">
        <Row label="Name" value={draft.display_name} />
        <Row label="Born" value={draft.date_of_birth} />
        <Row label="Height" value={draft.height_cm ? `${draft.height_cm} cm` : null} />
        <Row label="Weight" value={draft.weight_kg ? `${draft.weight_kg} kg` : null} />
        <Row label="Activity" value={draft.activity_level ? titleCase(draft.activity_level) : null} />
        <Row label="Diet" value={draft.diet_type ? titleCase(draft.diet_type) : null} />
        <Row label="Cuisines" value={list(draft.cuisines)} />
        <Row label="Allergies" value={list(draft.allergens)} />
        <Row label="Dislikes" value={list(draft.dislikes)} />
        <Row label="Loves" value={list(draft.likes)} />
        <Row label="Health" value={draft.medical_conditions?.length ? draft.medical_conditions.map((c) => c.name).join(", ") : "None"} />
        <Row label="Notes" value={draft.medical_notes} />
        <Row label="Goals" value={list(draft.goals)} />
        <Row label="Cooking" value={draft.cooking_skill ? titleCase(draft.cooking_skill) : null} />
        <Row label="Time to cook" value={draft.max_prep_minutes ? `${draft.max_prep_minutes} min` : null} />
      </dl>
      <p className="mt-3 text-sm text-ink-muted">You can change any of this later under Profile. Suggestions are not medical advice.</p>
      <Button className="mt-4 w-full" onClick={onConfirm} loading={busy} data-testid="confirm-profile">
        Confirm and continue
      </Button>
    </section>
  );
}

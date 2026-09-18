"use client";

import { useHousehold, useMe, useSetPreferredView, useUpdateHousehold } from "@larder/api-client";
import { useState } from "react";
import { InviteCode, JoinForm, MemberList } from "@/components/household/Members";
import { ScheduleForm } from "@/components/household/ScheduleForm";
import { SlotsEditor } from "@/components/household/SlotsEditor";
import { Banner, Button, Input, Segmented, SkeletonList } from "@/components/ui";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border-t border-line py-6">
      <h2 className="mb-3 text-lg">{title}</h2>
      {children}
    </section>
  );
}

export default function HouseholdPage() {
  const me = useMe();
  const household = useHousehold();
  const update = useUpdateHousehold();
  const setView = useSetPreferredView();
  const [name, setName] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);

  if (household.isLoading || me.isLoading) return <SkeletonList rows={3} />;
  const h = household.data;
  const profile = me.data?.profile;
  if (!h || !profile) return <p className="text-ink-muted">Couldn&apos;t load your household.</p>;
  const mine = h.members.find((m) => m.user_id === profile.id);
  const isOwner = mine?.role === "owner";

  const save = (patch: Parameters<typeof update.mutate>[0]["patch"], label: string) =>
    update.mutate({ id: h.id, patch }, { onSuccess: () => setSaved(label) });

  return (
    <div>
      <h1 className="text-2xl">{h.name}</h1>
      <p className="mt-1 text-sm text-ink-muted">
        {h.members.length === 1 ? "Just you, for now." : `${h.members.length} people share this kitchen.`}
      </p>
      {saved && (
        <div className="mt-4">
          <Banner tone="success" action={<button className="underline" onClick={() => setSaved(null)}>Dismiss</button>}>
            {saved} saved.
          </Banner>
        </div>
      )}
      {update.error && <div className="mt-4"><Banner tone="danger">{update.error.message}</Banner></div>}

      <div className="mt-4">
        <Section title="Members">
          <MemberList household={h} meId={profile.id} isOwner={!!isOwner} />
        </Section>
        {isOwner && (
          <Section title="Invite someone">
            <InviteCode householdId={h.id} />
          </Section>
        )}
        <Section title="Join a household">
          <JoinForm />
        </Section>
        {h.members.length > 1 && mine && (
          <Section title="Your view">
            <p className="mb-2 text-sm text-ink-muted">Plan for everyone, or just for you from the same pantry.</p>
            <Segmented
              label="Preferred view"
              value={mine.preferred_view}
              onChange={(v) => setView.mutate({ id: h.id, preferred_view: v })}
              options={[
                { value: "family", label: "Family" },
                { value: "single", label: "Just me" },
              ]}
            />
          </Section>
        )}
        {isOwner && (
          <>
            <Section title="Kitchen name">
              <div className="flex items-end gap-2">
                <Input name="name" value={name ?? h.name} onChange={(e) => setName(e.target.value)} maxLength={60} />
                <Button variant="secondary" disabled={name === null || !name.trim() || name === h.name} onClick={() => save({ name: name!.trim() }, "Name")} loading={update.isPending}>
                  Save
                </Button>
              </div>
            </Section>
            <Section title="Meal slots">
              <SlotsEditor slots={h.slots} onSave={(slots) => save({ slots }, "Slots")} busy={update.isPending} />
            </Section>
            <Section title="Refresh schedule">
              <ScheduleForm household={h} onSave={(patch) => save(patch, "Schedule")} busy={update.isPending} />
            </Section>
          </>
        )}
      </div>
    </div>
  );
}

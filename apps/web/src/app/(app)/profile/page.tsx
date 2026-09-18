"use client";

import { useMe, useUpdateMe, type ProfilePatch } from "@larder/api-client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Banner, Button, Chip, Input, Segmented, Select, SkeletonList, Textarea } from "@/components/ui";
import { titleCase } from "@/lib/format";
import { supabaseBrowser } from "@/lib/supabase/client";
import { useTheme, type ThemeMode } from "@/lib/theme";

const DIETS = ["omnivore", "vegetarian", "eggetarian", "vegan", "pescatarian", "jain", "other"];
const ACTIVITY = ["sedentary", "light", "moderate", "active", "very_active"];
const SKILLS = ["beginner", "intermediate", "advanced"];
const GOALS = ["weight_loss", "muscle_gain", "maintenance", "manage_condition", "eat_healthier", "save_time", "reduce_waste"];

function ChipList({ label, values, onChange, placeholder }: { label: string; values: string[]; onChange: (v: string[]) => void; placeholder?: string }) {
  const [draft, setDraft] = useState("");
  const add = () => {
    const items = draft
      .split(",")
      .map((s) => s.trim())
      .filter((s) => s && !values.includes(s));
    if (items.length) onChange([...values, ...items]);
    setDraft("");
  };
  return (
    <div>
      <span className="mb-1 block text-sm font-medium">{label}</span>
      <div className="mb-2 flex flex-wrap gap-2">
        {values.map((v) => (
          <Chip key={v} selected onRemove={() => onChange(values.filter((x) => x !== v))}>
            {v}
          </Chip>
        ))}
        {!values.length && <span className="text-sm text-ink-muted">None</span>}
      </div>
      <div className="flex gap-2">
        <Input name={label} placeholder={placeholder ?? "Add, separated by commas"} value={draft} onChange={(e) => setDraft(e.target.value)} onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), add())} />
        <Button type="button" variant="secondary" onClick={add} disabled={!draft.trim()}>
          Add
        </Button>
      </div>
    </div>
  );
}

export default function ProfilePage() {
  const me = useMe();
  const update = useUpdateMe();
  const router = useRouter();
  const { theme, setTheme } = useTheme();
  const [patch, setPatch] = useState<ProfilePatch>({});
  const [saved, setSaved] = useState(false);

  if (me.isLoading) return <SkeletonList rows={3} />;
  const p = me.data?.profile;
  if (!p) return <p className="text-ink-muted">Couldn&apos;t load your profile.</p>;

  const v = <K extends keyof ProfilePatch>(k: K): NonNullable<ProfilePatch[K]> | undefined =>
    (patch[k] ?? (p as unknown as Record<string, unknown>)[k]) as NonNullable<ProfilePatch[K]> | undefined;
  const set = <K extends keyof ProfilePatch>(k: K, value: ProfilePatch[K]) => setPatch((x) => ({ ...x, [k]: value }));
  const dirty = Object.keys(patch).length > 0;
  const save = () => update.mutate(patch, { onSuccess: () => { setPatch({}); setSaved(true); } });
  const clearHealth = () => update.mutate({ medical_conditions: [], medical_notes: null }, { onSuccess: () => setSaved(true) });
  const signOut = async () => {
    await supabaseBrowser().auth.signOut();
    router.replace("/sign-in");
    router.refresh();
  };

  return (
    <div className="mx-auto max-w-xl">
      <h1 className="text-2xl">Profile</h1>
      <p className="mt-1 text-sm text-ink-muted">{p.email}</p>
      {saved && <div className="mt-4"><Banner tone="success" action={<button className="underline" onClick={() => setSaved(false)}>Dismiss</button>}>Profile saved. Your next plan will use it.</Banner></div>}
      {update.error && <div className="mt-4"><Banner tone="danger">{update.error.message}</Banner></div>}

      <section className="mt-6 space-y-4">
        <h2 className="text-lg">Basics</h2>
        <Input label="Name" name="display_name" value={v("display_name") ?? ""} onChange={(e) => set("display_name", e.target.value)} maxLength={40} />
        <div className="grid gap-4 sm:grid-cols-2">
          <Input label="Height (cm)" name="height_cm" type="number" min={50} max={250} value={v("height_cm") ?? ""} onChange={(e) => set("height_cm", e.target.value ? Number(e.target.value) : null)} />
          <Input label="Weight (kg)" name="weight_kg" type="number" min={20} max={400} step={0.5} value={v("weight_kg") ?? ""} onChange={(e) => set("weight_kg", e.target.value ? Number(e.target.value) : null)} />
          <Select label="Activity" name="activity_level" value={v("activity_level") ?? ""} onChange={(e) => set("activity_level", e.target.value as ProfilePatch["activity_level"])} placeholder="Choose" options={ACTIVITY.map((a) => ({ value: a, label: titleCase(a) }))} />
          <Select label="Cooking time" name="max_prep_minutes" value={String(v("max_prep_minutes") ?? "")} onChange={(e) => set("max_prep_minutes", Number(e.target.value))} placeholder="Choose" options={["15", "30", "45", "60", "90"].map((m) => ({ value: m, label: `${m} minutes` }))} />
        </div>
      </section>

      <section className="mt-8 space-y-4">
        <h2 className="text-lg">Diet</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <Select label="Diet type" name="diet_type" value={v("diet_type") ?? ""} onChange={(e) => set("diet_type", e.target.value as ProfilePatch["diet_type"])} placeholder="Choose" options={DIETS.map((d) => ({ value: d, label: titleCase(d) }))} />
          <Select label="Cooking skill" name="cooking_skill" value={v("cooking_skill") ?? ""} onChange={(e) => set("cooking_skill", e.target.value as ProfilePatch["cooking_skill"])} placeholder="Choose" options={SKILLS.map((s) => ({ value: s, label: titleCase(s) }))} />
        </div>
        <ChipList label="Cuisines" values={v("cuisines") ?? []} onChange={(x) => set("cuisines", x)} />
        <ChipList label="Allergies and intolerances" values={v("allergens") ?? []} onChange={(x) => set("allergens", x)} />
        <ChipList label="Dislikes" values={v("dislikes") ?? []} onChange={(x) => set("dislikes", x)} />
        <ChipList label="Loves" values={v("likes") ?? []} onChange={(x) => set("likes", x)} />
        <div>
          <span className="mb-1 block text-sm font-medium">Goals</span>
          <div className="flex flex-wrap gap-2">
            {GOALS.map((g) => {
              const goals = v("goals") ?? [];
              const on = goals.includes(g);
              return (
                <Chip key={g} selected={on} onClick={() => set("goals", on ? goals.filter((x) => x !== g) : [...goals, g])}>
                  {titleCase(g)}
                </Chip>
              );
            })}
          </div>
        </div>
      </section>

      <section className="mt-8 space-y-4">
        <h2 className="text-lg">Health</h2>
        <p className="text-sm text-ink-muted">Used only to shape suggestions. Larder does not give medical advice.</p>
        <ChipList
          label="Conditions"
          values={(v("medical_conditions") ?? []).map((c) => c.name)}
          onChange={(names) => set("medical_conditions", names.map((name) => ({ name, notes: null })))}
          placeholder="e.g. type 2 diabetes"
        />
        <Textarea label="Notes" name="medical_notes" value={v("medical_notes") ?? ""} onChange={(e) => set("medical_notes", e.target.value || null)} maxLength={500} />
        <Button variant="danger" size="sm" onClick={clearHealth} loading={update.isPending}>
          Clear health data
        </Button>
      </section>

      <div className="mt-8 flex items-center gap-3 border-t border-line pt-6">
        <Button onClick={save} disabled={!dirty} loading={update.isPending}>
          Save changes
        </Button>
        {dirty && (
          <Button variant="ghost" onClick={() => setPatch({})}>
            Discard
          </Button>
        )}
      </div>

      <section className="mt-8 border-t border-line pt-6">
        <h2 className="text-lg">Appearance</h2>
        <div className="mt-3">
          <Segmented
            label="Theme"
            value={theme}
            onChange={(t: ThemeMode) => setTheme(t)}
            options={[
              { value: "system", label: "System" },
              { value: "light", label: "Light" },
              { value: "dark", label: "Dark" },
            ]}
          />
        </div>
      </section>

      <section className="mt-8 border-t border-line pt-6">
        <Button variant="secondary" onClick={signOut}>
          Sign out
        </Button>
      </section>
    </div>
  );
}

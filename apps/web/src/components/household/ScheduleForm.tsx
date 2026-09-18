"use client";

import type { HouseholdOut, HouseholdPatch } from "@larder/api-client";
import { useState, type FormEvent } from "react";
import { Button, Input, Select } from "@/components/ui";

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

function timezones(): string[] {
  try {
    return (Intl as unknown as { supportedValuesOf?: (k: string) => string[] }).supportedValuesOf?.("timeZone") ?? [];
  } catch {
    return [];
  }
}

export function ScheduleForm({ household, onSave, busy }: { household: HouseholdOut; onSave: (patch: HouseholdPatch) => void; busy?: boolean }) {
  const [day, setDay] = useState(String(household.weekly_refresh_day));
  const [weekly, setWeekly] = useState(household.weekly_refresh_time.slice(0, 5));
  const [daily, setDaily] = useState(household.daily_refresh_time.slice(0, 5));
  const [tz, setTz] = useState(household.timezone);
  const zones = timezones();
  const submit = (e: FormEvent) => {
    e.preventDefault();
    onSave({ weekly_refresh_day: Number(day), weekly_refresh_time: `${weekly}:00`, daily_refresh_time: `${daily}:00`, timezone: tz });
  };
  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <Select label="Plan the week on" name="weekly_day" value={day} onChange={(e) => setDay(e.target.value)} options={DAYS.map((d, i) => ({ value: String(i), label: d }))} />
        <Input label="At" name="weekly_time" type="time" value={weekly} onChange={(e) => setWeekly(e.target.value)} />
        <Input label="Check the pantry each morning at" name="daily_time" type="time" value={daily} onChange={(e) => setDaily(e.target.value)} />
        {zones.length ? (
          <Select label="Timezone" name="timezone" value={tz} onChange={(e) => setTz(e.target.value)} options={zones.map((z) => ({ value: z, label: z }))} />
        ) : (
          <Input label="Timezone" name="timezone" value={tz} onChange={(e) => setTz(e.target.value)} />
        )}
      </div>
      <Button type="submit" loading={busy}>
        Save schedule
      </Button>
    </form>
  );
}

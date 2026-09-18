"use client";

import { useHousehold, useMeals } from "@larder/api-client";
import Link from "next/link";
import { useState } from "react";
import { MealList } from "@/components/meals/MealList";
import { Button, EmptyState, Input, Segmented, Select, SkeletonList } from "@/components/ui";

export default function MealsPage() {
  const [query, setQuery] = useState("");
  const [mealType, setMealType] = useState("");
  const [source, setSource] = useState<"user" | "generated">("user");
  const household = useHousehold();
  const meals = useMeals({ query: query || undefined, meal_type: mealType || undefined, source });
  const slots = household.data?.slots ?? [];
  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl">Meals</h1>
          <p className="mt-1 text-sm text-ink-muted">Your household&apos;s recipes. The planner reaches for these first.</p>
        </div>
        <Link href="/meals/new">
          <Button>Add a meal</Button>
        </Link>
      </div>
      <div className="mt-5 flex flex-wrap items-end gap-3">
        <div className="min-w-48 flex-1">
          <Input name="search" placeholder="Search" aria-label="Search meals" value={query} onChange={(e) => setQuery(e.target.value)} />
        </div>
        <div className="min-w-40">
          <Select name="meal_type" aria-label="Meal type" value={mealType} onChange={(e) => setMealType(e.target.value)} options={[{ value: "", label: "Any slot" }, ...slots.map((s) => ({ value: s.key, label: s.label }))]} />
        </div>
        <Segmented
          label="Source"
          value={source}
          onChange={setSource}
          options={[
            { value: "user", label: "Mine" },
            { value: "generated", label: "Suggested by Larder" },
          ]}
        />
      </div>
      <div className="mt-6">
        {meals.isLoading ? (
          <SkeletonList rows={4} />
        ) : !meals.data?.meals.length ? (
          <EmptyState action={source === "user" ? <Link href="/meals/new"><Button>Add your first meal</Button></Link> : undefined}>
            {source === "user" ? "No meals of your own yet." : "Larder hasn't suggested any meals yet."}
          </EmptyState>
        ) : (
          <MealList meals={meals.data.meals} />
        )}
      </div>
    </div>
  );
}

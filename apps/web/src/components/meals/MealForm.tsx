"use client";

import type { MealCreate } from "@larder/api-client";
import { useState, type FormEvent } from "react";
import { Button, Input, Textarea } from "@/components/ui";

export function parseIngredients(text: string): string[] {
  const seen = new Set<string>();
  return text
    .split(/[\n,]/)
    .map((s) => s.trim())
    .filter((s) => s && !seen.has(s.toLowerCase()) && seen.add(s.toLowerCase()));
}

export function MealForm({ onSubmit, busy, initial }: { onSubmit: (body: MealCreate) => void; busy?: boolean; initial?: Partial<MealCreate> }) {
  const [name, setName] = useState(initial?.name ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [ingredients, setIngredients] = useState((initial?.ingredients ?? []).join("\n"));
  const [instructions, setInstructions] = useState(initial?.instructions ?? "");
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    onSubmit({
      name: name.trim(),
      description: description.trim() || null,
      ingredients: parseIngredients(ingredients),
      instructions: instructions.trim() || null,
    });
  };
  return (
    <form onSubmit={submit} className="space-y-4" data-testid="meal-form">
      <Input label="Name" name="name" required maxLength={80} value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Grandma's rajma" />
      <Input label="Description (optional)" name="description" maxLength={240} value={description} onChange={(e) => setDescription(e.target.value)} />
      <Textarea
        label="Ingredients"
        name="ingredients"
        hint="One per line or comma separated. No quantities needed."
        value={ingredients}
        onChange={(e) => setIngredients(e.target.value)}
        placeholder={"rajma\nonion\ntomato\nginger garlic paste"}
      />
      <Textarea label="How you make it (optional)" name="instructions" maxLength={4000} value={instructions} onChange={(e) => setInstructions(e.target.value)} />
      <Button type="submit" loading={busy} disabled={!name.trim()}>
        Save meal
      </Button>
    </form>
  );
}

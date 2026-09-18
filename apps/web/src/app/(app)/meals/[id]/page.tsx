"use client";

import { useDeleteMeal, useEnrichMeal, useFeedback, useMeal, useUpdateMeal, type MealOut } from "@larder/api-client";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { IngredientList } from "@/components/meals/IngredientList";
import { MealForm } from "@/components/meals/MealForm";
import { Banner, Button, Chip, Sheet, SkeletonList } from "@/components/ui";
import { titleCase } from "@/lib/format";

export default function MealDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const meal = useMeal(id);
  const update = useUpdateMeal();
  const remove = useDeleteMeal();
  const enrich = useEnrichMeal();
  const feedback = useFeedback();
  const [editing, setEditing] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (meal.isLoading) return <SkeletonList rows={3} />;
  if (!meal.data) return <p className="text-ink-muted">Meal not found.</p>;
  const m: MealOut = meal.data;

  const save = (body: { name: string; description?: string | null; ingredients?: string[] | null; instructions?: string | null }) =>
    update.mutate(
      {
        id: m.id,
        patch: {
          name: body.name,
          description: body.description ?? undefined,
          instructions: body.instructions ?? undefined,
          ingredients: (body.ingredients ?? []).map((name) => {
            const existing = m.ingredients.find((i) => i.name === name);
            return {
              name,
              category: existing?.category ?? "other",
              is_staple: existing?.is_staple ?? false,
              is_optional: existing?.is_optional ?? false,
            };
          }),
        },
      },
      { onSuccess: () => setEditing(false), onError: (e) => setError(e.message) },
    );

  return (
    <div className="mx-auto max-w-xl">
      <p className="text-xs font-medium uppercase tracking-wide text-ink-muted">{m.source === "user" ? "Your meal" : "Suggested by Larder"}</p>
      <h1 className="mt-1 text-2xl">{m.name}</h1>
      {m.description && <p className="mt-2 text-ink-muted">{m.description}</p>}
      <div className="mt-3 flex flex-wrap gap-2">
        {m.cuisine && <Chip disabled>{titleCase(m.cuisine)}</Chip>}
        {m.prep_minutes && <Chip disabled>{m.prep_minutes} min</Chip>}
        {m.meal_types.map((t) => (
          <Chip key={t} disabled>
            {titleCase(t)}
          </Chip>
        ))}
        {m.diet_tags.map((t) => (
          <Chip key={t} disabled selected>
            {titleCase(t)}
          </Chip>
        ))}
        {m.allergens.map((t) => (
          <Chip key={t} disabled className="text-warning">
            contains {titleCase(t)}
          </Chip>
        ))}
      </div>
      {m.enrichment_status === "failed" && (
        <div className="mt-4">
          <Banner tone="warning" action={<button className="underline" onClick={() => enrich.mutate(m.id)}>Try again</button>}>
            Couldn&apos;t fill in the details automatically. You can edit them below.
          </Banner>
        </div>
      )}
      {error && <div className="mt-4"><Banner tone="danger" action={<button className="underline" onClick={() => setError(null)}>Dismiss</button>}>{error}</Banner></div>}

      {editing ? (
        <div className="mt-6 rounded-md border border-line bg-surface p-4">
          <MealForm
            busy={update.isPending}
            initial={{ name: m.name, description: m.description, ingredients: m.ingredients.map((i) => i.name), instructions: m.instructions }}
            onSubmit={save}
          />
          <Button variant="ghost" className="mt-3" onClick={() => setEditing(false)}>
            Cancel
          </Button>
        </div>
      ) : (
        <>
          <section className="mt-6">
            <h2 className="text-lg">Ingredients</h2>
            <div className="mt-2">
              <IngredientList ingredients={m.ingredients} />
            </div>
          </section>
          {m.instructions && (
            <section className="mt-6">
              <h2 className="text-lg">How to make it</h2>
              <p className="mt-2 whitespace-pre-line text-ink">{m.instructions}</p>
            </section>
          )}
          <section className="mt-6 flex flex-wrap items-center gap-3 border-t border-line pt-4 text-sm">
            <span className="text-ink-muted">
              {m.feedback.up} likes · {m.feedback.down} dislikes · cooked {m.feedback.cooked} times
            </span>
            <Button size="sm" variant="secondary" onClick={() => feedback.mutate({ mealId: m.id, kind: "cooked" })}>
              Cooked it
            </Button>
          </section>
          <div className="mt-6 flex gap-3">
            {m.source === "user" && (
              <Button variant="secondary" onClick={() => setEditing(true)}>
                Edit
              </Button>
            )}
            <Button variant="danger" onClick={() => setConfirmDelete(true)}>
              Delete
            </Button>
          </div>
        </>
      )}

      <Sheet open={confirmDelete} onClose={() => setConfirmDelete(false)} title="Delete this meal?">
        <p className="text-sm text-ink-muted">If it is in your current plan, Larder will refuse so the plan stays intact.</p>
        <div className="mt-5 flex gap-3">
          <Button
            variant="danger"
            loading={remove.isPending}
            onClick={() =>
              remove.mutate(m.id, {
                onSuccess: () => router.replace("/meals"),
                onError: (e) => {
                  setConfirmDelete(false);
                  setError(e.message);
                },
              })
            }
          >
            Delete
          </Button>
          <Button variant="ghost" onClick={() => setConfirmDelete(false)}>
            Keep
          </Button>
        </div>
      </Sheet>
    </div>
  );
}

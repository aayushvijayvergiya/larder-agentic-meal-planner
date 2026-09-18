"use client";

import { useCreateMeal } from "@larder/api-client";
import { useRouter } from "next/navigation";
import { MealForm } from "@/components/meals/MealForm";
import { Banner } from "@/components/ui";

export default function NewMealPage() {
  const router = useRouter();
  const create = useCreateMeal();
  return (
    <div className="mx-auto max-w-xl">
      <h1 className="text-2xl">Add a meal</h1>
      <p className="mt-1 text-sm text-ink-muted">Larder fills in ingredients, tags and allergens; you can correct anything after.</p>
      <div className="mt-6">
        {create.error && <div className="mb-4"><Banner tone="danger">{create.error.message}</Banner></div>}
        <MealForm busy={create.isPending} onSubmit={(body) => create.mutate(body, { onSuccess: (m) => router.replace(`/meals/${m.id}`) })} />
      </div>
    </div>
  );
}

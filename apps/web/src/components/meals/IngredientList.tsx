import type { MealOut } from "@larder/api-client";

export function IngredientList({ ingredients }: { ingredients: MealOut["ingredients"] }) {
  if (!ingredients.length) return <p className="text-sm text-ink-muted">No ingredients recorded yet.</p>;
  return (
    <ul className="divide-y divide-line text-sm">
      {ingredients.map((i) => (
        <li key={i.name} className="flex items-center justify-between py-1.5">
          <span className={i.is_optional ? "text-ink-muted" : "text-ink"}>
            {i.name}
            {i.is_optional ? " (optional)" : ""}
          </span>
          <span className="text-xs text-ink-muted">{i.is_staple ? "staple" : i.category}</span>
        </li>
      ))}
    </ul>
  );
}

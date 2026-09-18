"""Deterministic fallback so a plan always completes (LLD §8.2)."""

from collections import Counter
from datetime import date

from larder.agents.planner.state import (
    EntryDraft,
    IngredientDraft,
    MealCandidate,
    NewMealDraft,
    PlanDraft,
    PlanningContext,
)
from larder.agents.planner.validate import MAX_REPEATS, ValidationResult
from larder.services.normalize import normalize_name

# Allergen-free, vegan and jain-safe (no root vegetables) so they satisfy every diet type in the vocabulary.
_VARIANTS: list[list[tuple[str, str]]] = [
    [("rice", "grains"), ("toor dal", "pulses"), ("tomato", "vegetables")],
    [("poha", "grains"), ("green peas", "vegetables"), ("tomato", "vegetables")],
    [("rice", "grains"), ("moong dal", "pulses"), ("spinach", "vegetables")],
    [("millet", "grains"), ("tomato", "vegetables"), ("cucumber", "vegetables")],
    [("green peas", "vegetables"), ("capsicum", "vegetables"), ("tomato", "vegetables")],
]

FALLBACK_REASON = "A simple fallback that fits everyone's constraints."


def SIMPLE_BOWL(slot_key: str, variant: int = 0) -> NewMealDraft:  # noqa: N802  (name fixed by the plan)
    items = _VARIANTS[variant % len(_VARIANTS)]
    suffix = "" if variant == 0 else f" {variant + 1}"
    return NewMealDraft(
        name=f"Simple {slot_key} bowl{suffix}",
        description="A quick one-pot bowl from pantry basics.",
        cuisine="home",
        meal_types=[slot_key],
        diet_tags=["vegetarian", "vegan", "jain"],
        allergens=[],
        prep_minutes=25,
        ingredients=[IngredientDraft(name=n, category=c) for n, c in items]
        + [IngredientDraft(name="salt", category="spices", is_staple=True)],
    )


def _reason_for(candidate: MealCandidate) -> str:
    if candidate.covered:
        names = ", ".join(candidate.covered[:3])
        return f"Uses the {names} you already have."
    return "A household favourite that fits everyone's constraints."


def fallback_fill(
    draft: PlanDraft | None, result: ValidationResult, ctx: PlanningContext, shortlist: list[MealCandidate]
) -> PlanDraft:
    slot_order = {s.key: s.order for s in ctx.slots}
    kept: dict[tuple[date, str], EntryDraft] = {}
    counts: Counter[str] = Counter(str(f.meal_id) for f in ctx.fixed_entries)
    for idx, e in enumerate(draft.entries if draft else []):
        pair = (e.date, e.slot_key)
        if idx in result.bad_entry_indexes or pair not in set(ctx.requested) or pair in kept:
            continue
        kept[pair] = e
        counts[str(e.existing_meal_id) if e.existing_meal_id else "new:" + normalize_name(e.new_meal.name)] += 1  # type: ignore[union-attr]

    cursor = 0
    variant_by_slot: dict[str, int] = {}
    for pair in sorted(ctx.requested, key=lambda p: (p[0], slot_order.get(p[1], 99))):
        if pair in kept:
            continue
        chosen: EntryDraft | None = None
        for _ in range(len(shortlist)):
            cand = shortlist[cursor % len(shortlist)]
            cursor += 1
            key = str(cand.meal.id)
            if counts[key] < MAX_REPEATS:
                counts[key] += 1
                chosen = EntryDraft(
                    date=pair[0], slot_key=pair[1], existing_meal_id=cand.meal.id, reason=_reason_for(cand)
                )
                break
        if chosen is None:
            variant = variant_by_slot.get(pair[1], 0)
            while True:
                bowl = SIMPLE_BOWL(pair[1], variant)
                key = "new:" + normalize_name(bowl.name)
                if counts[key] < MAX_REPEATS:
                    break
                variant += 1
            counts[key] += 1
            variant_by_slot[pair[1]] = variant
            chosen = EntryDraft(date=pair[0], slot_key=pair[1], new_meal=bowl, reason=FALLBACK_REASON)
        kept[pair] = chosen

    entries = [kept[p] for p in sorted(kept, key=lambda p: (p[0], slot_order.get(p[1], 99)))]
    return PlanDraft(entries=entries)

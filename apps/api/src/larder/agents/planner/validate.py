"""Hard and soft plan validation (LLD §8.2). Hard rules are enforced here, never only in prompts."""

from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from uuid import UUID

from larder.agents.planner.medical_rules import rules_for
from larder.agents.planner.state import (
    EntryDraft,
    IngredientCtx,
    MealCandidate,
    MealCtx,
    PlanDraft,
    PlanningContext,
)
from larder.agents.planner.vocab import diet_ok, infer_allergens
from larder.services import coverage as coverage_svc
from larder.services.normalize import normalize_name, tokens

MAX_REPEATS = 2


@dataclass
class ValidationResult:
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    bad_entry_indexes: set[int] = field(default_factory=set)

    @property
    def ok(self) -> bool:
        return not self.violations


@dataclass
class ResolvedMeal:
    key: str  # meal id or normalised new-meal name
    name: str
    allergens: set[str]
    diet_tags: list[str]
    ingredients: list[IngredientCtx]
    prep_minutes: int | None
    cuisine: str | None
    meal_types: list[str]


def resolve_entry(entry: EntryDraft, library: dict[UUID, MealCtx]) -> ResolvedMeal | None:
    if entry.existing_meal_id is not None:
        meal = library.get(entry.existing_meal_id)
        if meal is None:
            return None
        return ResolvedMeal(
            key=str(meal.id),
            name=meal.name,
            allergens=set(meal.allergens) | set(infer_allergens([i.name for i in meal.ingredients])),
            diet_tags=list(meal.diet_tags),
            ingredients=list(meal.ingredients),
            prep_minutes=meal.prep_minutes,
            cuisine=meal.cuisine,
            meal_types=list(meal.meal_types),
        )
    nm = entry.new_meal
    assert nm is not None
    ingredients = [
        IngredientCtx(
            name=i.name,
            normalized_name=normalize_name(i.name),
            category=i.category,
            is_staple=i.is_staple,
            is_optional=i.is_optional,
        )
        for i in nm.ingredients
    ]
    return ResolvedMeal(
        key="new:" + normalize_name(nm.name),
        name=nm.name,
        allergens=set(nm.allergens) | set(infer_allergens([i.name for i in ingredients])),
        diet_tags=list(nm.diet_tags),
        ingredients=ingredients,
        prep_minutes=nm.prep_minutes,
        cuisine=nm.cuisine,
        meal_types=list(nm.meal_types),
    )


def _where(rm: ResolvedMeal, e: EntryDraft) -> str:
    return f"{rm.name} ({e.date} {e.slot_key})"


def validate(draft: PlanDraft, ctx: PlanningContext, shortlist: list[MealCandidate]) -> ValidationResult:
    res = ValidationResult()
    library = {m.id: m for m in ctx.library}
    member_ids = {m.id for m in ctx.members}
    requested = set(ctx.requested)
    slot_keys = {s.key for s in ctx.slots}

    # --- slot completeness ---------------------------------------------------------
    seen_pairs: dict[tuple[date, str], int] = {}
    for idx, e in enumerate(draft.entries):
        pair = (e.date, e.slot_key)
        if pair not in requested:
            res.violations.append(f"entry {idx} ({e.date} {e.slot_key}) was not requested")
            res.bad_entry_indexes.add(idx)
            continue
        if pair in seen_pairs:
            res.violations.append(f"duplicate entry for {e.date} {e.slot_key}")
            res.bad_entry_indexes.add(idx)
            continue
        seen_pairs[pair] = idx
    for pair in sorted(requested):
        if pair not in seen_pairs:
            res.violations.append(f"missing entry for {pair[0]} {pair[1]}")

    # --- per-entry hard rules ------------------------------------------------------
    resolved: dict[int, ResolvedMeal] = {}
    for idx, e in enumerate(draft.entries):
        if idx in res.bad_entry_indexes:
            continue
        rm = resolve_entry(e, library)
        if rm is None:
            res.violations.append(f"entry {idx} references unknown meal id {e.existing_meal_id}")
            res.bad_entry_indexes.add(idx)
            continue
        resolved[idx] = rm
        for m in ctx.members:
            hit = rm.allergens & set(m.allergens)
            if hit:
                res.violations.append(
                    f"{_where(rm, e)} contains {', '.join(sorted(hit))}, an allergen for {m.display_name}"
                )
                res.bad_entry_indexes.add(idx)
            if not diet_ok(m.diet_type, rm.diet_tags):
                res.violations.append(f"{_where(rm, e)} does not fit {m.display_name}'s {m.diet_type} diet")
                res.bad_entry_indexes.add(idx)
            medical = rules_for(m.medical_conditions)
            hit = rm.allergens & medical.hard_allergens
            if hit:
                res.violations.append(
                    f"{_where(rm, e)} contains {', '.join(sorted(hit))}, which {m.display_name} must avoid"
                )
                res.bad_entry_indexes.add(idx)
        for v in e.variations:
            if v.member_id not in member_ids:
                res.violations.append(f"entry {idx} has a variation for an unknown member")
                res.bad_entry_indexes.add(idx)
        if len(ctx.members) == 1 and e.variations:
            res.violations.append(f"entry {idx} has per-member variations in a single-member plan")
            res.bad_entry_indexes.add(idx)

    # --- repetition ---------------------------------------------------------------
    counts: Counter[str] = Counter(str(f.meal_id) for f in ctx.fixed_entries)
    for idx in sorted(resolved):
        key = resolved[idx].key
        counts[key] += 1
        if counts[key] > MAX_REPEATS:
            res.violations.append(f"{resolved[idx].name} appears more than twice in the plan window")
            res.bad_entry_indexes.add(idx)

    # --- soft rules ---------------------------------------------------------------
    pantry = ctx.pantry_norms
    min_prep = min((m.max_prep_minutes for m in ctx.members if m.max_prep_minutes), default=None)
    low_coverage = 0
    by_date: dict[date, list[str | None]] = {}
    for idx, e in enumerate(draft.entries):
        rm = resolved.get(idx)
        if rm is None:
            continue
        ing_tokens: set[str] = set()
        for i in rm.ingredients:
            ing_tokens |= tokens(i.name)
        for m in ctx.members:
            disliked = {d for d in m.dislikes if tokens(d) and tokens(d) <= ing_tokens}
            if disliked:
                res.warnings.append(
                    f"{_where(rm, e)} uses {', '.join(sorted(disliked))}, which {m.display_name} dislikes"
                )
            avoid = rules_for(m.medical_conditions).avoid_tokens
            hit = {a for a in avoid if tokens(a) and tokens(a) <= ing_tokens}
            if hit:
                res.warnings.append(f"{_where(rm, e)} uses {', '.join(sorted(hit))}, best avoided for {m.display_name}")
        if min_prep and rm.prep_minutes and rm.prep_minutes > min_prep:
            res.warnings.append(f"{_where(rm, e)} takes {rm.prep_minutes} min, over the {min_prep} min limit")
        if rm.meal_types and e.slot_key not in rm.meal_types and "any" not in rm.meal_types and e.slot_key in slot_keys:
            res.warnings.append(f"{rm.name} is not tagged for the {e.slot_key} slot")
        if coverage_svc.compute(rm.ingredients, pantry).coverage < 0.5:
            low_coverage += 1
        by_date.setdefault(e.date, []).append(rm.cuisine)
    if resolved and low_coverage / len(resolved) > 0.3:
        res.warnings.append(
            f"{low_coverage} of {len(resolved)} meals use less than half their ingredients from the pantry"
        )
    days = sorted(by_date)
    for i in range(2, len(days)):
        cuisines = [set(c for c in by_date[d] if c) for d in days[i - 2 : i + 1]]
        common = set.intersection(*cuisines) if all(cuisines) else set()
        if common:
            res.warnings.append(f"{', '.join(sorted(common))} appears three days in a row ({days[i - 2]} to {days[i]})")
    return res

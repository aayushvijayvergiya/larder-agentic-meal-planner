"""Deterministic shortlist of library meals (LLD §8.2)."""

from datetime import date

from larder.agents.planner.medical_rules import rules_for
from larder.agents.planner.state import MealCandidate, MealCtx, MemberCtx, PlanningContext
from larder.agents.planner.vocab import diet_ok, infer_allergens
from larder.services import coverage as coverage_svc

SHORTLIST_SIZE = 40
MIN_COVERAGE = 0.5


def meal_allergens(meal: MealCtx) -> set[str]:
    return set(meal.allergens) | set(infer_allergens([i.name for i in meal.ingredients]))


def hard_conflict(meal: MealCtx, members: list[MemberCtx]) -> str | None:
    allergens = meal_allergens(meal)
    for m in members:
        hit = allergens & set(m.allergens)
        if hit:
            return f"{meal.name} contains {', '.join(sorted(hit))} which {m.display_name} is allergic to"
        if not diet_ok(m.diet_type, meal.diet_tags):
            return f"{meal.name} does not fit {m.display_name}'s {m.diet_type} diet"
        medical = rules_for(m.medical_conditions)
        hit = allergens & medical.hard_allergens
        if hit:
            return f"{meal.name} contains {', '.join(sorted(hit))} which {m.display_name} must avoid"
    return None


def feedback_norm(meal: MealCtx) -> float:
    raw = (meal.feedback_up - meal.feedback_down) / (meal.feedback_up + meal.feedback_down + 1)
    return (raw + 1) / 2


def recency(meal: MealCtx, start_date: date) -> float:
    if meal.last_used_date is None:
        return 1.0
    days = (start_date - meal.last_used_date).days
    if days < 7:
        return 0.0
    if days < 14:
        return 0.5
    return 1.0


def build(ctx: PlanningContext, start_date: date) -> list[MealCandidate]:
    pantry = ctx.pantry_norms
    out: list[MealCandidate] = []
    for meal in ctx.library:
        if hard_conflict(meal, ctx.members):
            continue
        cov = coverage_svc.compute(meal.ingredients, pantry)
        if cov.coverage < MIN_COVERAGE and meal.source != "user":
            continue
        score = cov.coverage * 0.6 + feedback_norm(meal) * 0.25 + recency(meal, start_date) * 0.15
        out.append(
            MealCandidate(
                meal=meal, coverage=cov.coverage, score=round(score, 4), covered=cov.covered, missing=cov.missing
            )
        )
    out.sort(key=lambda c: (-c.score, c.meal.name))
    return out[:SHORTLIST_SIZE]

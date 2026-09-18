"""Pantry coverage of a meal's ingredients (LLD §7.2)."""

from dataclasses import dataclass, field

from larder.agents.planner.state import IngredientCtx
from larder.services.normalize import ingredient_matches_pantry


@dataclass
class CoverageResult:
    coverage: float
    covered: list[str] = field(default_factory=list)  # matched pantry item names (normalised)
    missing: list[IngredientCtx] = field(default_factory=list)  # non-staple ingredients not on hand, optional flagged


def compute(ingredients: list[IngredientCtx], pantry_norms: set[str]) -> CoverageResult:
    countable = [i for i in ingredients if not i.is_staple]
    if not countable:
        return CoverageResult(coverage=1.0)
    covered: list[str] = []
    missing: list[IngredientCtx] = []
    for ing in countable:
        hit = ingredient_matches_pantry(ing.normalized_name, pantry_norms)
        if hit:
            if hit not in covered:
                covered.append(hit)
        else:
            missing.append(ing)
    return CoverageResult(coverage=(len(countable) - len(missing)) / len(countable), covered=covered, missing=missing)

"""Meal enrichment: one structured call (LLD §8.3)."""

from larder.agents.categorize.keyword_map import CATEGORY_ORDER, keyword_category
from larder.agents.enrichment.prompts import SYSTEM_PROMPT
from larder.agents.enrichment.schemas import IngredientDraft, MealEnrichment
from larder.agents.planner.vocab import ALLERGENS, DIET_TAGS, infer_allergens, is_staple
from larder.llm.base import LLM, build_context_block
from larder.services.normalize import normalize_name, slugify


def _dedupe_ingredients(drafts: list[IngredientDraft]) -> list[IngredientDraft]:
    seen: set[str] = set()
    out: list[IngredientDraft] = []
    for d in drafts:
        norm = normalize_name(d.name)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        category = d.category if d.category != "other" else (keyword_category(norm) or "other")
        out.append(
            IngredientDraft(
                name=d.name.strip(),
                category=category,
                is_staple=d.is_staple or is_staple(d.name),
                is_optional=d.is_optional,
            )
        )
    return out


def clean_enrichment(
    raw: MealEnrichment, *, user_ingredients: list[str] | None, slot_keys: list[str]
) -> MealEnrichment:
    """Apply the vocabulary rules regardless of what the model returned."""
    ingredients = _dedupe_ingredients(raw.ingredients)
    present = {normalize_name(i.name) for i in ingredients}
    for name in user_ingredients or []:
        norm = normalize_name(name)
        if norm and norm not in present:
            ingredients.append(
                IngredientDraft(
                    name=name.strip(), category=keyword_category(norm) or "other", is_staple=is_staple(name)
                )
            )
            present.add(norm)
    allowed_types = set(slot_keys) | {"any"}
    meal_types = [t for t in dict.fromkeys(raw.meal_types) if t in allowed_types] or ["any"]
    diet_tags = [t for t in dict.fromkeys(raw.diet_tags) if t in DIET_TAGS]
    allergens = [a for a in dict.fromkeys(raw.allergens) if a in ALLERGENS]
    for inferred in infer_allergens([i.name for i in ingredients]):
        if inferred not in allergens:
            allergens.append(inferred)
    return MealEnrichment(
        description=raw.description.strip()[:240],
        cuisine=slugify(raw.cuisine) or "home",
        meal_types=meal_types,
        diet_tags=diet_tags,
        allergens=allergens,
        prep_minutes=raw.prep_minutes,
        ingredients=ingredients[:25],
    )


async def enrich_meal(
    llm: LLM,
    *,
    name: str,
    description: str | None,
    ingredients: list[str] | None,
    instructions: str | None,
    slot_keys: list[str],
) -> MealEnrichment:
    context = {
        "name": name,
        "description": description,
        "ingredients": ingredients or [],
        "instructions": (instructions or "")[:1500],
        "slot_keys": slot_keys,
        "allowed_diet_tags": DIET_TAGS,
        "allowed_allergens": ALLERGENS,
        "categories": CATEGORY_ORDER,
    }
    user = f"Enrich the dish '{name}'.\n" + build_context_block(context)
    raw = await llm.complete_structured(system=SYSTEM_PROMPT, user=user, schema=MealEnrichment, temperature=0)
    return clean_enrichment(raw, user_ingredients=ingredients, slot_keys=slot_keys)

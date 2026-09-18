"""Default deterministic handlers for FakeLLM, keyed by structured-output schema name (LLD §5.3).

Each agent registers its schema handler here so a fresh clone with LLM_PROVIDER=fake completes every flow.
Handlers receive the parsed <context> dict and the schema class (so this module never imports agent schemas)
and must return a valid instance.
"""

from collections.abc import Callable

from pydantic import BaseModel

Handler = Callable[[dict, type[BaseModel]], BaseModel]

DEFAULT_HANDLERS: dict[str, Handler] = {}


def handler(schema_name: str) -> Callable[[Handler], Handler]:
    def _register(fn: Handler) -> Handler:
        DEFAULT_HANDLERS[schema_name] = fn
        return fn

    return _register


def register_default_handlers(fake) -> None:
    for name, fn in DEFAULT_HANDLERS.items():
        fake.register_handler(name, fn)


@handler("CategoryAssignments")
def _category_assignments(ctx: dict, schema: type[BaseModel]) -> BaseModel:
    # The static keyword map has already handled everything it recognises; the fake knows nothing more.
    return schema(assignments=[{"name": n, "category": "other"} for n in ctx.get("names", [])])


@handler("MealEnrichment")
def _meal_enrichment(ctx: dict, schema: type[BaseModel]) -> BaseModel:
    from larder.agents.categorize.keyword_map import keyword_category
    from larder.agents.planner.vocab import infer_allergens, infer_diet_tags, is_staple
    from larder.services.normalize import normalize_name

    names = [n for n in ctx.get("ingredients", []) if n and n.strip()]
    if len(names) < 2:
        names += [n for n in ("onion", "salt") if n not in names]
    ingredients = [
        {
            "name": n,
            "category": keyword_category(normalize_name(n)) or "other",
            "is_staple": is_staple(n),
            "is_optional": False,
        }
        for n in names
    ]
    slot_keys = [k for k in ctx.get("slot_keys", []) if k != "breakfast"] or ctx.get("slot_keys", []) or ["any"]
    return schema(
        description=f"{ctx.get('name', 'This dish')}, made from what you have.",
        cuisine="home",
        meal_types=[slot_keys[0]],
        diet_tags=infer_diet_tags(names),
        allergens=infer_allergens(names),
        prep_minutes=30,
        ingredients=ingredients,
    )

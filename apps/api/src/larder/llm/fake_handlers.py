"""Default deterministic handlers for FakeLLM, keyed by structured-output schema name (LLD §5.3).

Each agent registers its schema handler here so a fresh clone with LLM_PROVIDER=fake completes every flow.
Handlers receive the parsed <context> dict and the schema class (so this module never imports agent schemas)
and must return a valid instance.
"""

from collections.abc import Callable

from pydantic import BaseModel

Handler = Callable[[dict, type[BaseModel]], BaseModel]

DEFAULT_HANDLERS: dict[str, Handler] = {}
TEXT_HANDLERS: dict[str, Callable[[dict], str]] = {}


def handler(schema_name: str) -> Callable[[Handler], Handler]:
    def _register(fn: Handler) -> Handler:
        DEFAULT_HANDLERS[schema_name] = fn
        return fn

    return _register


def text_handler(task: str) -> Callable[[Callable[[dict], str]], Callable[[dict], str]]:
    def _register(fn: Callable[[dict], str]) -> Callable[[dict], str]:
        TEXT_HANDLERS[task] = fn
        return fn

    return _register


def register_default_handlers(fake) -> None:
    for name, fn in DEFAULT_HANDLERS.items():
        fake.register_handler(name, fn)
    for task, fn in TEXT_HANDLERS.items():
        fake.register_text_handler(task, fn)


@text_handler("onboarding_question")
def _onboarding_question(ctx: dict) -> str:
    q = str(ctx.get("default_question") or "Tell me more.")
    name = (ctx.get("draft_so_far") or {}).get("display_name")
    if ctx.get("error"):
        return f"Sorry, {ctx['error']}. {q}"
    return f"{name}, {q[0].lower() + q[1:]}" if name and ctx.get("field") != "display_name" else q


@handler("ParsedFieldAnswer")
def _parsed_field_answer(ctx: dict, schema: type[BaseModel]) -> BaseModel:
    # Unscripted free-text answers are not understood by the fake, so the question is re-asked.
    return schema(value=None, confidence=0.0)


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


@handler("PlanDraft")
def _plan_draft(ctx: dict, schema: type[BaseModel]) -> BaseModel:
    """Fills every requested (date, slot) round-robin from the shortlist (max two uses each), then with
    allergen-free simple bowls, so the fake always yields a plan the validator accepts."""
    from collections import Counter

    from larder.agents.planner.fallback import FALLBACK_REASON, SIMPLE_BOWL

    requested = [tuple(p) for p in ctx.get("requested", [])]
    shortlist = ctx.get("shortlist", [])
    counts: Counter[str] = Counter()
    for f in ctx.get("fixed_entries", []):
        counts[f.get("meal_name", "")] += 1
    entries = []
    cursor = 0
    variant_by_slot: dict[str, int] = {}
    for d, slot in requested:
        chosen = None
        for _ in range(len(shortlist)):
            cand = shortlist[cursor % len(shortlist)]
            cursor += 1
            if counts[cand["name"]] < 2:
                counts[cand["name"]] += 1
                covered = ", ".join(cand.get("covered", [])[:3])
                chosen = {
                    "date": d,
                    "slot_key": slot,
                    "existing_meal_id": cand["existing_meal_id"],
                    "reason": f"Uses the {covered} you already have." if covered else "A household favourite.",
                }
                break
        if chosen is None:
            variant = variant_by_slot.get(slot, 0)
            while counts[SIMPLE_BOWL(slot, variant).name] >= 2:
                variant += 1
            bowl = SIMPLE_BOWL(slot, variant)
            counts[bowl.name] += 1
            variant_by_slot[slot] = variant
            chosen = {"date": d, "slot_key": slot, "new_meal": bowl.model_dump(), "reason": FALLBACK_REASON}
        entries.append(chosen)
    return schema(entries=entries)

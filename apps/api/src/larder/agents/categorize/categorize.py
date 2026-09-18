"""Pantry categoriser: static map first, one batched LLM call for the rest (LLD §8.4)."""

import logging

from larder.agents.categorize.keyword_map import CATEGORY_ORDER, keyword_category
from larder.agents.categorize.schemas import CategoryAssignments
from larder.llm.base import LLM, LLMError, build_context_block
from larder.services.normalize import normalize_name

log = logging.getLogger("larder.categorize")

SYSTEM_PROMPT = (
    "You classify kitchen items into pantry categories for a home-cooking app. "
    "For every name in the context return exactly one category from the allowed list. "
    "Use 'other' only when nothing else fits. Return the names exactly as given."
)


async def categorize(llm: LLM, names: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    unknown: list[str] = []
    for name in names:
        hit = keyword_category(normalize_name(name))
        if hit:
            result[name] = hit
        else:
            unknown.append(name)
    if not unknown:
        return result

    user = "Classify these kitchen items.\n" + build_context_block({"names": unknown, "categories": CATEGORY_ORDER})
    try:
        out = await llm.complete_structured(system=SYSTEM_PROMPT, user=user, schema=CategoryAssignments, temperature=0)
        assigned = {a.name: a.category for a in out.assignments}
        lowered = {k.lower(): v for k, v in assigned.items()}
        for name in unknown:
            result[name] = assigned.get(name) or lowered.get(name.lower()) or "other"
    except LLMError as exc:
        log.warning("categoriser llm failed, defaulting to other: %s", exc)
        for name in unknown:
            result[name] = "other"
    return result

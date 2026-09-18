"""Planner agent graph (LLD §8.2).

START -> load_context -> shortlist -> draft_plan -> validate --ok--> persist -> END
                                          ^              |--violations, attempts < 2--> repair --> validate
                                                         '--violations, attempts == 2--> fallback_fill -> persist -> END
"""

import logging
from collections import defaultdict
from datetime import datetime
from typing import Any
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from larder.agents.planner import fallback as fallback_mod
from larder.agents.planner import shortlist as shortlist_mod
from larder.agents.planner.context import load_context
from larder.agents.planner.errors import PlannerError
from larder.agents.planner.medical_rules import rules_for
from larder.agents.planner.persist import persist
from larder.agents.planner.prompts import REPAIR_SUFFIX, SYSTEM_DRAFT
from larder.agents.planner.state import MealCandidate, PlanDraft, PlannerInput, PlannerState, PlanningContext
from larder.agents.planner.validate import validate
from larder.db.models import PlanJob
from larder.llm.base import LLM, LLMError, build_context_block

log = logging.getLogger("larder.planner")

MAX_REPAIRS = 2
SOFT_RULES = [
    "avoid ingredients a member dislikes",
    "keep prep time within each member's max_prep_minutes",
    "at least 70% of meals should use most of their ingredients from the pantry",
    "do not serve the same cuisine three days in a row",
    "tag meals for the slot they fill",
]


def _cfg(config: RunnableConfig, key: str) -> Any:
    return config["configurable"][key]


def _member_brief(m) -> dict:
    rules = rules_for(m.medical_conditions)
    return {
        "id": str(m.id),
        "name": m.display_name,
        "diet_type": m.diet_type,
        "allergens": m.allergens,
        "dislikes": m.dislikes,
        "likes": m.likes,
        "cuisines": m.cuisines,
        "max_prep_minutes": m.max_prep_minutes,
        "goals": m.goals,
        "medical": [c.get("name") for c in m.medical_conditions if isinstance(c, dict)],
        "medical_rules": rules.notes
        + (["avoid: " + ", ".join(sorted(rules.avoid_tokens))] if rules.avoid_tokens else []),
        "medical_notes": (m.medical_notes or "")[:500] or None,
    }


def prompt_context(inp: PlannerInput, ctx: PlanningContext, shortlist: list[MealCandidate]) -> dict:
    pantry: dict[str, list[str]] = defaultdict(list)
    for p in ctx.pantry:
        if p.is_available:
            pantry[p.category].append(p.name)
    recent = {m.id: m.name for m in ctx.library}
    return {
        "task": "planner_draft",
        "mode": inp.mode,
        "scope": inp.scope,
        "requested": [[d.isoformat(), s] for d, s in ctx.requested],
        "slots": [{"key": s.key, "label": s.label} for s in ctx.slots],
        "members": [_member_brief(m) for m in ctx.members],
        "pantry": dict(pantry),
        "shortlist": [
            {
                "existing_meal_id": str(c.meal.id),
                "name": c.meal.name,
                "cuisine": c.meal.cuisine,
                "meal_types": c.meal.meal_types,
                "coverage": round(c.coverage, 2),
                "covered": c.covered[:6],
                "missing": [m.name for m in c.missing][:4],
                "up": c.meal.feedback_up,
                "down": c.meal.feedback_down,
            }
            for c in shortlist
        ],
        "recent_meal_names": [recent[i] for i in ctx.recent_meal_ids if i in recent][:20],
        "fixed_entries": [
            {"date": f.date.isoformat(), "slot_key": f.slot_key, "meal_name": f.meal_name} for f in ctx.fixed_entries
        ],
        "swap_reason": inp.swap_reason,
        "soft_rules": SOFT_RULES,
    }


async def node_load_context(state: PlannerState, config: RunnableConfig) -> dict:
    from larder.services.hashing import compute_inputs_hash

    inp = state["input"]
    session_factory = _cfg(config, "session_factory")
    async with session_factory() as session:
        ctx = await load_context(session, inp)
        inputs_hash = compute_inputs_hash(ctx)
        job = await session.get(PlanJob, inp.job_id)
        if job is not None:
            job.inputs_hash = inputs_hash
            await session.commit()
    return {"context": ctx, "inputs_hash": inputs_hash}


async def node_shortlist(state: PlannerState) -> dict:
    ctx = state["context"]
    assert ctx is not None
    return {"shortlist": shortlist_mod.build(ctx, state["input"].start_date)}


async def _call_draft(llm: LLM, system: str, user: str) -> tuple[PlanDraft | None, str | None]:
    try:
        return await llm.complete_structured(system=system, user=user, schema=PlanDraft, temperature=0.2), None
    except LLMError as exc:
        log.warning("planner draft failed: %s", exc)
        return None, str(exc)


async def node_draft_plan(state: PlannerState, config: RunnableConfig) -> dict:
    inp, ctx = state["input"], state["context"]
    assert ctx is not None
    user = "Plan the requested meals.\n" + build_context_block(prompt_context(inp, ctx, state.get("shortlist", [])))
    draft, err = await _call_draft(_cfg(config, "llm"), SYSTEM_DRAFT, user)
    return {"draft": draft, "llm_error": err}


async def node_validate(state: PlannerState) -> dict:
    ctx = state["context"]
    assert ctx is not None
    draft = state.get("draft")
    if draft is None:
        return {
            "violations": [f"the model returned no usable draft ({state.get('llm_error') or 'unknown error'})"],
            "warnings": [],
            "bad_entry_indexes": [],
        }
    res = validate(draft, ctx, state.get("shortlist", []))
    return {"violations": res.violations, "warnings": res.warnings, "bad_entry_indexes": sorted(res.bad_entry_indexes)}


async def node_repair(state: PlannerState, config: RunnableConfig) -> dict:
    inp, ctx = state["input"], state["context"]
    assert ctx is not None
    context = prompt_context(inp, ctx, state.get("shortlist", []))
    context["task"] = "planner_repair"
    context["previous_draft"] = state["draft"].model_dump(mode="json") if state.get("draft") else None
    context["violations"] = state.get("violations", [])
    context["warnings"] = state.get("warnings", [])[:10]
    system = SYSTEM_DRAFT + REPAIR_SUFFIX.format(
        violations="; ".join(state.get("violations", []))[:1500],
        warnings="; ".join(state.get("warnings", [])[:10])[:800] or "nothing else",
    )
    draft, err = await _call_draft(_cfg(config, "llm"), system, "Repair the draft.\n" + build_context_block(context))
    return {"draft": draft, "llm_error": err, "attempts": state.get("attempts", 0) + 1}


async def node_fallback(state: PlannerState) -> dict:
    ctx = state["context"]
    assert ctx is not None
    shortlist = state.get("shortlist", [])
    draft = state.get("draft")
    res = validate(draft, ctx, shortlist) if draft is not None else None
    from larder.agents.planner.validate import ValidationResult

    filled = fallback_mod.fallback_fill(draft, res or ValidationResult(), ctx, shortlist)
    check = validate(filled, ctx, shortlist)
    if check.violations:
        raise PlannerError("fallback plan still invalid: " + "; ".join(check.violations[:5]))
    return {"draft": filled, "used_fallback": True, "violations": [], "warnings": check.warnings}


async def node_persist(state: PlannerState, config: RunnableConfig) -> dict:
    inp, ctx, draft = state["input"], state["context"], state.get("draft")
    assert ctx is not None and draft is not None
    session_factory = _cfg(config, "session_factory")
    llm: LLM = _cfg(config, "llm")
    async with session_factory() as session:
        written = await persist(
            session,
            inp,
            ctx,
            draft,
            attempts=state.get("attempts", 0),
            used_fallback=bool(state.get("used_fallback")),
            model_name=llm.name,
            inputs_hash=state.get("inputs_hash"),
        )
    return {"persisted": True, "entries_written": written}


def _after_validate(state: PlannerState) -> str:
    if not state.get("violations"):
        return "persist"
    if state.get("attempts", 0) < MAX_REPAIRS:
        return "repair"
    return "fallback_fill"


def build_planner_graph():
    g = StateGraph(PlannerState)
    g.add_node("load_context", node_load_context)
    g.add_node("shortlist", node_shortlist)
    g.add_node("draft_plan", node_draft_plan)
    g.add_node("validate", node_validate)
    g.add_node("repair", node_repair)
    g.add_node("fallback_fill", node_fallback)
    g.add_node("persist", node_persist)
    g.add_edge(START, "load_context")
    g.add_edge("load_context", "shortlist")
    g.add_edge("shortlist", "draft_plan")
    g.add_edge("draft_plan", "validate")
    g.add_conditional_edges("validate", _after_validate, ["persist", "repair", "fallback_fill"])
    g.add_edge("repair", "validate")
    g.add_edge("fallback_fill", "persist")
    g.add_edge("persist", END)
    return g.compile()


_GRAPH = None


def planner_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_planner_graph()
    return _GRAPH


class PlannerOutcome(BaseModel):
    plan_id: UUID
    attempts: int
    used_fallback: bool
    inputs_hash: str | None
    entries_written: int
    finished_at: datetime


async def run_planner(session_factory, llm: LLM, inp: PlannerInput) -> PlannerOutcome:
    config: RunnableConfig = {"configurable": {"llm": llm, "session_factory": session_factory}}
    initial: PlannerState = {
        "input": inp,
        "context": None,
        "shortlist": [],
        "draft": None,
        "violations": [],
        "warnings": [],
        "bad_entry_indexes": [],
        "attempts": 0,
        "used_fallback": False,
        "persisted": False,
        "entries_written": 0,
        "llm_error": None,
    }
    state = await planner_graph().ainvoke(initial, config=config)
    return PlannerOutcome(
        plan_id=inp.plan_id,
        attempts=state.get("attempts", 0),
        used_fallback=bool(state.get("used_fallback")),
        inputs_hash=state.get("inputs_hash"),
        entries_written=state.get("entries_written", 0),
        finished_at=datetime.now(),
    )

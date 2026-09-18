"""Onboarding agent graph (LLD §8.1).

    START -> ingest_answer -> select_next_field -> compose_question -> END
                                               \\-> summarize        -> END
Each HTTP turn is one invocation; state persists through the checkpointer keyed by thread id.
"""

import logging
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from larder.agents.onboarding.fields import FIELD_BY_NAME, coerce_widget_value, next_field, progress
from larder.agents.onboarding.prompts import SUMMARY_MESSAGE, SYSTEM_PARSE, SYSTEM_QUESTION
from larder.agents.onboarding.schemas import ParsedFieldAnswer, ProfileDraft, Progress
from larder.agents.onboarding.state import OnboardingState
from larder.agents.onboarding.widgets import ReviewWidget, Widget, parse_widget
from larder.llm.base import LLM, LLMError, build_context_block

log = logging.getLogger("larder.onboarding")

MIN_PARSE_CONFIDENCE = 0.4


def _llm(config: RunnableConfig) -> LLM:
    return config["configurable"]["llm"]


def _summarise_answer(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(v.get("name") if isinstance(v, dict) else v) for v in value) or "none"
    return str(value)


async def ingest_answer(state: OnboardingState, config: RunnableConfig) -> dict:
    answer = state.get("last_answer")
    field_name = state.get("current_field")
    if not answer or not field_name or field_name not in FIELD_BY_NAME:
        return {"error": None}
    spec = FIELD_BY_NAME[field_name]
    try:
        if answer.get("kind") == "text":
            text = str(answer.get("text", "")).strip()
            user = f"Reply: {text}\n" + build_context_block(
                {
                    "task": "onboarding_parse",
                    "field": spec.name,
                    "description": spec.description,
                    "expected": spec.parse_hint,
                    "text": text,
                }
            )
            parsed = await _llm(config).complete_structured(
                system=SYSTEM_PARSE, user=user, schema=ParsedFieldAnswer, temperature=0
            )
            if parsed.value is None or parsed.confidence < MIN_PARSE_CONFIDENCE:
                raise ValueError("I couldn't quite catch that")
            raw = parsed.value
        else:
            raw = answer.get("value")
        cleaned = spec.validate(coerce_widget_value(spec, raw))
    except LLMError as exc:
        log.warning("parse failed: %s", exc)
        return {"error": "I couldn't read that just now — could you use the picker below?"}
    except (ValueError, TypeError) as exc:
        return {"error": str(exc)}
    return {
        "draft": {spec.name: cleaned},
        "error": None,
        "history": [{"role": "user", "content": _summarise_answer(cleaned)}],
    }


async def select_next_field(state: OnboardingState) -> dict:
    spec = next_field(state.get("draft") or {})
    return {"current_field": spec.name if spec else None}


async def compose_question(state: OnboardingState, config: RunnableConfig) -> dict:
    spec = FIELD_BY_NAME[state["current_field"]]  # type: ignore[index]
    draft = state.get("draft") or {}
    error = state.get("error")
    context = {
        "task": "onboarding_question",
        "field": spec.name,
        "field_description": spec.description,
        "draft_so_far": {k: v for k, v in draft.items() if k not in ("medical_conditions", "medical_notes")},
        "error": error,
        "default_question": spec.default_question,
    }
    try:
        text = (
            await _llm(config).complete_text(
                system=SYSTEM_QUESTION, user="Ask the next question.\n" + build_context_block(context)
            )
        ).strip()
        if not text or len(text) > 400:
            raise LLMError("empty or oversized question")
    except LLMError as exc:
        log.warning("compose_question fell back to default: %s", exc)
        text = f"{error}. {spec.default_question}" if error else spec.default_question
    return {
        "message": text,
        "widget": spec.widget().model_dump(mode="json"),
        "history": [{"role": "assistant", "content": text}],
    }


async def summarize(state: OnboardingState) -> dict:
    draft = ProfileDraft(**(state.get("draft") or {}))
    return {
        "is_complete": True,
        "message": SUMMARY_MESSAGE,
        "widget": ReviewWidget(draft=draft).model_dump(mode="json"),
        "history": [{"role": "assistant", "content": SUMMARY_MESSAGE}],
    }


def _route(state: OnboardingState) -> str:
    return "compose_question" if state.get("current_field") else "summarize"


def build_onboarding_graph(checkpointer):
    g = StateGraph(OnboardingState)
    g.add_node("ingest_answer", ingest_answer)
    g.add_node("select_next_field", select_next_field)
    g.add_node("compose_question", compose_question)
    g.add_node("summarize", summarize)
    g.add_edge(START, "ingest_answer")
    g.add_edge("ingest_answer", "select_next_field")
    g.add_conditional_edges("select_next_field", _route, ["compose_question", "summarize"])
    g.add_edge("compose_question", END)
    g.add_edge("summarize", END)
    return g.compile(checkpointer=checkpointer)


class TurnResult(BaseModel):
    message: str
    widget: Widget | None
    field: str | None
    draft: ProfileDraft
    progress: Progress
    is_complete: bool


def thread_id_for(user_id: str) -> str:
    return f"onb_{user_id}"


async def run_turn(graph, llm: LLM, user_id: str, last_answer: dict | None) -> TurnResult:
    config: RunnableConfig = {"configurable": {"thread_id": thread_id_for(user_id), "llm": llm}}
    state = await graph.ainvoke({"user_id": user_id, "last_answer": last_answer}, config=config)
    draft = state.get("draft") or {}
    answered, total = progress(draft)
    return TurnResult(
        message=state.get("message", ""),
        widget=parse_widget(state.get("widget")),
        field=state.get("current_field"),
        draft=ProfileDraft(**draft),
        progress=Progress(answered=answered, total=total),
        is_complete=bool(state.get("is_complete")),
    )


async def current_state(graph, user_id: str) -> dict | None:
    """The last checkpointed state for a thread, or None when the thread does not exist."""
    snapshot = await graph.aget_state({"configurable": {"thread_id": thread_id_for(user_id)}})
    return snapshot.values if snapshot and snapshot.values else None

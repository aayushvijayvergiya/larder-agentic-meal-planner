"""LangGraph state for the onboarding conversation (LLD §8.1)."""

from typing import Annotated, TypedDict

HISTORY_CAP = 20


def merge_draft(current: dict | None, update: dict | None) -> dict:
    return {**(current or {}), **(update or {})}


def append_history(current: list | None, update: list | None) -> list:
    return ((current or []) + (update or []))[-HISTORY_CAP:]


class OnboardingState(TypedDict, total=False):
    user_id: str
    draft: Annotated[dict, merge_draft]
    current_field: str | None
    last_answer: dict | None
    message: str
    widget: dict | None
    error: str | None
    history: Annotated[list[dict], append_history]
    is_complete: bool

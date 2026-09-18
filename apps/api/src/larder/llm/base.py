"""LLM provider protocol (LLD §5.1)."""

import json
import re
from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """Raised after the provider's retry is exhausted or output cannot be parsed. Routers map it to llm_unavailable."""


class LLM(Protocol):
    name: str

    async def complete_text(self, *, system: str, user: str, temperature: float = 0.7) -> str: ...

    async def complete_structured(self, *, system: str, user: str, schema: type[T], temperature: float = 0.2) -> T: ...


_CONTEXT_RE = re.compile(r"<context>(.*?)</context>", re.S)


def build_context_block(context: dict) -> str:
    """Every user prompt ends with this block so the fake provider can read the same inputs as the real one."""
    return "<context>\n" + json.dumps(context, default=str, ensure_ascii=False) + "\n</context>"


def extract_context(user: str) -> dict:
    m = _CONTEXT_RE.search(user)
    if not m:
        return {}
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return {}

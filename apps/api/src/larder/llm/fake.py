"""Deterministic fake provider for development and tests (LLD §5.3)."""

from collections.abc import Callable

from pydantic import BaseModel

from larder.llm.base import LLMError, extract_context
from larder.llm.fake_handlers import register_default_handlers


class FakeLLM:
    name = "fake"

    def __init__(self) -> None:
        self._text_queue: list[str] = []
        self._structured_queues: dict[str, list[BaseModel]] = {}
        self._handlers: dict[str, Callable[[dict, type[BaseModel]], BaseModel]] = {}
        self._text_handlers: dict[str, Callable[[dict], str]] = {}
        self._fail: Exception | None = None
        self.calls: list[dict] = []
        register_default_handlers(self)

    # --- scripting API used by tests -------------------------------------------------
    def script_text(self, responses: list[str]) -> None:
        self._text_queue.extend(responses)

    def script_structured(self, schema: type[BaseModel], instances: list[BaseModel]) -> None:
        self._structured_queues.setdefault(schema.__name__, []).extend(instances)

    def fail_next(self, exc: Exception) -> None:
        self._fail = exc

    def register_handler(self, schema_name: str, fn: Callable[[dict, type[BaseModel]], BaseModel]) -> None:
        self._handlers[schema_name] = fn

    def register_text_handler(self, task: str, fn: Callable[[dict], str]) -> None:
        """Text handlers key off the `task` value inside the prompt's <context> block."""
        self._text_handlers[task] = fn

    def reset(self) -> None:
        self._text_queue.clear()
        self._structured_queues.clear()
        self._fail = None
        self.calls.clear()

    # --- provider API ---------------------------------------------------------------
    def _maybe_fail(self) -> None:
        if self._fail is not None:
            exc, self._fail = self._fail, None
            raise exc

    async def complete_text(self, *, system: str, user: str, temperature: float = 0.7) -> str:
        self.calls.append({"kind": "text", "system": system, "user": user, "schema": None})
        self._maybe_fail()
        if self._text_queue:
            return self._text_queue.pop(0)
        ctx = extract_context(user)
        fn = self._text_handlers.get(str(ctx.get("task", "")))
        if fn is not None:
            return fn(ctx)
        return f"[fake] {user[:80]}"

    async def complete_structured(self, *, system: str, user: str, schema, temperature: float = 0.2):
        name = schema.__name__
        self.calls.append({"kind": "structured", "system": system, "user": user, "schema": name})
        self._maybe_fail()
        queue = self._structured_queues.get(name)
        if queue:
            return queue.pop(0)
        fn = self._handlers.get(name)
        if fn is None:
            raise LLMError(f"no fake handler for {name}")
        return fn(extract_context(user), schema)

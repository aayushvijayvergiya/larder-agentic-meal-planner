"""Groq provider through the official langchain-groq integration (LLD §5.2)."""

import logging
import time

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from pydantic import ValidationError

from larder.config import Settings
from larder.llm.base import LLMError

log = logging.getLogger("larder.llm")


class GroqLLM:
    def __init__(self, settings: Settings) -> None:
        self.name = f"groq:{settings.groq_model}"
        self._chat = ChatGroq(
            model=settings.groq_model,
            api_key=settings.groq_api_key,
            base_url=settings.groq_base_url,
            timeout=settings.llm_timeout_seconds,
            max_retries=1,
            max_tokens=16000,
            reasoning_effort="low",
        )

    async def complete_text(self, *, system: str, user: str, temperature: float = 0.7) -> str:
        started = time.perf_counter()
        try:
            chat = self._chat.model_copy(update={"temperature": temperature})
            msg = await chat.ainvoke([SystemMessage(content=system), HumanMessage(content=user)])
        except Exception as exc:  # noqa: BLE001
            raise LLMError(str(exc)) from exc
        self._log("text", msg, started)
        return msg.content if isinstance(msg.content, str) else str(msg.content)

    async def complete_structured(self, *, system: str, user: str, schema, temperature: float = 0.2):
        started = time.perf_counter()
        last: Exception | None = None
        chat = self._chat.model_copy(update={"temperature": temperature})
        for method in ("json_schema", "function_calling"):
            try:
                model = chat.with_structured_output(schema, method=method)
                out = await model.ainvoke([SystemMessage(content=system), HumanMessage(content=user)])
                result = out if isinstance(out, schema) else schema.model_validate(out)
                log.info(
                    "llm structured %s via %s in %.0f ms",
                    schema.__name__,
                    method,
                    (time.perf_counter() - started) * 1000,
                )
                return result
            except ValidationError as exc:
                raise LLMError(f"invalid structured output for {schema.__name__}: {exc}") from exc
            except Exception as exc:  # noqa: BLE001
                last = exc
                log.warning("structured output via %s failed: %s", method, exc)
                continue
        raise LLMError(str(last))

    @staticmethod
    def _log(kind: str, msg, started: float) -> None:
        usage = getattr(msg, "usage_metadata", None) or {}
        log.info(
            "llm %s in %.0f ms (in=%s out=%s)",
            kind,
            (time.perf_counter() - started) * 1000,
            usage.get("input_tokens"),
            usage.get("output_tokens"),
        )

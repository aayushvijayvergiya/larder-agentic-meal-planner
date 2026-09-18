import pytest
from pydantic import BaseModel

from larder.llm.base import LLMError, build_context_block, extract_context
from larder.llm.fake import FakeLLM


class Out(BaseModel):
    x: int


async def test_scripted_structured_and_default_text():
    llm = FakeLLM()
    llm.script_structured(Out, [Out(x=7)])
    assert (await llm.complete_structured(system="s", user="u", schema=Out)).x == 7
    assert (await llm.complete_text(system="s", user="hello")).startswith("[fake]")
    assert [c["kind"] for c in llm.calls] == ["structured", "text"]


async def test_fail_next_raises_once():
    llm = FakeLLM()
    llm.fail_next(LLMError("down"))
    with pytest.raises(LLMError):
        await llm.complete_text(system="s", user="u")
    assert (await llm.complete_text(system="s", user="u")).startswith("[fake]")


async def test_unknown_schema_without_handler_raises():
    llm = FakeLLM()
    with pytest.raises(LLMError):
        await llm.complete_structured(system="s", user="u", schema=Out)


async def test_handler_receives_context():
    llm = FakeLLM()
    llm.register_handler("Out", lambda ctx, schema: schema(x=ctx["n"] * 2))
    user = "Please compute.\n" + build_context_block({"n": 21})
    assert (await llm.complete_structured(system="s", user=user, schema=Out)).x == 42


def test_extract_context_tolerates_missing_or_bad_block():
    assert extract_context("no block") == {}
    assert extract_context("<context>{not json}</context>") == {}

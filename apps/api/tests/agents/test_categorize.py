from larder.agents.categorize.categorize import categorize
from larder.agents.categorize.schemas import CategoryAssignment, CategoryAssignments
from larder.llm.base import LLMError
from larder.llm.fake import FakeLLM


async def test_map_hits_skip_llm_and_unknowns_go_to_llm():
    llm = FakeLLM()
    llm.script_structured(
        CategoryAssignments,
        [CategoryAssignments(assignments=[CategoryAssignment(name="gundruk", category="vegetables")])],
    )
    out = await categorize(llm, ["Paneer", "red onion", "gundruk"])
    assert out == {"Paneer": "dairy", "red onion": "vegetables", "gundruk": "vegetables"}
    assert len(llm.calls) == 1
    assert "gundruk" in llm.calls[0]["user"] and "Paneer" not in llm.calls[0]["user"]


async def test_no_llm_call_when_everything_is_known():
    llm = FakeLLM()
    assert await categorize(llm, ["milk", "atta"]) == {"milk": "dairy", "atta": "flours"}
    assert llm.calls == []


async def test_default_fake_handler_gives_other():
    llm = FakeLLM()
    assert (await categorize(llm, ["mystery item"]))["mystery item"] == "other"


async def test_llm_failure_falls_back_to_other():
    llm = FakeLLM()
    llm.fail_next(LLMError("x"))
    assert (await categorize(llm, ["mystery"]))["mystery"] == "other"

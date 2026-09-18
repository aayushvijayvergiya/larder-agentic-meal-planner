from langgraph.checkpoint.memory import InMemorySaver

from larder.agents.onboarding.graph import build_onboarding_graph, run_turn
from larder.agents.onboarding.schemas import ParsedFieldAnswer
from larder.llm.base import LLMError
from larder.llm.fake import FakeLLM

ANSWERS = {
    "display_name": "Priya",
    "date_of_birth": "1995-04-02",
    "sex": "female",
    "height_cm": 165,
    "weight_kg": 58,
    "activity_level": "moderate",
    "diet_type": "vegetarian",
    "cuisines": ["north_indian"],
    "allergens": ["peanut"],
    "dislikes": ["bitter gourd"],
    "likes": ["paneer"],
    "medical_conditions": ["type 2 diabetes"],
    "medical_notes": "avoid sugar",
    "goals": ["eat_healthier"],
    "cooking_skill": "intermediate",
    "max_prep_minutes": "30",
}


async def test_full_conversation_with_one_invalid_and_one_text_answer():
    llm = FakeLLM()
    graph = build_onboarding_graph(InMemorySaver())
    t = await run_turn(graph, llm, "u1", None)
    assert t.field == "display_name" and t.widget.type == "text" and not t.is_complete
    assert t.progress.answered == 0 and t.progress.total == 15
    sent_bad_height = False
    while not t.is_complete:
        if t.field == "height_cm" and not sent_bad_height:
            sent_bad_height = True
            t = await run_turn(graph, llm, "u1", {"kind": "widget", "value": 900})
            assert t.field == "height_cm" and "between" in t.message.lower()
            continue
        if t.field == "weight_kg":
            llm.script_structured(ParsedFieldAnswer, [ParsedFieldAnswer(value=58, confidence=0.9)])
            t = await run_turn(graph, llm, "u1", {"kind": "text", "text": "about 58 kilos"})
            continue
        t = await run_turn(graph, llm, "u1", {"kind": "widget", "value": ANSWERS[t.field]})
    assert t.widget.type == "review"
    assert t.draft.weight_kg == 58 and t.draft.display_name == "Priya"
    assert t.draft.medical_conditions[0].name == "type 2 diabetes" and t.draft.medical_notes == "avoid sugar"
    assert t.progress.answered == 16 and t.progress.total == 16
    assert t.draft.max_prep_minutes == 30


async def test_unparseable_text_reasks_and_llm_failure_falls_back_to_default_question():
    llm = FakeLLM()
    graph = build_onboarding_graph(InMemorySaver())
    t = await run_turn(graph, llm, "u2", None)
    assert "call you" in t.message
    t = await run_turn(graph, llm, "u2", {"kind": "widget", "value": "Aarav"})
    assert t.field == "date_of_birth" and t.message.startswith("Aarav,")
    # default fake parser returns no value -> same field re-asked with an error message
    t = await run_turn(graph, llm, "u2", {"kind": "text", "text": "long ago"})
    assert t.field == "date_of_birth" and "couldn't" in t.message.lower()
    # LLM outage while composing -> deterministic default question, conversation continues
    llm.fail_next(LLMError("down"))
    t = await run_turn(graph, llm, "u2", {"kind": "widget", "value": "1990-01-01"})
    assert t.field == "sex" and t.message == "Which best describes you?"


async def test_start_twice_repeats_pending_question_without_losing_answers():
    llm = FakeLLM()
    graph = build_onboarding_graph(InMemorySaver())
    await run_turn(graph, llm, "u3", None)
    await run_turn(graph, llm, "u3", {"kind": "widget", "value": "Priya"})
    t = await run_turn(graph, llm, "u3", None)
    assert t.field == "date_of_birth" and t.draft.display_name == "Priya" and t.progress.answered == 1

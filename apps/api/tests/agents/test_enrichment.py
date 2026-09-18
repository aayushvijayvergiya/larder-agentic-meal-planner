from larder.agents.enrichment.enrich import enrich_meal
from larder.agents.enrichment.schemas import IngredientDraft, MealEnrichment
from larder.llm.fake import FakeLLM


async def test_default_fake_enrichment_keeps_user_ingredients():
    llm = FakeLLM()
    out = await enrich_meal(
        llm,
        name="Palak paneer",
        description=None,
        ingredients=["spinach", "paneer", "cream"],
        instructions=None,
        slot_keys=["lunch", "dinner"],
    )
    names = [i.name for i in out.ingredients]
    assert {"spinach", "paneer", "cream"} <= set(names)
    assert out.prep_minutes >= 5
    assert set(out.meal_types) <= {"lunch", "dinner", "any"}
    assert "dairy" in out.allergens and out.diet_tags == ["vegetarian"]
    cats = {i.name: i.category for i in out.ingredients}
    assert cats["spinach"] == "vegetables" and cats["paneer"] == "dairy"


async def test_unknown_tags_are_dropped_and_allergens_inferred():
    llm = FakeLLM()
    llm.script_structured(
        MealEnrichment,
        [
            MealEnrichment(
                description="d",
                cuisine="North Indian",
                meal_types=["dinner", "brunch"],
                diet_tags=["vegetarian", "keto!!"],
                allergens=["unicorn"],
                prep_minutes=20,
                ingredients=[
                    IngredientDraft(name="Paneer"),
                    IngredientDraft(name="PANEER"),
                    IngredientDraft(name="Salt"),
                ],
            )
        ],
    )
    out = await enrich_meal(
        llm, name="X", description=None, ingredients=["ghee"], instructions=None, slot_keys=["dinner"]
    )
    assert out.diet_tags == ["vegetarian"]
    assert out.allergens == ["dairy"]  # inferred from paneer/ghee even though the model said nothing usable
    assert out.cuisine == "north_indian" and out.meal_types == ["dinner"]
    names = [i.name for i in out.ingredients]
    assert names == ["Paneer", "Salt", "ghee"]  # duplicate dropped, user ingredient appended
    assert next(i for i in out.ingredients if i.name == "Salt").is_staple is True


async def test_meal_types_default_to_any_when_none_match():
    llm = FakeLLM()
    llm.script_structured(
        MealEnrichment,
        [
            MealEnrichment(
                description="d",
                cuisine="x",
                meal_types=["supper"],
                diet_tags=[],
                allergens=[],
                prep_minutes=10,
                ingredients=[IngredientDraft(name="rice")],
            )
        ],
    )
    out = await enrich_meal(llm, name="X", description=None, ingredients=None, instructions=None, slot_keys=["dinner"])
    assert out.meal_types == ["any"]

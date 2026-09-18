from pydantic import BaseModel, Field

from larder.schemas.common import PantryCategory


class IngredientDraft(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    category: PantryCategory = "other"
    is_staple: bool = False
    is_optional: bool = False


class MealEnrichment(BaseModel):
    description: str = Field(max_length=240)
    cuisine: str = Field(max_length=40)
    meal_types: list[str]
    diet_tags: list[str]
    allergens: list[str]
    prep_minutes: int = Field(ge=5, le=240)
    ingredients: list[IngredientDraft] = Field(min_length=1, max_length=25)

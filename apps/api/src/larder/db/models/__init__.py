"""ORM models (LLD §3). Import this package so every table is registered on Base.metadata."""

from larder.db.base import Base
from larder.db.models.feedback import MealFeedback
from larder.db.models.household import DEFAULT_SLOTS, Household, HouseholdInvite, HouseholdMember
from larder.db.models.meal import Meal, MealIngredient
from larder.db.models.pantry import PantryItem
from larder.db.models.plan import MealPlan, PlanEntry, PlanEntryVariation, PlanJob
from larder.db.models.profile import Profile
from larder.db.models.refresh import RefreshRun

__all__ = [
    "Base",
    "DEFAULT_SLOTS",
    "Household",
    "HouseholdInvite",
    "HouseholdMember",
    "Meal",
    "MealFeedback",
    "MealIngredient",
    "MealPlan",
    "PantryItem",
    "PlanEntry",
    "PlanEntryVariation",
    "PlanJob",
    "Profile",
    "RefreshRun",
]

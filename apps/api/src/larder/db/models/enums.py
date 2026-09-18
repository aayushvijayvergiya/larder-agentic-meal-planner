"""Enumeration value sets (LLD §3.1). Columns store plain strings backed by PostgreSQL enums."""

from sqlalchemy import Enum

SEX = ("female", "male", "other", "prefer_not_to_say")
ACTIVITY = ("sedentary", "light", "moderate", "active", "very_active")
DIET = ("omnivore", "vegetarian", "eggetarian", "vegan", "pescatarian", "jain", "other")
SKILL = ("beginner", "intermediate", "advanced")
ONBOARDING = ("pending", "in_progress", "complete")
MEMBER_ROLE = ("owner", "member")
VIEW = ("single", "family")
PANTRY_CATEGORY = (
    "spices",
    "grains",
    "pulses",
    "flours",
    "dairy",
    "vegetables",
    "fruits",
    "proteins",
    "condiments",
    "oils",
    "snacks",
    "beverages",
    "frozen",
    "other",
)
MEAL_SOURCE = ("user", "generated")
ENRICHMENT = ("pending", "complete", "failed")
PLAN_SCOPE = ("family", "single")
PLAN_STATUS = ("active", "superseded")
JOB_MODE = ("week", "today", "slot")
JOB_STATUS = ("queued", "running", "ready", "failed")
JOB_ORIGIN = ("user", "scheduler", "onboarding")
FEEDBACK = ("up", "down", "cooked", "skipped")
REFRESH_KIND = ("weekly", "daily")


def sex_enum() -> Enum:
    return Enum(*SEX, name="sex_enum")


def activity_enum() -> Enum:
    return Enum(*ACTIVITY, name="activity_enum")


def diet_enum() -> Enum:
    return Enum(*DIET, name="diet_enum")


def skill_enum() -> Enum:
    return Enum(*SKILL, name="skill_enum")


def onboarding_enum() -> Enum:
    return Enum(*ONBOARDING, name="onboarding_enum")


def member_role_enum() -> Enum:
    return Enum(*MEMBER_ROLE, name="member_role_enum")


def view_enum() -> Enum:
    return Enum(*VIEW, name="view_enum")


def pantry_category_enum() -> Enum:
    return Enum(*PANTRY_CATEGORY, name="pantry_category_enum")


def meal_source_enum() -> Enum:
    return Enum(*MEAL_SOURCE, name="meal_source_enum")


def enrichment_enum() -> Enum:
    return Enum(*ENRICHMENT, name="enrichment_enum")


def plan_scope_enum() -> Enum:
    return Enum(*PLAN_SCOPE, name="plan_scope_enum")


def plan_status_enum() -> Enum:
    return Enum(*PLAN_STATUS, name="plan_status_enum")


def job_mode_enum() -> Enum:
    return Enum(*JOB_MODE, name="job_mode_enum")


def job_status_enum() -> Enum:
    return Enum(*JOB_STATUS, name="job_status_enum")


def job_origin_enum() -> Enum:
    return Enum(*JOB_ORIGIN, name="job_origin_enum")


def feedback_enum() -> Enum:
    return Enum(*FEEDBACK, name="feedback_enum")


def refresh_kind_enum() -> Enum:
    return Enum(*REFRESH_KIND, name="refresh_kind_enum")

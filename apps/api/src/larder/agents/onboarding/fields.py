"""Ordered onboarding fields with widgets, coercion and validation (LLD §8.1)."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from larder.agents.onboarding.widgets import (
    ChipsWidget,
    DateWidget,
    MultiSelectWidget,
    NumberWidget,
    Option,
    SingleSelectWidget,
    TextWidget,
)
from larder.agents.planner.vocab import ALLERGENS
from larder.services.normalize import normalize_name, slugify

NONE_VALUES = {"none", "no", "nothing", "n/a", "na", "-"}


@dataclass(frozen=True)
class FieldSpec:
    name: str
    description: str
    widget: Callable[[], Any]
    coerce: Callable[[Any], Any]
    validate: Callable[[Any], Any]
    default_question: str
    parse_hint: str
    condition: Callable[[dict], bool] | None = None


def _opts(*pairs: tuple[str, str] | tuple[str, str, str]) -> list[Option]:
    return [Option(value=p[0], label=p[1], description=p[2] if len(p) > 2 else None) for p in pairs]


def _enum_validator(allowed: list[str], label: str) -> Callable[[Any], str]:
    def _v(value: Any) -> str:
        v = str(value).strip().lower().replace(" ", "_")
        if v not in allowed:
            raise ValueError(f"{label} must be one of: {', '.join(allowed)}")
        return v

    return _v


def _str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [p for p in value.replace("\n", ",").split(",")]
    return [str(v).strip() for v in value if str(v).strip()]


def _norm_list(max_items: int) -> Callable[[Any], list[str]]:
    def _v(value: Any) -> list[str]:
        items = _str_list(value)
        if len(items) == 1 and items[0].lower() in NONE_VALUES:
            return []
        out: list[str] = []
        for i in items:
            n = normalize_name(i)
            if n and n not in out:
                out.append(n)
        if len(out) > max_items:
            raise ValueError(f"please keep it to {max_items} items")
        return out

    return _v


def _coerce_number(value: Any) -> float:
    if isinstance(value, bool):
        raise ValueError("please enter a number")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("please enter a number") from exc


def _validate_display_name(value: Any) -> str:
    v = " ".join(str(value).split())
    if not 1 <= len(v) <= 40:
        raise ValueError("a name between 1 and 40 characters, please")
    return v


def _coerce_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError as exc:
        raise ValueError("please give the date as YYYY-MM-DD") from exc


def _validate_dob(value: date) -> str:
    today = date.today()
    age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
    if age < 5 or age > 120:
        raise ValueError("that date gives an age outside 5 to 120 years")
    return value.isoformat()


def _range(lo: float, hi: float, label: str, as_int: bool = False) -> Callable[[Any], float | int]:
    def _v(value: Any) -> float | int:
        n = _coerce_number(value)
        if not lo <= n <= hi:
            raise ValueError(f"{label} should be between {lo:g} and {hi:g}")
        return int(round(n)) if as_int else round(n, 1)

    return _v


def _slug_list(min_items: int, max_items: int, label: str) -> Callable[[Any], list[str]]:
    def _v(value: Any) -> list[str]:
        out: list[str] = []
        for i in _str_list(value):
            s = slugify(i)
            if s and s not in out:
                out.append(s)
        if not min_items <= len(out) <= max_items:
            raise ValueError(f"pick between {min_items} and {max_items} {label}")
        return out

    return _v


def _validate_conditions(value: Any) -> list[dict]:
    items = _str_list(value)
    if not items or (len(items) == 1 and items[0].lower() in NONE_VALUES):
        return []
    out: list[dict] = []
    seen: set[str] = set()
    for i in items[:10]:
        key = i.strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append({"name": i.strip()[:80], "notes": None})
    return out


def _validate_notes(value: Any) -> str:
    v = str(value).strip()
    if len(v) > 500:
        raise ValueError("please keep the notes under 500 characters")
    return v


def _has_conditions(draft: dict) -> bool:
    conds = draft.get("medical_conditions") or []
    for c in conds:
        name = c.get("name") if isinstance(c, dict) else str(c)
        if name and name.strip().lower() not in NONE_VALUES:
            return True
    return False


SEX = ["female", "male", "other", "prefer_not_to_say"]
ACTIVITY = ["sedentary", "light", "moderate", "active", "very_active"]
DIET = ["omnivore", "vegetarian", "eggetarian", "vegan", "pescatarian", "jain", "other"]
SKILL = ["beginner", "intermediate", "advanced"]
GOALS = ["weight_loss", "muscle_gain", "maintenance", "manage_condition", "eat_healthier", "save_time", "reduce_waste"]
CUISINES = [
    "north_indian",
    "south_indian",
    "gujarati",
    "bengali",
    "punjabi",
    "maharashtrian",
    "continental",
    "italian",
    "chinese",
    "mediterranean",
    "mexican",
    "thai",
]
PREP_OPTIONS = ["15", "30", "45", "60", "90"]


def _label(slug: str) -> str:
    return slug.replace("_", " ").capitalize()


FIELDS: list[FieldSpec] = [
    FieldSpec(
        "display_name",
        "the name they would like to be called",
        lambda: TextWidget(placeholder="Your first name", max_length=40),
        str,
        _validate_display_name,
        "What should I call you?",
        "a short name (string)",
    ),
    FieldSpec(
        "date_of_birth",
        "their date of birth",
        lambda: DateWidget(min=date(1900, 1, 1), max=date.today() - timedelta(days=5 * 365)),
        _coerce_date,
        _validate_dob,
        "When were you born?",
        "a date in YYYY-MM-DD format (string)",
    ),
    FieldSpec(
        "sex",
        "their biological sex, for nutrition estimates",
        lambda: SingleSelectWidget(
            options=_opts(
                ("female", "Female"), ("male", "Male"), ("other", "Other"), ("prefer_not_to_say", "Prefer not to say")
            )
        ),
        str,
        _enum_validator(SEX, "sex"),
        "Which best describes you?",
        f"one of {SEX} (string)",
    ),
    FieldSpec(
        "height_cm",
        "their height in centimetres",
        lambda: NumberWidget(unit="cm", min=50, max=250, step=1),
        _coerce_number,
        _range(50, 250, "height", as_int=True),
        "Roughly how tall are you, in centimetres?",
        "height in centimetres (number)",
    ),
    FieldSpec(
        "weight_kg",
        "their weight in kilograms",
        lambda: NumberWidget(unit="kg", min=20, max=400, step=0.5),
        _coerce_number,
        _range(20, 400, "weight"),
        "And your weight, in kilograms?",
        "weight in kilograms (number)",
    ),
    FieldSpec(
        "activity_level",
        "how physically active they are",
        lambda: SingleSelectWidget(
            options=_opts(
                ("sedentary", "Sedentary", "Desk work, little exercise"),
                ("light", "Light", "Walks or light exercise 1-3 days a week"),
                ("moderate", "Moderate", "Exercise 3-5 days a week"),
                ("active", "Active", "Hard exercise most days"),
                ("very_active", "Very active", "Physical job or training twice a day"),
            )
        ),
        str,
        _enum_validator(ACTIVITY, "activity level"),
        "How active are you in a typical week?",
        f"one of {ACTIVITY} (string)",
    ),
    FieldSpec(
        "diet_type",
        "their diet type",
        lambda: SingleSelectWidget(options=_opts(*[(d, _label(d)) for d in DIET])),
        str,
        _enum_validator(DIET, "diet type"),
        "How would you describe the way you eat?",
        f"one of {DIET} (string)",
    ),
    FieldSpec(
        "cuisines",
        "the cuisines they enjoy most (one to six)",
        lambda: MultiSelectWidget(options=_opts(*[(c, _label(c)) for c in CUISINES]), allow_custom=True, min=1, max=6),
        _str_list,
        _slug_list(1, 6, "cuisines"),
        "Which cuisines do you cook or crave most often?",
        "a list of cuisine names (list of strings)",
    ),
    FieldSpec(
        "allergens",
        "food allergies or intolerances, if any",
        lambda: MultiSelectWidget(
            options=_opts(("none", "None"), *[(a, _label(a)) for a in ALLERGENS]), allow_custom=True, min=0, max=20
        ),
        _str_list,
        _norm_list(20),
        "Any food allergies or intolerances I should always avoid?",
        "a list of allergens, or 'none' (list of strings)",
    ),
    FieldSpec(
        "dislikes",
        "ingredients or dishes they dislike",
        lambda: ChipsWidget(placeholder="e.g. bitter gourd, mushrooms", max=20),
        _str_list,
        _norm_list(20),
        "Anything you would rather never see on your plate?",
        "a list of disliked foods (list of strings)",
    ),
    FieldSpec(
        "likes",
        "ingredients or dishes they love",
        lambda: ChipsWidget(placeholder="e.g. paneer, rajma, dosa", max=20),
        _str_list,
        _norm_list(20),
        "And what do you love eating?",
        "a list of favourite foods (list of strings)",
    ),
    FieldSpec(
        "medical_conditions",
        "medical conditions that affect what they should eat, if any",
        lambda: ChipsWidget(
            suggestions=[
                "none",
                "type 2 diabetes",
                "hypertension",
                "high cholesterol",
                "PCOS",
                "thyroid",
                "celiac disease",
                "lactose intolerance",
            ],
            placeholder="e.g. type 2 diabetes",
            max=10,
        ),
        _str_list,
        _validate_conditions,
        "Any health conditions I should plan around?",
        "a list of condition names, or 'none' (list of strings)",
    ),
    FieldSpec(
        "medical_notes",
        "any notes on how those conditions affect their food",
        lambda: TextWidget(placeholder="e.g. avoid refined sugar, low salt", multiline=True, max_length=500),
        str,
        _validate_notes,
        "Anything specific your doctor asked you to watch for?",
        "free text notes (string)",
        condition=_has_conditions,
    ),
    FieldSpec(
        "goals",
        "what they want from meal planning (one to four goals)",
        lambda: MultiSelectWidget(options=_opts(*[(g, _label(g)) for g in GOALS]), min=1, max=4),
        _str_list,
        _slug_list(1, 4, "goals"),
        "What would you like Larder to help with?",
        f"a list of goals from {GOALS} (list of strings)",
    ),
    FieldSpec(
        "cooking_skill",
        "how confident a cook they are",
        lambda: SingleSelectWidget(options=_opts(*[(s, _label(s)) for s in SKILL])),
        str,
        _enum_validator(SKILL, "cooking skill"),
        "How confident are you in the kitchen?",
        f"one of {SKILL} (string)",
    ),
    FieldSpec(
        "max_prep_minutes",
        "the most time they usually have to cook a meal",
        lambda: SingleSelectWidget(options=_opts(*[(p, f"{p} minutes") for p in PREP_OPTIONS])),
        _coerce_number,
        _range(5, 240, "cooking time", as_int=True),
        "How much time do you usually have to cook?",
        "minutes as a number",
    ),
]

FIELD_BY_NAME: dict[str, FieldSpec] = {f.name: f for f in FIELDS}


def applicable_fields(draft: dict) -> list[FieldSpec]:
    return [f for f in FIELDS if f.condition is None or f.condition(draft)]


def next_field(draft: dict) -> FieldSpec | None:
    for f in applicable_fields(draft):
        if f.name not in draft:
            return f
    return None


def coerce_widget_value(field: FieldSpec, value: Any) -> Any:
    return field.coerce(value)


def progress(draft: dict) -> tuple[int, int]:
    fields = applicable_fields(draft)
    return sum(1 for f in fields if f.name in draft), len(fields)

"""Controlled vocabularies and diet compatibility (LLD §7.3)."""

from larder.services.normalize import tokens

ALLERGENS: list[str] = [
    "peanut",
    "tree_nut",
    "dairy",
    "egg",
    "gluten",
    "soy",
    "sesame",
    "shellfish",
    "fish",
    "mustard",
    "sulphite",
]

DIET_TAGS: list[str] = [
    "vegan",
    "vegetarian",
    "eggetarian",
    "pescatarian",
    "jain",
    "contains_meat",
    "gluten_free",
    "dairy_free",
    "nut_free",
    "low_carb",
    "high_protein",
]

DIET_COMPAT: dict[str, set[str]] = {
    "vegan": {"vegan"},
    "vegetarian": {"vegan", "vegetarian"},
    "eggetarian": {"vegan", "vegetarian", "eggetarian"},
    "jain": {"jain"},
    "pescatarian": {"vegan", "vegetarian", "eggetarian", "pescatarian"},
}

STAPLE_TOKENS: set[str] = {"salt", "oil", "water", "sugar", "ghee", "turmeric", "cumin", "pepper", "hing", "asafoetida"}

MEAT_TOKENS: set[str] = {
    "chicken",
    "mutton",
    "lamb",
    "beef",
    "pork",
    "bacon",
    "sausage",
    "ham",
    "turkey",
    "keema",
    "mince",
}
EGG_TOKENS: set[str] = {"egg"}
FISH_TOKENS: set[str] = {"fish", "salmon", "tuna", "rohu", "pomfret", "basa", "sardine", "mackerel"}
SHELLFISH_TOKENS: set[str] = {"prawn", "shrimp", "crab", "lobster", "squid", "clam", "mussel"}

ALLERGEN_TOKENS: dict[str, set[str]] = {
    "dairy": {
        "paneer",
        "milk",
        "cream",
        "ghee",
        "curd",
        "yogurt",
        "dahi",
        "butter",
        "cheese",
        "khoya",
        "malai",
        "mawa",
    },
    "egg": EGG_TOKENS,
    "peanut": {"peanut", "groundnut"},
    "tree_nut": {"almond", "cashew", "walnut", "pistachio", "hazelnut", "pecan"},
    "gluten": {
        "wheat",
        "atta",
        "maida",
        "bread",
        "pasta",
        "noodle",
        "semolina",
        "sooji",
        "rava",
        "seitan",
        "roti",
        "naan",
    },
    "soy": {"soy", "soya", "tofu", "tempeh", "edamame"},
    "sesame": {"sesame", "til", "tahini"},
    "shellfish": SHELLFISH_TOKENS,
    "fish": FISH_TOKENS,
    "mustard": {"mustard"},
}


def diet_ok(diet_type: str | None, diet_tags: list[str]) -> bool:
    """True when a meal with these diet tags satisfies the member's diet type."""
    if diet_type in (None, "omnivore", "other"):
        return True
    acceptable = DIET_COMPAT.get(diet_type)
    if acceptable is None:
        return True
    return bool(set(diet_tags) & acceptable)


def infer_allergens(ingredient_names: list[str]) -> list[str]:
    """Allergens implied by ingredient names; used as a safety net on top of what the LLM declares."""
    all_tokens: set[str] = set()
    for name in ingredient_names:
        all_tokens |= tokens(name)
    return [a for a in ALLERGENS if a in ALLERGEN_TOKENS and ALLERGEN_TOKENS[a] & all_tokens]


def infer_diet_tags(ingredient_names: list[str]) -> list[str]:
    """Coarse diet tag from ingredients: contains_meat / pescatarian / eggetarian / vegetarian / vegan."""
    all_tokens: set[str] = set()
    for name in ingredient_names:
        all_tokens |= tokens(name)
    if all_tokens & MEAT_TOKENS:
        return ["contains_meat"]
    if all_tokens & (FISH_TOKENS | SHELLFISH_TOKENS):
        return ["pescatarian"]
    if all_tokens & EGG_TOKENS:
        return ["eggetarian"]
    if all_tokens & ALLERGEN_TOKENS["dairy"]:
        return ["vegetarian"]
    return ["vegetarian", "vegan"]


def is_staple(name: str) -> bool:
    return bool(tokens(name) & STAPLE_TOKENS) and len(tokens(name)) <= 2

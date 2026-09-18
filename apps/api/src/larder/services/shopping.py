"""Shopping list derived from plan entries minus the pantry (LLD §7.7)."""

from datetime import date

from larder.agents.categorize.keyword_map import CATEGORY_LABELS, CATEGORY_ORDER
from larder.schemas.plans import ShoppingGroupOut, ShoppingItemOut, ShoppingListOut
from larder.services.normalize import normalize_name


def build_shopping_list(entries, meals_by_id, from_date: date, to_date: date | None = None) -> ShoppingListOut:
    """Union of non-optional missing ingredients for entries on or after from_date, grouped by category."""
    by_norm: dict[str, dict] = {}
    last_date = from_date
    for e in sorted(entries, key=lambda x: x.date):
        if e.date < from_date:
            continue
        last_date = max(last_date, e.date)
        meal = meals_by_id.get(e.meal_id)
        meal_name = getattr(meal, "name", None) or "Planned meal"
        for m in e.missing_ingredients or []:
            if m.get("is_optional"):
                continue
            norm = normalize_name(m["name"])
            if not norm:
                continue
            item = by_norm.setdefault(norm, {"name": m["name"], "category": m.get("category", "other"), "meals": []})
            if meal_name not in item["meals"]:
                item["meals"].append(meal_name)
    groups: list[ShoppingGroupOut] = []
    for cat in CATEGORY_ORDER:
        items = sorted((i for i in by_norm.values() if i["category"] == cat), key=lambda i: i["name"].lower())
        if items:
            groups.append(
                ShoppingGroupOut(
                    category=cat,
                    label=CATEGORY_LABELS[cat],
                    items=[ShoppingItemOut(name=i["name"], meals=i["meals"]) for i in items],
                )
            )
    return ShoppingListOut(from_date=from_date, to_date=to_date or last_date, groups=groups, total=len(by_norm))

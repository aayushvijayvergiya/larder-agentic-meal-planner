from datetime import date
from types import SimpleNamespace as NS

from larder.services.shopping import build_shopping_list


def test_groups_dedupes_and_drops_optional():
    e0 = NS(
        date=date(2026, 9, 17),
        meal_id="m1",
        missing_ingredients=[{"name": "ghee", "category": "dairy", "is_optional": False}],
    )
    e1 = NS(
        date=date(2026, 9, 18),
        meal_id="m1",
        missing_ingredients=[
            {"name": "Cream", "category": "dairy", "is_optional": False},
            {"name": "coriander", "category": "vegetables", "is_optional": True},
        ],
    )
    e2 = NS(
        date=date(2026, 9, 19),
        meal_id="m2",
        missing_ingredients=[{"name": "cream", "category": "dairy", "is_optional": False}],
    )
    e3 = NS(
        date=date(2026, 9, 19),
        meal_id="m2",
        missing_ingredients=[{"name": "okra", "category": "vegetables", "is_optional": False}],
    )
    out = build_shopping_list(
        [e0, e1, e2, e3], {"m1": NS(name="Palak paneer"), "m2": NS(name="Malai kofta")}, from_date=date(2026, 9, 18)
    )
    assert out.total == 2 and out.from_date == date(2026, 9, 18) and out.to_date == date(2026, 9, 19)
    assert [g.category for g in out.groups] == ["vegetables", "dairy"]
    dairy = out.groups[1]
    assert (
        dairy.label == "Dairy"
        and dairy.items[0].name == "Cream"
        and dairy.items[0].meals == ["Palak paneer", "Malai kofta"]
    )
    assert out.groups[0].items[0].name == "okra"


def test_empty_plan_gives_empty_list():
    out = build_shopping_list([], {}, from_date=date(2026, 9, 18))
    assert out.total == 0 and out.groups == [] and out.to_date == date(2026, 9, 18)

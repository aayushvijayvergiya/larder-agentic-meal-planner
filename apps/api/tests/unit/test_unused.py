from datetime import date
from types import SimpleNamespace as NS

from larder.services.unused import unused_from


def _p(name, cat, available=True):
    return NS(name=name, normalized_name=name.lower(), category=cat, is_available=available)


def test_unused_excludes_spices_used_and_unavailable():
    pantry = [
        _p("Cumin", "spices"),
        _p("Bottle gourd", "vegetables"),
        _p("Paneer", "dairy"),
        _p("Okra", "vegetables", available=False),
        _p("Apple", "fruits"),
    ]
    entries = [
        NS(date=date(2026, 9, 18), covered_ingredients=["paneer"]),
        NS(date=date(2026, 9, 17), covered_ingredients=["apple"]),  # in the past: does not count as used
    ]
    assert [i["name"] for i in unused_from(pantry, entries, date(2026, 9, 18))] == ["Apple", "Bottle gourd"]


def test_unused_caps_at_eight():
    pantry = [_p(f"Veg {i:02d}", "vegetables") for i in range(12)]
    assert len(unused_from(pantry, [], date(2026, 9, 18))) == 8

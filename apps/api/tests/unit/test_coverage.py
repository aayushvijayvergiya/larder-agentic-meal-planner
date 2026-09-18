from larder.agents.planner.state import IngredientCtx
from larder.services.coverage import compute


def ing(n, staple=False, opt=False):
    return IngredientCtx(name=n, normalized_name=n, category="other", is_staple=staple, is_optional=opt)


def test_staples_ignored_and_ratio():
    r = compute(
        [ing("spinach"), ing("paneer"), ing("cream", opt=True), ing("salt", staple=True)], {"spinach", "paneer"}
    )
    assert r.coverage == 2 / 3
    assert r.covered == ["spinach", "paneer"]
    assert [m.name for m in r.missing] == ["cream"] and r.missing[0].is_optional is True


def test_empty_countable_is_full():
    assert compute([ing("salt", staple=True)], set()).coverage == 1.0


def test_token_match_reports_pantry_name():
    r = compute([IngredientCtx(name="Paneer cubes", normalized_name="paneer cube", category="dairy")], {"paneer"})
    assert r.coverage == 1.0 and r.covered == ["paneer"]

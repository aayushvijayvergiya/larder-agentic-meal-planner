from larder.agents.categorize.keyword_map import (
    CATEGORY_LABELS,
    CATEGORY_ORDER,
    KEYWORDS,
    SUGGESTIONS,
    keyword_category,
)


def test_map_size_and_values():
    assert len(KEYWORDS) >= 250
    assert set(KEYWORDS.values()) <= set(CATEGORY_ORDER)
    assert KEYWORDS["paneer"] == "dairy"
    assert KEYWORDS["toor dal"] == "pulses"
    assert KEYWORDS["cumin"] == "spices"
    assert len(SUGGESTIONS) >= 60
    assert all(c in CATEGORY_ORDER for _, c in SUGGESTIONS)
    assert set(CATEGORY_LABELS) == set(CATEGORY_ORDER)


def test_token_hits():
    assert keyword_category("red onion") == "vegetables"
    assert keyword_category("organic toor dal") == "pulses"
    assert keyword_category("gundruk") is None
    assert keyword_category("") is None

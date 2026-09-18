import pytest

from larder.services.normalize import ingredient_matches_pantry, normalize_name, slugify, tokens


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Fresh Spinach leaves", "spinach leaf"),
        ("Tomatoes", "tomato"),
        ("Paneer cubes", "paneer cube"),
        ("2 cups of basmati rice", "2 basmati rice"),
        ("Toor Dal", "toor dal"),
        ("chillies", "chillie"),
        ("  Ghee ", "ghee"),
        ("Jalapeños", "jalapeno"),
        ("", ""),
    ],
)
def test_normalize(raw, expected):
    assert normalize_name(raw) == expected


def test_match_exact_then_token_subset():
    pantry = {"paneer", "spinach", "basmati rice", "rice"}
    assert ingredient_matches_pantry("paneer cube", pantry) == "paneer"
    assert ingredient_matches_pantry("basmati rice", pantry) == "basmati rice"
    assert ingredient_matches_pantry("cooked basmati rice", pantry) == "basmati rice"  # most specific wins
    assert ingredient_matches_pantry("cream", pantry) is None
    assert ingredient_matches_pantry("", pantry) is None


def test_tokens_and_slugify():
    assert tokens("Fresh green chillies") == {"green", "chillie"}
    assert slugify("North Indian") == "north_indian"
    assert slugify("  Weight loss! ") == "weight_loss"

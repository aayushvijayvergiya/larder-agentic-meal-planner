"""Ingredient and pantry name normalisation (LLD §7.1)."""

import re
import unicodedata

_STOP = {
    "fresh",
    "chopped",
    "sliced",
    "diced",
    "ground",
    "whole",
    "large",
    "small",
    "medium",
    "cup",
    "cups",
    "tbsp",
    "tsp",
    "of",
    "a",
    "the",
}


_IRREGULAR = {"leaves": "leaf", "loaves": "loaf", "halves": "half", "knives": "knife", "shelves": "shelf"}


def _singular(word: str) -> str:
    if word in _IRREGULAR:
        return _IRREGULAR[word]
    if len(word) <= 3 or not word.endswith("s") or word.endswith(("ss", "us", "is")):
        return word
    if word.endswith("oes"):
        return word[:-2]  # tomatoes -> tomato
    if word.endswith(("ches", "shes", "xes", "sses")):
        return word[:-2]  # radishes -> radish, peaches -> peach
    return word[:-1]


def normalize_name(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    words = [w for w in s.split() if w not in _STOP]
    return " ".join(_singular(w) for w in words)


def slugify(s: str) -> str:
    """Lowercase slug with underscores, for cuisines and goals."""
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s


def tokens(s: str) -> set[str]:
    return set(normalize_name(s).split())


def ingredient_matches_pantry(ingredient_norm: str, pantry_norms: set[str]) -> str | None:
    """Exact match first; otherwise the pantry item whose tokens are a subset of the ingredient's tokens.

    When several pantry items match, the one with the most tokens (most specific) wins.
    """
    if ingredient_norm in pantry_norms:
        return ingredient_norm
    ing_tokens = set(ingredient_norm.split())
    if not ing_tokens:
        return None
    best: str | None = None
    best_len = 0
    for p in pantry_norms:
        p_tokens = set(p.split())
        if p_tokens and p_tokens <= ing_tokens and len(p_tokens) > best_len:
            best, best_len = p, len(p_tokens)
    return best

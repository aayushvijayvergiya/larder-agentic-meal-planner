"""Medical condition -> planning rules (LLD §7.3). Hard rules become validator violations; soft ones become warnings
and prompt text. This is a POC heuristic, not medical advice."""

import re
from dataclasses import dataclass, field


@dataclass
class MedicalRules:
    hard_allergens: set[str] = field(default_factory=set)
    avoid_tokens: set[str] = field(default_factory=set)
    notes: list[str] = field(default_factory=list)

    def merge(self, other: "MedicalRules") -> "MedicalRules":
        return MedicalRules(
            hard_allergens=self.hard_allergens | other.hard_allergens,
            avoid_tokens=self.avoid_tokens | other.avoid_tokens,
            notes=self.notes + [n for n in other.notes if n not in self.notes],
        )


_RULES: list[tuple[re.Pattern[str], set[str], set[str], str]] = [
    (
        re.compile(r"diabet"),
        set(),
        {"sugar", "jaggery", "honey", "maida", "white bread"},
        "keep added sugar and refined flour low",
    ),
    (re.compile(r"hypertension|blood pressure"), set(), {"pickle", "papad", "processed meat"}, "keep salt moderate"),
    (re.compile(r"celiac|gluten"), {"gluten"}, set(), "strictly gluten free"),
    (re.compile(r"lactose"), {"dairy"}, set(), "no dairy"),
    (re.compile(r"gout"), set(), {"organ meat", "shellfish"}, "avoid purine-heavy foods"),
    (re.compile(r"kidney|ckd"), set(), {"banana", "potato skin", "tomato ketchup"}, "watch potassium"),
    (re.compile(r"cholesterol"), set(), {"ghee", "butter", "cream", "fried"}, "limit saturated fat"),
    (re.compile(r"pcos|pcod"), set(), {"sugar", "maida", "white bread"}, "prefer low glycaemic meals"),
]


def rules_for(conditions: list[dict] | None) -> MedicalRules:
    rules = MedicalRules()
    for cond in conditions or []:
        name = str(cond.get("name", "") if isinstance(cond, dict) else cond).lower()
        for pattern, hard, avoid, note in _RULES:
            if pattern.search(name):
                rules = rules.merge(MedicalRules(hard_allergens=set(hard), avoid_tokens=set(avoid), notes=[note]))
    return rules

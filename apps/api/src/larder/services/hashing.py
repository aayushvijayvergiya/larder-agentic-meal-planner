"""Planner inputs hash (LLD §7.4). Feedback is deliberately excluded."""

import hashlib
import json

from larder.agents.planner.state import PlanningContext


def compute_inputs_hash(ctx: PlanningContext) -> str:
    payload = {
        "pantry": sorted(p.normalized_name for p in ctx.pantry if p.is_available),
        "members": [
            {
                "id": str(m.id),
                "diet": m.diet_type,
                "allergens": sorted(m.allergens),
                "dislikes": sorted(m.dislikes),
                "likes": sorted(m.likes),
                "cuisines": sorted(m.cuisines),
                "medical": sorted(str(c.get("name", "")) for c in m.medical_conditions),
                "max_prep": m.max_prep_minutes,
                "goals": sorted(m.goals),
            }
            for m in sorted(ctx.members, key=lambda m: str(m.id))
        ],
        "slots": [s.key for s in ctx.slots],
        "library_version": ctx.library_count_and_max_updated,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()

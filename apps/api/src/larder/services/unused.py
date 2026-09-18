"""Pantry items no planned meal touches (LLD §7.8)."""

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from larder.db.models import PantryItem

EXCLUDED_CATEGORIES = {"spices", "condiments", "oils"}
MAX_ITEMS = 8


def unused_from(pantry, entries, today: date) -> list[dict]:
    used: set[str] = set()
    for e in entries:
        if e.date >= today:
            used |= set(e.covered_ingredients)
    out = [
        {"name": p.name, "category": p.category}
        for p in pantry
        if p.is_available and p.category not in EXCLUDED_CATEGORIES and p.normalized_name not in used
    ]
    out.sort(key=lambda x: x["name"].lower())
    return out[:MAX_ITEMS]


async def unused_pantry_items(session: AsyncSession, household_id: uuid.UUID, entries, today: date) -> list[dict]:
    pantry = (await session.scalars(select(PantryItem).where(PantryItem.household_id == household_id))).all()
    return unused_from(pantry, entries, today)

"""Pantry service (LLD §6.6)."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from larder.agents.categorize.categorize import categorize
from larder.agents.categorize.keyword_map import CATEGORY_LABELS, CATEGORY_ORDER, SUGGESTIONS
from larder.db.models import PantryItem
from larder.errors import conflict, not_found
from larder.llm.base import LLM
from larder.schemas.pantry import PantryItemIn, PantryItemPatch
from larder.services.normalize import normalize_name


async def list_items(session: AsyncSession, household_id: uuid.UUID) -> list[PantryItem]:
    rows = await session.scalars(
        select(PantryItem).where(PantryItem.household_id == household_id).order_by(PantryItem.name)
    )
    return list(rows.all())


async def list_grouped(session: AsyncSession, household_id: uuid.UUID) -> list[tuple[str, str, list[PantryItem]]]:
    items = await list_items(session, household_id)
    by_cat: dict[str, list[PantryItem]] = {}
    for item in items:
        by_cat.setdefault(item.category, []).append(item)
    return [(c, CATEGORY_LABELS[c], by_cat[c]) for c in CATEGORY_ORDER if c in by_cat]


async def add_items(
    session: AsyncSession,
    llm: LLM,
    household_id: uuid.UUID,
    added_by: uuid.UUID,
    items: list[PantryItemIn],
) -> tuple[list[PantryItem], list[PantryItem]]:
    wanted: dict[str, PantryItemIn] = {}
    for item in items:
        norm = normalize_name(item.name)
        if norm and norm not in wanted:
            wanted[norm] = item
    if not wanted:
        return [], []

    existing_rows = (
        await session.scalars(
            select(PantryItem).where(
                PantryItem.household_id == household_id, PantryItem.normalized_name.in_(list(wanted))
            )
        )
    ).all()
    existing: list[PantryItem] = []
    for row in existing_rows:
        if not row.is_available:
            row.is_available = True
        existing.append(row)
        wanted.pop(row.normalized_name, None)

    uncategorised = [i.name for i in wanted.values() if i.category is None]
    assigned = await categorize(llm, uncategorised) if uncategorised else {}

    created: list[PantryItem] = []
    for norm, item in wanted.items():
        row = PantryItem(
            household_id=household_id,
            name=item.name,
            normalized_name=norm,
            category=item.category or assigned.get(item.name, "other"),
            added_by=added_by,
        )
        session.add(row)
        created.append(row)
    await session.commit()
    for row in created + existing:
        await session.refresh(row)
    return created, existing


async def _get_item(session: AsyncSession, household_id: uuid.UUID, item_id: uuid.UUID) -> PantryItem:
    item = await session.get(PantryItem, item_id)
    if item is None or item.household_id != household_id:
        raise not_found("Pantry item not found")
    return item


async def update_item(
    session: AsyncSession, household_id: uuid.UUID, item_id: uuid.UUID, patch: PantryItemPatch
) -> PantryItem:
    item = await _get_item(session, household_id, item_id)
    data = patch.model_dump(exclude_unset=True)
    if data.get("name") is not None:
        norm = normalize_name(data["name"])
        clash = await session.scalar(
            select(PantryItem.id).where(
                PantryItem.household_id == household_id,
                PantryItem.normalized_name == norm,
                PantryItem.id != item_id,
            )
        )
        if clash:
            raise conflict("You already have an item with that name")
        item.name = data["name"]
        item.normalized_name = norm
    if data.get("category") is not None:
        item.category = data["category"]
    if data.get("is_available") is not None:
        item.is_available = data["is_available"]
    await session.commit()
    await session.refresh(item)
    return item


async def delete_item(session: AsyncSession, household_id: uuid.UUID, item_id: uuid.UUID) -> None:
    item = await _get_item(session, household_id, item_id)
    await session.delete(item)
    await session.commit()


async def suggestions(session: AsyncSession, household_id: uuid.UUID) -> list[tuple[str, str]]:
    present = {i.normalized_name for i in await list_items(session, household_id)}
    return [(name, cat) for name, cat in SUGGESTIONS if normalize_name(name) not in present]

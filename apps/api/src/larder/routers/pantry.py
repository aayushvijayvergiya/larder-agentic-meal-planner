from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from larder.auth.deps import CurrentUser, require_household
from larder.db.session import get_session
from larder.schemas.pantry import (
    PantryAddRequest,
    PantryAddResponse,
    PantryCategoryGroup,
    PantryItemOut,
    PantryItemPatch,
    PantryOut,
    SuggestionItem,
    SuggestionsOut,
)
from larder.services import pantry as svc

router = APIRouter(prefix="/pantry", tags=["pantry"])


@router.get("", response_model=PantryOut)
async def get_pantry(
    user: CurrentUser = Depends(require_household), session: AsyncSession = Depends(get_session)
) -> PantryOut:
    groups = await svc.list_grouped(session, user.household_id)
    categories = [
        PantryCategoryGroup(category=c, label=label, items=[PantryItemOut.model_validate(i) for i in items])
        for c, label, items in groups
    ]
    return PantryOut(categories=categories, total=sum(len(g.items) for g in categories))


@router.get("/suggestions", response_model=SuggestionsOut)
async def get_suggestions(
    user: CurrentUser = Depends(require_household), session: AsyncSession = Depends(get_session)
) -> SuggestionsOut:
    items = await svc.suggestions(session, user.household_id)
    return SuggestionsOut(items=[SuggestionItem(name=n, category=c) for n, c in items])


@router.post("/items", response_model=PantryAddResponse, status_code=status.HTTP_201_CREATED)
async def add_items(
    body: PantryAddRequest,
    request: Request,
    user: CurrentUser = Depends(require_household),
    session: AsyncSession = Depends(get_session),
) -> PantryAddResponse:
    created, existing = await svc.add_items(
        session, request.app.state.llm, user.household_id, user.profile.id, body.items
    )
    return PantryAddResponse(
        created=[PantryItemOut.model_validate(i) for i in created],
        existing=[PantryItemOut.model_validate(i) for i in existing],
    )


@router.patch("/items/{item_id}", response_model=PantryItemOut)
async def patch_item(
    item_id: UUID,
    patch: PantryItemPatch,
    user: CurrentUser = Depends(require_household),
    session: AsyncSession = Depends(get_session),
) -> PantryItemOut:
    return PantryItemOut.model_validate(await svc.update_item(session, user.household_id, item_id, patch))


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(
    item_id: UUID,
    user: CurrentUser = Depends(require_household),
    session: AsyncSession = Depends(get_session),
) -> Response:
    await svc.delete_item(session, user.household_id, item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

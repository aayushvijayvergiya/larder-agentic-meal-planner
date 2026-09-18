import hmac

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from larder.db.session import get_session
from larder.errors import forbidden
from larder.schemas.internal import TickReport
from larder.services import scheduler

router = APIRouter(prefix="/internal", tags=["internal"])


def require_scheduler_secret(request: Request, x_scheduler_secret: str = Header(default="")) -> None:
    expected = request.app.state.settings.scheduler_secret
    if not expected or not hmac.compare_digest(x_scheduler_secret, expected):
        raise forbidden("Invalid scheduler secret")


@router.post("/scheduler/tick", response_model=TickReport, dependencies=[Depends(require_scheduler_secret)])
async def tick(
    request: Request,
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> TickReport:
    settings = request.app.state.settings
    return await scheduler.run_tick(
        session, scheduler.utcnow(), background, request.app.state.llm, history_weeks=settings.plan_history_weeks
    )

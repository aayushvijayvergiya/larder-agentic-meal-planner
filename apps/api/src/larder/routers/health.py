from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(request: Request):
    settings = request.app.state.settings
    db = "ok"
    try:
        async with request.app.state.engine.connect() as conn:
            await conn.execute(text("select 1"))
    except Exception:  # noqa: BLE001
        db = "error"
    body = {"status": "ok" if db == "ok" else "degraded", "database": db, "llm_provider": settings.llm_provider}
    if db != "ok":
        return JSONResponse(body, status_code=503)
    return body

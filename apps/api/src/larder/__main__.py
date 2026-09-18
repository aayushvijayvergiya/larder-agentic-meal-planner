"""Local dev entry point: `python -m larder`.

Uses the selector event loop on Windows because the LangGraph Postgres checkpointer (psycopg async) cannot run on
the Proactor loop uvicorn would otherwise pick. Production runs on Linux where this makes no difference.
"""

import asyncio
import os
import sys

import uvicorn


def main() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    uvicorn.run(
        "larder.main:app",
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "8000")),
        reload=os.environ.get("RELOAD", "1") == "1",
        loop="none",
    )


if __name__ == "__main__":
    main()

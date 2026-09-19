"""Local dev entry point: `python -m larder`.

Passes uvicorn an explicit selector-loop factory on Windows because the LangGraph Postgres checkpointer
(psycopg async) cannot run on the Proactor loop uvicorn would otherwise pick. This has to be a `loop=`
factory (resolved by uvicorn inside whichever process actually runs the server) rather than an
`asyncio.set_event_loop_policy()` call here: with `reload=True` (the default), uvicorn runs the real
server in a subprocess spawned via `multiprocessing`, which never executes this module's
`if __name__ == "__main__"` block, so a policy set here would never reach it. Production runs on Linux
where this makes no difference.
"""

import asyncio
import os
import sys

import uvicorn


def selector_loop_factory() -> asyncio.AbstractEventLoop:
    return asyncio.SelectorEventLoop()


def main() -> None:
    uvicorn.run(
        "larder.main:app",
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "8000")),
        reload=os.environ.get("RELOAD", "1") == "1",
        loop="larder.__main__:selector_loop_factory" if sys.platform == "win32" else "asyncio",
    )


if __name__ == "__main__":
    main()

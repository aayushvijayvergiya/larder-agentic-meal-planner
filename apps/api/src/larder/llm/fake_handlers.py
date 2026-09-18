"""Default deterministic handlers for FakeLLM, keyed by structured-output schema name (LLD §5.3).

Each agent registers its schema handler here so a fresh clone with LLM_PROVIDER=fake completes every flow.
Handlers receive the parsed <context> dict and the schema class (so this module never imports agent schemas)
and must return a valid instance.
"""

from collections.abc import Callable

from pydantic import BaseModel

Handler = Callable[[dict, type[BaseModel]], BaseModel]

DEFAULT_HANDLERS: dict[str, Handler] = {}


def handler(schema_name: str) -> Callable[[Handler], Handler]:
    def _register(fn: Handler) -> Handler:
        DEFAULT_HANDLERS[schema_name] = fn
        return fn

    return _register


def register_default_handlers(fake) -> None:
    for name, fn in DEFAULT_HANDLERS.items():
        fake.register_handler(name, fn)


@handler("CategoryAssignments")
def _category_assignments(ctx: dict, schema: type[BaseModel]) -> BaseModel:
    # The static keyword map has already handled everything it recognises; the fake knows nothing more.
    return schema(assignments=[{"name": n, "category": "other"} for n in ctx.get("names", [])])

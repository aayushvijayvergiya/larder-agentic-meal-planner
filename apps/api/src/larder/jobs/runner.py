"""In-process job runner (LLD §7.6). This is the single place to swap in a queue later.

Callers must invoke `runner.enqueue(...)` through the module attribute so tests can patch it to run inline.
"""

import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import BackgroundTasks

from larder.agents.planner.graph import run_planner
from larder.agents.planner.state import PlannerInput
from larder.db import session as db_session_module
from larder.db.models import MealPlan, PlanJob
from larder.llm.base import LLM

log = logging.getLogger("larder.jobs")


async def enqueue(job_id: UUID, background: BackgroundTasks, llm: LLM) -> None:
    background.add_task(run_job, job_id, llm)


async def run_job(job_id: UUID, llm: LLM) -> None:
    factory = db_session_module.session_factory()
    async with factory() as session:
        job = await session.get(PlanJob, job_id)
        if job is None:
            log.error("job %s not found", job_id)
            return
        plan = await session.get(MealPlan, job.plan_id)
        if plan is None:
            job.status = "failed"
            job.error = "plan not found"
            await session.commit()
            return
        job.status = "running"
        job.started_at = datetime.now(UTC)
        await session.commit()
        inp = PlannerInput(
            job_id=job.id,
            plan_id=plan.id,
            household_id=plan.household_id,
            scope=plan.scope,
            member_id=plan.member_id,
            mode=job.mode,
            start_date=plan.start_date,
            end_date=plan.end_date,
            target_date=job.target_date,
            target_slot_key=job.target_slot_key,
            target_entry_id=job.target_entry_id,
            swap_reason=job.swap_reason,
        )
    try:
        outcome = await run_planner(factory, llm, inp)
        log.info(
            "job %s ready: %s entries, attempts=%s fallback=%s",
            job_id,
            outcome.entries_written,
            outcome.attempts,
            outcome.used_fallback,
        )
    except Exception as exc:  # noqa: BLE001
        log.exception("job %s failed", job_id)
        async with factory() as session:
            job = await session.get(PlanJob, job_id)
            if job is not None:
                job.status = "failed"
                job.error = str(exc)[:2000]
                job.finished_at = datetime.now(UTC)
                await session.commit()

"""Queue inspection and cancellation never wait behind application work."""
from typing import Literal

from fastapi import APIRouter, Depends, Query

from Backend.core.protocol import to_wire


def create_job_router(runtime, authorized):
    router = APIRouter(prefix="/api", tags=["Jobs and queues"], dependencies=[Depends(authorized)])

    @router.get("/jobs")
    def list_jobs(limit: int = Query(default=50, ge=1, le=200),
                  lane: Literal["document", "image", "audio", "video"] | None = None):
        return {"jobs": to_wire(runtime.scheduler.list(lane=lane, limit=limit))}

    @router.get("/jobs/{job_id}")
    def get_job(job_id: str):
        return {"job": to_wire(runtime.scheduler.get(job_id))}

    @router.post("/jobs/{job_id}/cancel")
    def cancel_job(job_id: str):
        return {"job": to_wire(runtime.scheduler.cancel(job_id))}

    @router.get("/queues")
    def queues():
        return {"queues": to_wire(runtime.scheduler.lanes())}

    return router

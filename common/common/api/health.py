# -*- coding: utf-8 -*-
"""
    common.api.health
    ~~~~~~~~~~~~~~~~~

    Healthcheck endpoint.
"""

from datetime import datetime

from dateutil import tz
from fastapi import status
from fastapi.responses import Response
from fastapi.routing import APIRouter
from psutil import cpu_percent, disk_usage, virtual_memory
from pydantic import BaseModel

router = APIRouter()


class HealthService(BaseModel):
    checker: str
    output: str
    passed: bool


class Health(BaseModel):
    results: list[HealthService]
    status: str
    timestamp: float


@router.get(
    "/health",
    response_model=Health,
    status_code=status.HTTP_200_OK,
    summary="Healthcheck endpoint",
)
def get_health(response: Response) -> Health:
    results = [
        cpu_checker(),
        disk_checker(),
        memory_checker(),
    ]

    if all(r.passed for r in results):
        r_status = "success"
    else:
        r_status = "failed"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return Health(
        results=results,
        status=r_status,
        timestamp=datetime.now(tz=tz.UTC).timestamp(),
    )


def cpu_checker() -> HealthService:
    return HealthService(
        checker=cpu_checker.__name__,
        output=str(cpu := cpu_percent()),
        passed=cpu < 90,
    )


def disk_checker() -> HealthService:
    return HealthService(
        checker=disk_checker.__name__,
        output=str(disk := disk_usage("/").percent),
        passed=disk < 90,
    )


def memory_checker() -> HealthService:
    return HealthService(
        checker=memory_checker.__name__,
        output=str(mem := virtual_memory().percent),
        passed=mem < 90,
    )

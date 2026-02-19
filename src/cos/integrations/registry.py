"""Integration registry and health checks."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum

import structlog

log = structlog.get_logger("integrations.registry")


class HealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNCONFIGURED = "unconfigured"


@dataclass
class IntegrationHealth:
    name: str
    status: HealthStatus
    message: str = ""


@dataclass
class IntegrationRegistry:
    """Registry of available integrations and their health check functions."""

    _checks: dict[str, Callable[[], Awaitable[IntegrationHealth]]] = field(default_factory=dict)

    def register(self, name: str, check: Callable[[], Awaitable[IntegrationHealth]]) -> None:
        self._checks[name] = check

    async def check_all(self) -> list[IntegrationHealth]:
        results = []
        for name, check in self._checks.items():
            try:
                result = await check()
                results.append(result)
            except Exception as e:
                results.append(
                    IntegrationHealth(name=name, status=HealthStatus.UNHEALTHY, message=str(e))
                )
        return results

    async def check(self, name: str) -> IntegrationHealth:
        if name not in self._checks:
            return IntegrationHealth(
                name=name, status=HealthStatus.UNCONFIGURED, message="Not registered"
            )
        try:
            return await self._checks[name]()
        except Exception as e:
            return IntegrationHealth(name=name, status=HealthStatus.UNHEALTHY, message=str(e))


# Global registry
registry = IntegrationRegistry()

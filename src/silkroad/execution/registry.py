from __future__ import annotations

from collections.abc import Callable
from typing import Dict

from .base import ExecutionEngine

ExecutionFactory = Callable[..., ExecutionEngine]

EXECUTION_REGISTRY: Dict[str, ExecutionFactory] = {}


def register_execution_engine(name: str) -> Callable[[ExecutionFactory], ExecutionFactory]:
    def decorator(factory: ExecutionFactory) -> ExecutionFactory:
        EXECUTION_REGISTRY[name] = factory
        return factory

    return decorator

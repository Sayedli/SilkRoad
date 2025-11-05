from __future__ import annotations

from collections.abc import Callable
from typing import Dict, Type

from .base import Strategy

StrategyFactory = Callable[..., Strategy]

STRATEGY_REGISTRY: Dict[str, StrategyFactory] = {}


def register_strategy(name: str) -> Callable[[StrategyFactory], StrategyFactory]:
    def decorator(factory: StrategyFactory) -> StrategyFactory:
        STRATEGY_REGISTRY[name] = factory
        return factory

    return decorator

from __future__ import annotations

from abc import ABC, abstractmethod


class Notifier(ABC):
    @abstractmethod
    def send(self, message: str) -> None: ...


class PrintNotifier(Notifier):
    def send(self, message: str) -> None:
        print(f"[SilkRoad] {message}")

"""
Event and RPC Message Bus for Automotive Service-Oriented Architecture (SOA).
Simulates SOME/IP or Android Binder/CarService IPC messaging.
"""

from typing import Callable, Dict, List, Any
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


class SystemBus:
    """Lightweight publish-subscribe and service registry bus."""

    def __init__(self):
        self._subscribers: Dict[str, List[Callable[[Any], None]]] = {}
        self._event_log: List[Dict[str, Any]] = []

    def subscribe(self, topic: str, callback: Callable[[Any], None]) -> None:
        if topic not in self._subscribers:
            self._subscribers[topic] = []
        self._subscribers[topic].append(callback)

    def publish(self, topic: str, payload: Any = None) -> None:
        entry = {"topic": topic, "payload": payload}
        self._event_log.append(entry)
        if topic in self._subscribers:
            for callback in self._subscribers[topic]:
                try:
                    callback(payload)
                except Exception as ex:
                    logging.error(f"Error handling event {topic}: {ex}")

    def get_event_log(self) -> List[Dict[str, Any]]:
        return list(self._event_log)

    def clear_log(self) -> None:
        self._event_log.clear()

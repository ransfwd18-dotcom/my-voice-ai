from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseEngine(ABC):
    name = "Base Engine"

    @abstractmethod
    def analyze(self, text: str, context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """
        Analyze text and return the engine's recommendations.
        """
        raise NotImplementedError

    def is_available(self) -> bool:
        return True

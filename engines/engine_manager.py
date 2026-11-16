from typing import Any, Dict, List

from core.engine_registry import EngineRegistry
from engines.base_engine import BaseEngine


class EngineManager:
    def __init__(self, registry: EngineRegistry | None = None):
        self.registry = registry or EngineRegistry()
        self.instances: Dict[str, BaseEngine] = {}

    def register_engine(self, engine: BaseEngine):
        self.instances[engine.name] = engine
        self.registry.register(
            engine.name,
            description=engine.__class__.__doc__ or "",
            enabled=True,
        )

    def analyze_all(
        self,
        text: str,
        context: Dict[str, Any] | None = None,
    ) -> List[Dict[str, Any]]:
        results = []

        for name, engine in self.instances.items():
            if not self.registry.engines.get(name, None):
                continue

            if not self.registry.engines[name].enabled:
                continue

            if not engine.is_available():
                continue

            result = engine.analyze(text, context or {})
            if result:
                results.append({
                    "engine": name,
                    "recommendation": result,
                })

        return results

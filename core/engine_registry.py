from dataclasses import dataclass
from typing import Dict


@dataclass
class EngineInfo:
    name: str
    enabled: bool = True
    description: str = ""


class EngineRegistry:
    def __init__(self):
        self.engines: Dict[str, EngineInfo] = {}

    def register(self, name: str, description: str = "", enabled: bool = True):
        self.engines[name] = EngineInfo(
            name=name,
            enabled=enabled,
            description=description,
        )

    def enable(self, name: str):
        if name in self.engines:
            self.engines[name].enabled = True

    def disable(self, name: str):
        if name in self.engines:
            self.engines[name].enabled = False

    def get_enabled(self) -> Dict[str, EngineInfo]:
        return {
            name: engine
            for name, engine in self.engines.items()
            if engine.enabled
        }

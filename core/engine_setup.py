import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.engine_registry import EngineRegistry
from engines.engine_manager import EngineManager
from engines.voice_intelligence import VoiceIntelligenceEngine


def create_engine_manager():
    registry = EngineRegistry()
    manager = EngineManager(registry)

    manager.register_engine(VoiceIntelligenceEngine())

    return manager


if __name__ == "__main__":
    manager = create_engine_manager()

    print("ENGINE SYSTEM READY")
    for name, info in manager.registry.get_enabled().items():
        print(f"- {name}: enabled={info.enabled}")

from typing import Any, Dict

from engines.engine_manager import EngineManager
from master_director import MasterNarrationDirector


class DirectorBridge:
    """
    Connects intelligence engines to the Master Narration Director.
    """

    def __init__(
        self,
        engine_manager: EngineManager,
        director: MasterNarrationDirector,
    ):
        self.engine_manager = engine_manager
        self.director = director

    def analyze_and_resolve(
        self,
        text: str,
        context: Dict[str, Any] | None = None,
    ):
        recommendations = self.engine_manager.analyze_all(
            text,
            context or {},
        )

        self.director.reset()

        for item in recommendations:
            recommendation = item["recommendation"]

            self.director.add_recommendation(
                engine=item["engine"],
                speed=recommendation.get("speed", 0.0),
                pitch=recommendation.get("pitch", 0.0),
                volume=recommendation.get("volume", 0.0),
                pauses=recommendation.get("pauses", 0.0),
                emphasis=recommendation.get("emphasis", 0.0),
                confidence=recommendation.get("confidence", 0.0),
                reason=recommendation.get("reason", ""),
            )

        return self.director.resolve()

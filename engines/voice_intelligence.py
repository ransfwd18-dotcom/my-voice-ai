from typing import Any, Dict

from engines.base_engine import BaseEngine


class VoiceIntelligenceEngine(BaseEngine):
    """
    Analyzes text for basic voice-delivery recommendations.
    """

    name = "Voice Intelligence"

    def analyze(
        self,
        text: str,
        context: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        text = text.strip()
        words = text.split()

        recommendation = {
            "speed": 0.0,
            "pitch": 0.0,
            "volume": 0.0,
            "pauses": 0.0,
            "emphasis": 0.0,
            "confidence": 60.0,
            "reason": "Baseline voice intelligence analysis.",
        }

        if len(words) > 35:
            recommendation["speed"] = -5.0
            recommendation["pauses"] = 150.0
            recommendation["reason"] = "Long text detected; slightly slower delivery recommended."

        if "!" in text:
            recommendation["emphasis"] = 10.0
            recommendation["pitch"] = 3.0
            recommendation["reason"] = "Exclamation detected; slightly stronger emphasis recommended."

        if "?" in text:
            recommendation["pitch"] = 4.0
            recommendation["reason"] = "Question detected; rising vocal movement recommended."

        return recommendation

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class SpeechDecision:
    speed: float = 0.0
    pitch: float = 0.0
    volume: float = 0.0
    pauses: float = 0.0
    emphasis: float = 0.0
    confidence: float = 0.0
    reasons: List[str] = field(default_factory=list)


class MasterNarrationDirector:
    """
    Master decision layer for My Voice AI.

    The Director receives:
        1. A baseline speech decision.
        2. Recommendations from individual intelligence engines.

    It resolves those recommendations into one final speech decision.

    Engine recommendations are treated as DELTAS from the baseline,
    not as replacement values.
    """

    LIMITS = {
        "speed": (-50.0, 50.0),
        "pitch": (-50.0, 50.0),
        "volume": (-50.0, 50.0),
        "pauses": (0.0, 5000.0),
        "emphasis": (0.0, 100.0),
        "confidence": (0.0, 100.0),
    }

    def __init__(self):
        self.recommendations: Dict[str, SpeechDecision] = {}
        self.baseline = SpeechDecision()

    def reset(self):
        """Clear recommendations and reset the baseline."""
        self.recommendations.clear()
        self.baseline = SpeechDecision()

    def set_baseline(
        self,
        speed: float = 0.0,
        pitch: float = 0.0,
        volume: float = 0.0,
        pauses: float = 0.0,
        emphasis: float = 0.0,
        confidence: float = 0.0,
        reasons: List[str] = None,
    ):
        """
        Set the starting speech values before engine recommendations
        are resolved.
        """

        self.baseline = SpeechDecision(
            speed=float(speed),
            pitch=float(pitch),
            volume=float(volume),
            pauses=float(pauses),
            emphasis=float(emphasis),
            confidence=float(confidence),
            reasons=list(reasons or []),
        )

    def add_recommendation(
        self,
        engine: str,
        speed: float = 0.0,
        pitch: float = 0.0,
        volume: float = 0.0,
        pauses: float = 0.0,
        emphasis: float = 0.0,
        confidence: float = 0.0,
        reason: str = "",
    ):
        """
        Add or replace an engine recommendation.

        Engine values are treated as DELTAS from the baseline.
        Confidence determines how strongly the recommendation participates
        in the final weighted resolution.
        """

        self.recommendations[engine] = SpeechDecision(
            speed=float(speed),
            pitch=float(pitch),
            volume=float(volume),
            pauses=float(pauses),
            emphasis=float(emphasis),
            confidence=float(confidence),
            reasons=[reason] if reason else [],
        )

    def _clamp(self, name: str, value: float) -> float:
        minimum, maximum = self.LIMITS[name]
        return max(minimum, min(maximum, value))

    def resolve(self) -> SpeechDecision:
        """
        Resolve the baseline plus weighted engine recommendations.

        Each engine contributes a weighted DELTA.

        Example:

            Baseline speed = 10
            Mood           = +8
            Pacing         = -4
            Excitement     = +12

        The Director calculates the weighted combined adjustment and
        applies it to the baseline.
        """

        if not self.recommendations:
            return SpeechDecision(
                speed=self._clamp("speed", self.baseline.speed),
                pitch=self._clamp("pitch", self.baseline.pitch),
                volume=self._clamp("volume", self.baseline.volume),
                pauses=self._clamp("pauses", self.baseline.pauses),
                emphasis=self._clamp("emphasis", self.baseline.emphasis),
                confidence=self._clamp("confidence", self.baseline.confidence),
                reasons=list(self.baseline.reasons),
            )

        decisions = list(self.recommendations.values())

        total_weight = 0.0

        delta_speed = 0.0
        delta_pitch = 0.0
        delta_volume = 0.0
        delta_pauses = 0.0
        delta_emphasis = 0.0
        recommendation_confidence = 0.0

        reasons = list(self.baseline.reasons)

        for decision in decisions:
            weight = max(1.0, abs(decision.confidence))

            delta_speed += decision.speed * weight
            delta_pitch += decision.pitch * weight
            delta_volume += decision.volume * weight
            delta_pauses += decision.pauses * weight
            delta_emphasis += decision.emphasis * weight

            recommendation_confidence += decision.confidence * weight
            total_weight += weight

            reasons.extend(decision.reasons)

        if total_weight:
            delta_speed /= total_weight
            delta_pitch /= total_weight
            delta_volume /= total_weight
            delta_pauses /= total_weight
            delta_emphasis /= total_weight
            recommendation_confidence /= total_weight

        final_speed = self.baseline.speed + delta_speed
        final_pitch = self.baseline.pitch + delta_pitch
        final_volume = self.baseline.volume + delta_volume
        final_pauses = self.baseline.pauses + delta_pauses
        final_emphasis = self.baseline.emphasis + delta_emphasis

        final_confidence = max(
            self.baseline.confidence,
            recommendation_confidence
        )

        return SpeechDecision(
            speed=self._clamp("speed", final_speed),
            pitch=self._clamp("pitch", final_pitch),
            volume=self._clamp("volume", final_volume),
            pauses=self._clamp("pauses", final_pauses),
            emphasis=self._clamp("emphasis", final_emphasis),
            confidence=self._clamp("confidence", final_confidence),
            reasons=reasons,
        )


def create_director():
    return MasterNarrationDirector()
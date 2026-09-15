"""Flood risk classification using configurable depth thresholds."""
from enum import Enum
from ...config import settings


class Severity(str, Enum):
    SAFE = "SAFE"
    MINOR = "MINOR"
    HIGH = "HIGH"
    SEVERE = "SEVERE"
    CRITICAL = "CRITICAL"


class FloodClassifier:
    def __init__(self, levels=None):
        levels = levels or settings.flood_levels
        self.safe_cm = levels["level_0_safe"]
        self.minor_cm = levels["level_1_minor"]
        self.high_cm = levels["level_2_high"]
        self.severe_cm = levels["level_3_severe"]

    def classify(self, depth_cm: float) -> Severity:
        if depth_cm <= self.safe_cm:
            return Severity.SAFE
        if depth_cm <= self.minor_cm:
            return Severity.MINOR
        if depth_cm <= self.high_cm:
            return Severity.HIGH
        if depth_cm <= self.severe_cm:
            return Severity.SEVERE
        return Severity.CRITICAL

    def thresholds(self) -> dict:
        return {
            "level_0_safe": self.safe_cm,
            "level_1_minor": self.minor_cm,
            "level_2_high": self.high_cm,
            "level_3_severe": self.severe_cm,
        }
import pytest

from app.simulation.risk.classifier import FloodClassifier, Severity


@pytest.fixture(scope="module")
def classifier() -> FloodClassifier:
    return FloodClassifier()


def test_classify_levels(classifier):
    assert classifier.classify(0) is Severity.SAFE
    assert classifier.classify(5) is Severity.SAFE
    assert classifier.classify(6) is Severity.MINOR
    assert classifier.classify(15) is Severity.MINOR
    assert classifier.classify(16) is Severity.HIGH
    assert classifier.classify(30) is Severity.HIGH
    assert classifier.classify(31) is Severity.SEVERE
    assert classifier.classify(50) is Severity.SEVERE
    assert classifier.classify(51) is Severity.CRITICAL
    assert classifier.classify(200) is Severity.CRITICAL


def test_classify_negative_depth(classifier):
    assert classifier.classify(-5) is Severity.SAFE


def test_thresholds_present(classifier):
    t = classifier.thresholds()
    assert t["level_0_safe"] == 5
    assert t["level_3_severe"] == 50
"""Tests for classifier module."""

import pytest
from ml.classifier import FragmentClassifier
from ml.features import extract_features
from ml.train import build_training_data, evaluate_model, train_and_evaluate, train_model


def test_classifier_module_imported():
    """Verify ML classifier and features are importable."""
    assert callable(extract_features)
    assert FragmentClassifier is not None


def _source_fragments():
    return {
        f"source-{source}": [
            bytes([source, 10 + source]) * 20,
            bytes([source, 20 + source]) * 20,
            bytes([source, 30 + source]) * 20,
        ]
        for source in range(4)
    }


def test_model_training_and_prediction_score_range():
    pairs, labels, _ = build_training_data(_source_fragments())
    model = train_model(pairs, labels)

    score = model.predict_score(*pairs[0])

    assert 0.0 <= score <= 1.0


def test_source_grouped_evaluation_reports_metrics():
    model, metrics = train_and_evaluate(_source_fragments())

    assert model is not None
    assert set(metrics) == {"accuracy", "precision", "recall", "f1"}
    assert all(0.0 <= value <= 1.0 for value in metrics.values())


def test_evaluate_model_rejects_empty_input():
    pairs, labels, _ = build_training_data(_source_fragments())
    model = train_model(pairs, labels)

    with pytest.raises(ValueError):
        evaluate_model(model, [], [])


def test_training_rejects_empty_or_single_class_input():
    with pytest.raises(ValueError):
        train_model([], [])

    with pytest.raises(ValueError):
        train_model([(b"a", b"b")], [1])


def test_grouped_evaluation_rejects_single_source():
    with pytest.raises(ValueError):
        train_and_evaluate({"only-source": [b"a", b"b"]})

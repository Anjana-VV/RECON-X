"""Small Random Forest model for fragment-pair compatibility."""

from collections.abc import Mapping, Sequence

from sklearn.ensemble import RandomForestClassifier

from ml.features import extract_pair_features


PAIR_FEATURE_NAMES = tuple(extract_pair_features(b"", b"").keys())


def _vectorize(pair: tuple[bytes, bytes] | Sequence[bytes]) -> list[float]:
    features = extract_pair_features(pair[0], pair[1])
    return [float(features[name]) for name in PAIR_FEATURE_NAMES]


class FragmentCompatibilityModel:
    """Random Forest predictor for the Fragment Compatibility Score."""

    def __init__(self, random_state: int = 42, n_estimators: int = 32):
        self.model = RandomForestClassifier(
            n_estimators=n_estimators,
            random_state=random_state,
            max_depth=6,
        )
        self._fitted = False

    def fit(self, pairs: Sequence[tuple[bytes, bytes]], labels: Sequence[int]):
        if not pairs or not labels or len(pairs) != len(labels):
            raise ValueError("pairs and labels must be non-empty and have equal length")
        if len(set(labels)) < 2:
            raise ValueError("training requires both compatibility classes")
        self.model.fit([_vectorize(pair) for pair in pairs], labels)
        self._fitted = True
        return self

    def predict_score(self, fragment_a: bytes, fragment_b: bytes) -> float:
        """Return the Fragment Compatibility Score in [0.0, 1.0]."""
        if not self._fitted:
            raise ValueError("model must be fitted before prediction")
        probabilities = self.model.predict_proba([_vectorize((fragment_a, fragment_b))])[0]
        class_index = list(self.model.classes_).index(1)
        return float(max(0.0, min(1.0, probabilities[class_index])))

    def predict_scores(self, pairs: Sequence[tuple[bytes, bytes]]) -> list[float]:
        if not pairs:
            raise ValueError("pairs must be non-empty")
        return [self.predict_score(first, second) for first, second in pairs]


# Retain the existing importable class for compatibility with earlier phases.
class FragmentClassifier:
    """Optional JPEG fragment classifier placeholder."""
    pass

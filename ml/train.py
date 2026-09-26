"""Offline training and evaluation for fragment-pair compatibility."""

from collections.abc import Mapping, Sequence

from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import GroupShuffleSplit

from ml.classifier import FragmentCompatibilityModel


Pair = tuple[bytes, bytes]


def build_training_data(
    source_fragments: Mapping[str, Sequence[bytes]],
) -> tuple[list[Pair], list[int], list[str]]:
    """Build positive/negative pairs while retaining original source groups."""
    pairs: list[Pair] = []
    labels: list[int] = []
    groups: list[str] = []
    for source_id, fragments in source_fragments.items():
        if len(fragments) < 2:
            continue
        for index in range(len(fragments) - 1):
            pairs.append((fragments[index], fragments[index + 1]))
            labels.append(1)
            groups.append(source_id)
            pairs.append((fragments[index + 1], fragments[index]))
            labels.append(0)
            groups.append(source_id)
        for index in range(len(fragments) - 2):
            pairs.append((fragments[index], fragments[index + 2]))
            labels.append(0)
            groups.append(source_id)
    if not pairs or len(set(labels)) < 2:
        raise ValueError("training data requires sources with at least two fragments")
    return pairs, labels, groups


def train_model(
    pairs: Sequence[Pair],
    labels: Sequence[int],
) -> FragmentCompatibilityModel:
    """Train a small compatibility model on supplied offline pair data."""
    return FragmentCompatibilityModel().fit(pairs, labels)


def evaluate_model(
    model: FragmentCompatibilityModel,
    pairs: Sequence[Pair],
    labels: Sequence[int],
) -> dict[str, float]:
    if not pairs or len(pairs) != len(labels):
        raise ValueError("pairs and labels must be non-empty and have equal length")
    scores = model.predict_scores(pairs)
    predictions = [int(score >= 0.5) for score in scores]
    return {
        "accuracy": float(accuracy_score(labels, predictions)),
        "precision": float(precision_score(labels, predictions, zero_division=0)),
        "recall": float(recall_score(labels, predictions, zero_division=0)),
        "f1": float(f1_score(labels, predictions, zero_division=0)),
    }


def train_and_evaluate(
    source_fragments: Mapping[str, Sequence[bytes]],
    test_size: float = 0.25,
    random_state: int = 42,
) -> tuple[FragmentCompatibilityModel, dict[str, float]]:
    """Train/test split by original source image and return metrics."""
    pairs, labels, groups = build_training_data(source_fragments)
    if len(set(groups)) < 2:
        raise ValueError("source-grouped evaluation requires at least two source images")
    splitter = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=random_state)
    train_indices, test_indices = next(splitter.split(pairs, labels, groups=groups))
    model = train_model([pairs[index] for index in train_indices], [labels[index] for index in train_indices])
    return model, evaluate_model(model, [pairs[index] for index in test_indices], [labels[index] for index in test_indices])


if __name__ == "__main__":
    train_model()

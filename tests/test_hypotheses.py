"""Tests for bounded fragment compatibility hypotheses."""

import io

from PIL import Image

from ml.hypotheses import generate_hypotheses


class StubCompatibilityModel:
    def predict_score(self, first: bytes, second: bytes) -> float:
        return 0.9


def _jpeg_bytes() -> bytes:
    image = Image.new("RGB", (32, 32), color=(80, 120, 160))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


def _fragments(tmp_path, data: bytes):
    split = len(data) // 2
    first = tmp_path / "fragment-a.bin"
    second = tmp_path / "fragment-b.bin"
    first.write_bytes(data[:split])
    second.write_bytes(data[split:])
    return [
        {"fragment_id": "F1", "chunk_index": 0, "output_path": str(first)},
        {"fragment_id": "F2", "chunk_index": 1, "output_path": str(second)},
    ]


def test_supported_hypothesis_uses_deterministic_validation(tmp_path):
    fragments = _fragments(tmp_path, _jpeg_bytes())

    hypotheses = generate_hypotheses(fragments, StubCompatibilityModel(), tmp_path / "out", max_hypotheses=1)

    assert len(hypotheses) == 1
    assert hypotheses[0]["status"] == "SUPPORTED"
    assert hypotheses[0]["fragment_ids"] == ["F1", "F2"]
    assert hypotheses[0]["compatibility_scores"] == [0.9]
    assert hypotheses[0]["validation"]["structure_valid"] is True
    assert hypotheses[0]["reconstruction"]["status"] == "RECONSTRUCTED"


def test_high_compatibility_invalid_reconstruction_is_rejected(tmp_path):
    fragments = _fragments(tmp_path, b"not a jpeg" * 20)

    hypotheses = generate_hypotheses(fragments, StubCompatibilityModel(), tmp_path / "out", max_hypotheses=1)

    assert hypotheses[0]["compatibility_score"] == 0.9
    assert hypotheses[0]["status"] == "REJECTED"
    assert hypotheses[0]["validation"]["structure_valid"] is False


def test_missing_fragment_is_partial(tmp_path):
    fragments = _fragments(tmp_path, _jpeg_bytes())[:1]

    hypotheses = generate_hypotheses(
        fragments,
        StubCompatibilityModel(),
        tmp_path / "out",
        total_expected_chunks=2,
    )

    assert hypotheses[0]["status"] == "PARTIAL"
    assert hypotheses[0]["reconstruction"]["status"] == "PARTIAL"


def test_hypothesis_count_is_bounded(tmp_path):
    fragments = _fragments(tmp_path, _jpeg_bytes())
    extra = dict(fragments[1], fragment_id="F3", chunk_index=2)
    fragments.append(extra)

    hypotheses = generate_hypotheses(fragments, StubCompatibilityModel(), tmp_path / "out", max_hypotheses=2)

    assert len(hypotheses) == 2


def test_hypothesis_output_is_deterministic(tmp_path):
    fragments = _fragments(tmp_path, _jpeg_bytes())
    first = generate_hypotheses(fragments, StubCompatibilityModel(), tmp_path / "out-a", max_hypotheses=2)
    second = generate_hypotheses(fragments, StubCompatibilityModel(), tmp_path / "out-b", max_hypotheses=2)

    def stable(result):
        return [
            (item["fragment_ids"], item["compatibility_scores"], item["compatibility_score"], item["status"])
            for item in result
        ]

    assert stable(first) == stable(second)

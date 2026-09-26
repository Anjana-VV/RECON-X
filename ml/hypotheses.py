"""Bounded fragment-chain hypothesis generation and validation."""

from itertools import permutations
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from core.integrity import validate_jpeg
from core.reconstruction import reconstruct_artifact


DEFAULT_MAX_HYPOTHESES = 4


def _fragment_bytes(fragment: dict) -> bytes:
    data = fragment.get("data", fragment.get("bytes", fragment.get("content")))
    if data is not None:
        return bytes(data)
    output_path = fragment.get("output_path")
    if not output_path:
        raise ValueError(f"Fragment {fragment.get('fragment_id', 'UNKNOWN')} has no bytes or output_path")
    return Path(output_path).read_bytes()


def _score_chain(chain: tuple[dict, ...], model: Any) -> float:
    if len(chain) < 2:
        return 1.0
    scores = [
        model.predict_score(_fragment_bytes(first), _fragment_bytes(second))
        for first, second in zip(chain, chain[1:])
    ]
    return sum(scores) / len(scores)


def _candidate_orders(fragments: list[dict], limit: int) -> list[tuple[dict, ...]]:
    ordered = tuple(sorted(fragments, key=lambda item: (item.get("chunk_index", 0), item.get("fragment_id", ""))))
    if len(ordered) <= 1:
        return [ordered]
    candidates: list[tuple[dict, ...]] = []
    seen: set[tuple[str, ...]] = set()
    for candidate in permutations(ordered):
        key = tuple(item.get("fragment_id", str(index)) for index, item in enumerate(candidate))
        if key not in seen:
            seen.add(key)
            candidates.append(candidate)
        if len(candidates) >= max(limit * 4, limit):
            break
    return candidates


def _result_status(reconstruction: dict, validation: dict) -> str:
    if reconstruction["status"] == "PARTIAL":
        return "PARTIAL"
    if reconstruction["status"] == "RECONSTRUCTED" and validation["structure_valid"]:
        return "SUPPORTED"
    return "REJECTED"


def generate_hypotheses(
    fragments: list[dict],
    model: Any,
    output_directory: str | Path,
    max_hypotheses: int = DEFAULT_MAX_HYPOTHESES,
    total_expected_chunks: int | None = None,
) -> list[dict]:
    """Generate, reconstruct, and deterministically validate bounded hypotheses."""
    if not fragments:
        raise ValueError("fragments must be non-empty")
    if max_hypotheses <= 0:
        raise ValueError("max_hypotheses must be positive")

    output_dir = Path(output_directory)
    output_dir.mkdir(parents=True, exist_ok=True)
    candidates = _candidate_orders(fragments, max_hypotheses)
    scored = sorted(
        ((_score_chain(chain, model), chain) for chain in candidates),
        key=lambda item: (-item[0], tuple(fragment.get("fragment_id", "") for fragment in item[1])),
    )[:max_hypotheses]

    hypotheses = []
    for index, (compatibility_score, chain) in enumerate(scored, start=1):
        hypothesis_id = f"HYP-{index:03d}"
        ordered_fragments = []
        for chunk_index, fragment in enumerate(chain):
            item = dict(fragment)
            item["chunk_index"] = chunk_index
            ordered_fragments.append(item)
        output_path = output_dir / f"{hypothesis_id}.jpg"
        try:
            reconstruction = reconstruct_artifact(
                ordered_fragments,
                str(output_path),
                total_expected_chunks=total_expected_chunks,
            )
            validation = validate_jpeg(str(output_path))
            status = _result_status(reconstruction, validation)
        except (OSError, ValueError) as error:
            reconstruction = {
                "status": "PARTIAL" if total_expected_chunks and len(chain) < total_expected_chunks else "UNRELIABLE",
                "output_path": str(output_path),
                "fragment_ids": [fragment.get("fragment_id", "") for fragment in chain],
                "recovered_size_bytes": None,
            }
            validation = {
                "header_valid": False,
                "footer_valid": False,
                "decodable": False,
                "structure_valid": False,
                "corruption_detected": True,
                "error": str(error),
            }
            status = "PARTIAL" if reconstruction["status"] == "PARTIAL" else "REJECTED"

        hypotheses.append({
            "hypothesis_id": hypothesis_id,
            "fragment_ids": [fragment.get("fragment_id", "") for fragment in chain],
            "compatibility_scores": [
                model.predict_score(_fragment_bytes(first), _fragment_bytes(second))
                for first, second in zip(chain, chain[1:])
            ],
            "compatibility_score": float(compatibility_score),
            "validation": validation,
            "reconstruction": reconstruction,
            "status": status,
        })
    return hypotheses

"""Integrity analysis and recovery completeness measurement."""

from pathlib import Path
from PIL import Image

SOI_MARKER = b"\xff\xd8"
EOI_MARKER = b"\xff\xd9"


def validate_jpeg(file_path: str) -> dict:
    """Validate JPEG structure, markers, and decodability.

    Performs forensic inspection of JPEG header (SOI: FF D8), footer (EOI: FF D9),
    and validates format parsing and full pixel raster decodability via Pillow.

    Args:
        file_path: Path to the JPEG file to inspect.

    Returns:
        dict: Structured integrity assessment:
              {
                  "header_valid": bool,
                  "footer_valid": bool,
                  "decodable": bool,
                  "structure_valid": bool,
                  "corruption_detected": bool,
              }

    Raises:
        FileNotFoundError: If file_path does not exist.
        IsADirectoryError: If file_path is a directory.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Evidence file not found: {file_path}")
    if path.is_dir():
        raise IsADirectoryError(f"Evidence path is a directory: {file_path}")

    file_size = path.stat().st_size
    if file_size < 4:
        return {
            "header_valid": False,
            "footer_valid": False,
            "decodable": False,
            "structure_valid": False,
            "corruption_detected": True,
        }

    # Inspect SOI and EOI markers directly
    with open(path, "rb") as f:
        header_bytes = f.read(2)
        f.seek(file_size - 2)
        footer_bytes = f.read(2)

    header_valid = (header_bytes == SOI_MARKER)
    footer_valid = (footer_bytes == EOI_MARKER)

    decodable = False
    if header_valid:
        try:
            # Step 1: Open and verify format structure
            with Image.open(path) as img:
                if img.format == "JPEG":
                    img.verify()

            # Step 2: Reopen and attempt complete pixel decoding
            with Image.open(path) as img:
                img.load()
            decodable = True
        except Exception:
            decodable = False

    structure_valid = bool(header_valid and footer_valid and decodable)
    corruption_detected = not structure_valid

    return {
        "header_valid": header_valid,
        "footer_valid": footer_valid,
        "decodable": decodable,
        "structure_valid": structure_valid,
        "corruption_detected": corruption_detected,
    }


def calculate_recovery_completeness(
    recovered_size: int,
    expected_size: int
) -> float:
    """Calculate recovery completeness ratio clamped to [0.0, 1.0].

    Formula:
        recovered_size / expected_size

    Args:
        recovered_size: Number of recovered bytes.
        expected_size: Number of expected original bytes. Must be > 0.

    Returns:
        float: Completeness score in [0.0, 1.0].

    Raises:
        ValueError: If expected_size <= 0.
    """
    if expected_size <= 0:
        raise ValueError(f"expected_size must be positive, got {expected_size}")

    if recovered_size <= 0:
        return 0.0

    ratio = recovered_size / expected_size
    return max(0.0, min(1.0, float(ratio)))

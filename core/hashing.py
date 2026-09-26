"""Evidence acquisition and cryptographic hashing."""

import hashlib
from pathlib import Path

DEFAULT_CHUNK_SIZE = 1024 * 1024  # 1 MiB streaming buffer


def calculate_sha256(file_path: str, chunk_size: int = DEFAULT_CHUNK_SIZE) -> str:
    """Calculate SHA-256 hash of an evidence file using streaming reads.

    Args:
        file_path: Path to the evidence file.
        chunk_size: Size of byte chunks read into memory (default: 1 MiB).

    Returns:
        str: Lowercase hexadecimal SHA-256 hash digest.

    Raises:
        FileNotFoundError: If the file does not exist.
        IsADirectoryError: If the path is a directory.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Evidence file not found: {file_path}")
    if path.is_dir():
        raise IsADirectoryError(f"Path is a directory, not a file: {file_path}")

    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)

    return hasher.hexdigest().lower()

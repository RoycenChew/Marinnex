"""Blob storage: content-addressed files on local disk.

Content addressing is what makes stage 1 cheap. The same bytes uploaded twice
occupy one file, and the path is derivable from the hash, so a lost database row
does not orphan an unfindable blob.

The two-character shard directory exists because a flat directory of 100,000
files is slow to list on Windows and a nuisance to inspect by hand.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class BlobStore:
    root: Path

    def path_for(self, digest: str) -> Path:
        return self.root / digest[:2] / digest

    def put(self, data: bytes) -> tuple[str, str]:
        """Store the bytes, returning the digest and the path.

        Writing to a temporary name and renaming makes the store safe to read
        concurrently: a reader never sees a half-written blob, which is possible
        here because the worker reads what the API has just written.
        """
        digest = sha256_bytes(data)
        target = self.path_for(digest)
        if target.exists():
            return digest, str(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        staging = target.with_suffix(".partial")
        staging.write_bytes(data)
        staging.replace(target)
        return digest, str(target)

    def get(self, digest_or_path: str) -> bytes:
        candidate = Path(digest_or_path)
        if candidate.is_file():
            return candidate.read_bytes()
        return self.path_for(digest_or_path).read_bytes()

    def exists(self, digest_or_path: str) -> bool:
        candidate = Path(digest_or_path)
        return candidate.is_file() or self.path_for(digest_or_path).is_file()

    def delete(self, digest: str) -> None:
        target = self.path_for(digest)
        if target.is_file():
            target.unlink()


__all__ = ["BlobStore", "sha256_bytes"]

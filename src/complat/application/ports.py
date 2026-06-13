from __future__ import annotations

from pathlib import Path
from typing import Protocol

from complat.domain.entities import FileCandidate, ZipArchive, ZipBatch


class FileFinder(Protocol):
    def find(
        self,
        folder: Path,
        normalized_names: dict[str, str],
    ) -> tuple[FileCandidate, ...]:
        """Return only files that match the requested normalized names."""


class ArchiveWriter(Protocol):
    def write_batch(
        self,
        output_folder: Path,
        batch: ZipBatch,
        max_size_bytes: int,
    ) -> ZipArchive:
        """Write one archive batch and return its final metadata."""

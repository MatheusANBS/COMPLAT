from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FileCandidate:
    path: Path
    size_bytes: int
    is_directory: bool = False

    @property
    def filename(self) -> str:
        return self.path.name

    @property
    def stem(self) -> str:
        return self.path.stem

    @property
    def kind(self) -> str:
        return "Folder" if self.is_directory else "File"


@dataclass(frozen=True)
class RequestedName:
    lookup_name: str
    display_name: str


@dataclass(frozen=True)
class MatchedFiles:
    requested_names: tuple[str, ...]
    files: tuple[FileCandidate, ...]
    missing_names: tuple[str, ...]


@dataclass(frozen=True)
class ZipPlan:
    batches: tuple[ZipBatch, ...]
    max_size_bytes: int
    heuristic: str


@dataclass(frozen=True)
class ZipBatch:
    number: int
    files: tuple[FileCandidate, ...]
    total_size_bytes: int

    @property
    def file_count(self) -> int:
        return len(self.files)


@dataclass(frozen=True)
class ZipArchive:
    path: Path
    file_count: int
    max_size_bytes: int
    estimated_size_bytes: int
    actual_size_bytes: int

    @property
    def fits_limit(self) -> bool:
        return self.actual_size_bytes <= self.max_size_bytes

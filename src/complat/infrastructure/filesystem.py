from __future__ import annotations

from enum import StrEnum
import os
from pathlib import Path

from complat.application.cancellation import CancellationToken
from complat.domain.entities import FileCandidate


class LocalFileFinder:
    _MAX_CACHE_ITEMS = 8

    def __init__(
        self,
        recursive: bool = False,
        scan_mode: ScanMode | str = "files",
    ) -> None:
        self._recursive = recursive
        self._scan_mode = ScanMode.from_value(scan_mode)
        self._index_cache: dict[tuple[str, bool, ScanMode], dict[str, tuple[Path, ...]]] = {}
        self._cache_order: list[tuple[str, bool, ScanMode]] = []

    def find(
        self,
        folder: Path,
        normalized_names: dict[str, str],
        cancellation_token: CancellationToken | None = None,
    ) -> tuple[FileCandidate, ...]:
        if not folder.exists() or not folder.is_dir():
            raise NotADirectoryError(f"Folder does not exist: {folder}")

        if not normalized_names:
            return ()

        wanted = set(normalized_names)
        index = self._folder_index(folder, cancellation_token)
        files: list[FileCandidate] = []
        seen_paths = set()

        for key in wanted:
            if cancellation_token:
                cancellation_token.raise_if_cancelled()

            for path in index.get(key, ()):
                if path in seen_paths:
                    continue

                try:
                    is_directory = path.is_dir()
                    size_bytes = self._directory_size(path, cancellation_token) if is_directory else path.stat().st_size
                except FileNotFoundError:
                    continue

                files.append(
                    FileCandidate(
                        path=path,
                        size_bytes=size_bytes,
                        is_directory=is_directory,
                    )
                )
                seen_paths.add(path)

        return tuple(sorted(files, key=lambda file: file.filename.casefold()))

    def clear_cache(self) -> None:
        self._index_cache.clear()
        self._cache_order.clear()

    def _remember(
        self,
        key: tuple[str, bool, ScanMode],
        value: dict[str, tuple[Path, ...]],
    ) -> None:
        self._index_cache[key] = value
        self._cache_order.append(key)

        while len(self._cache_order) > self._MAX_CACHE_ITEMS:
            old_key = self._cache_order.pop(0)
            self._index_cache.pop(old_key, None)

    def _folder_index(
        self,
        folder: Path,
        cancellation_token: CancellationToken | None = None,
    ) -> dict[str, tuple[Path, ...]]:
        cache_key = (str(folder.resolve()), self._recursive, self._scan_mode)
        cached = self._index_cache.get(cache_key)
        if cached is not None:
            return cached

        indexed: dict[str, list[Path]] = {}
        for entry in self._iter_entries(folder):
            if cancellation_token:
                cancellation_token.raise_if_cancelled()

            path = Path(entry.path)
            keys = {
                entry.name.casefold(),
                path.stem.casefold(),
            }
            for key in keys:
                indexed.setdefault(key, []).append(path)

        result = {key: tuple(paths) for key, paths in indexed.items()}
        self._remember(cache_key, result)
        return result

    def _iter_entries(self, folder: Path):
        stack = [folder]

        while stack:
            current = stack.pop()
            with os.scandir(current) as entries:
                for entry in entries:
                    if entry.is_file() and self._scan_mode.includes_files:
                        yield entry
                    elif entry.is_dir():
                        if self._scan_mode.includes_folders:
                            yield entry
                        if self._recursive:
                            stack.append(Path(entry.path))

    def _directory_size(
        self,
        folder: Path,
        cancellation_token: CancellationToken | None = None,
    ) -> int:
        total_size = 0
        stack = [folder]

        while stack:
            if cancellation_token:
                cancellation_token.raise_if_cancelled()

            current = stack.pop()
            with os.scandir(current) as entries:
                for entry in entries:
                    if cancellation_token:
                        cancellation_token.raise_if_cancelled()

                    if entry.is_file():
                        total_size += entry.stat().st_size
                    elif entry.is_dir():
                        stack.append(Path(entry.path))

        return total_size


class ScanMode(StrEnum):
    FILES = "files"
    FOLDERS = "folders"
    BOTH = "both"

    @classmethod
    def from_value(cls, value: ScanMode | str) -> ScanMode:
        if isinstance(value, cls):
            return value

        normalized = value.strip().casefold()
        for mode in cls:
            if mode.value == normalized:
                return mode

        raise ValueError(f"Unknown scan mode: {value}")

    @property
    def includes_files(self) -> bool:
        return self in (ScanMode.FILES, ScanMode.BOTH)

    @property
    def includes_folders(self) -> bool:
        return self in (ScanMode.FOLDERS, ScanMode.BOTH)

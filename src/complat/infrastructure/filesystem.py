from __future__ import annotations

import os
from pathlib import Path

from complat.domain.entities import FileCandidate


class LocalFileFinder:
    _MAX_CACHE_ITEMS = 8

    def __init__(self, recursive: bool = False) -> None:
        self._recursive = recursive
        self._cache: dict[tuple[str, bool, tuple[str, ...]], tuple[FileCandidate, ...]] = {}
        self._cache_order: list[tuple[str, bool, tuple[str, ...]]] = []

    def find(
        self,
        folder: Path,
        normalized_names: dict[str, str],
    ) -> tuple[FileCandidate, ...]:
        if not folder.exists() or not folder.is_dir():
            raise NotADirectoryError(f"Folder does not exist: {folder}")

        if not normalized_names:
            return ()

        cache_key = self._cache_key(folder, normalized_names)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        wanted = set(normalized_names)
        files: list[FileCandidate] = []
        seen_paths = set()

        for entry in self._iter_entries(folder):
            name = entry.name
            stem = Path(name).stem

            if name.casefold() not in wanted and stem.casefold() not in wanted:
                continue

            path = Path(entry.path)
            if path in seen_paths:
                continue

            files.append(FileCandidate(path=path, size_bytes=entry.stat().st_size))
            seen_paths.add(path)

        result = tuple(sorted(files, key=lambda file: file.filename.casefold()))
        self._remember(cache_key, result)
        return result

    def _cache_key(
        self,
        folder: Path,
        normalized_names: dict[str, str],
    ) -> tuple[str, bool, tuple[str, ...]]:
        return (
            str(folder.resolve()),
            self._recursive,
            tuple(sorted(normalized_names)),
        )

    def _remember(
        self,
        key: tuple[str, bool, tuple[str, ...]],
        value: tuple[FileCandidate, ...],
    ) -> None:
        self._cache[key] = value
        self._cache_order.append(key)

        while len(self._cache_order) > self._MAX_CACHE_ITEMS:
            old_key = self._cache_order.pop(0)
            self._cache.pop(old_key, None)

    def _iter_entries(self, folder: Path):
        stack = [folder]

        while stack:
            current = stack.pop()
            with os.scandir(current) as entries:
                for entry in entries:
                    if entry.is_file():
                        yield entry
                    elif self._recursive and entry.is_dir():
                        stack.append(Path(entry.path))

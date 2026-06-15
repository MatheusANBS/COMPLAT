from __future__ import annotations

import os
from pathlib import Path

from complat.application.cancellation import CancellationToken
from complat.domain.entities import FileCandidate


class LocalFileFinder:
    _MAX_CACHE_ITEMS = 8

    def __init__(self, recursive: bool = False) -> None:
        self._recursive = recursive
        self._index_cache: dict[tuple[str, bool], dict[str, tuple[Path, ...]]] = {}
        self._cache_order: list[tuple[str, bool]] = []

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
                    size_bytes = path.stat().st_size
                except FileNotFoundError:
                    continue

                files.append(FileCandidate(path=path, size_bytes=size_bytes))
                seen_paths.add(path)

        return tuple(sorted(files, key=lambda file: file.filename.casefold()))

    def clear_cache(self) -> None:
        self._index_cache.clear()
        self._cache_order.clear()

    def _remember(
        self,
        key: tuple[str, bool],
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
        cache_key = (str(folder.resolve()), self._recursive)
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
                    if entry.is_file():
                        yield entry
                    elif self._recursive and entry.is_dir():
                        stack.append(Path(entry.path))

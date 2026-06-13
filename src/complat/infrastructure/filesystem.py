from __future__ import annotations

import os
from pathlib import Path

from complat.domain.entities import FileCandidate


class LocalFileFinder:
    def __init__(self, recursive: bool = False) -> None:
        self._recursive = recursive

    def find(
        self,
        folder: Path,
        normalized_names: dict[str, str],
    ) -> tuple[FileCandidate, ...]:
        if not folder.exists() or not folder.is_dir():
            raise NotADirectoryError(f"Folder does not exist: {folder}")

        if not normalized_names:
            return ()

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

        return tuple(sorted(files, key=lambda file: file.filename.casefold()))

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

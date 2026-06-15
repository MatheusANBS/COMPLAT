from __future__ import annotations

from bisect import bisect_left, insort
from typing import Protocol

from .entities import FileCandidate, MatchedFiles, RequestedName, ZipBatch, ZipPlan


class CancellationToken(Protocol):
    def raise_if_cancelled(self) -> None:
        """Raise when the current operation should stop."""


class NameNormalizer:
    def normalize(self, value: str) -> str:
        return value.strip().casefold()

    def normalize_many(self, values: list[str]) -> tuple[str, ...]:
        normalized = []
        seen = set()

        for value in values:
            item = self.normalize(value)
            if not item or item in seen:
                continue

            normalized.append(item)
            seen.add(item)

        return tuple(normalized)

    def unique_originals_by_normalized(self, values: list[str]) -> dict[str, str]:
        normalized: dict[str, str] = {}

        for value in values:
            requested_name = self.parse_requested_name(value)
            key = self.normalize(requested_name.lookup_name)
            if not key or key in normalized:
                continue

            normalized[key] = requested_name.display_name

        return normalized

    def parse_requested_name(self, value: str) -> RequestedName:
        text = value.strip()
        if not text:
            return RequestedName(lookup_name="", display_name="")

        parts = text.split(None, 1)
        if len(parts) == 2 and parts[0].isdigit():
            return RequestedName(lookup_name=parts[1].strip(), display_name=text)

        return RequestedName(lookup_name=text, display_name=text)


class FileNameMatcher:
    def __init__(self, normalizer: NameNormalizer) -> None:
        self._normalizer = normalizer

    def match(
        self,
        requested_names: tuple[str, ...],
        candidates: tuple[FileCandidate, ...],
    ) -> MatchedFiles:
        files_by_name = self._index_candidates(candidates)
        matched_files = []
        missing_names = []
        seen_paths = set()

        for requested_name in requested_names:
            matches = files_by_name.get(requested_name, ())
            if not matches:
                missing_names.append(requested_name)
                continue

            for file in matches:
                if file.path in seen_paths:
                    continue

                matched_files.append(file)
                seen_paths.add(file.path)

        return MatchedFiles(
            requested_names=requested_names,
            files=tuple(matched_files),
            missing_names=tuple(missing_names),
        )

    def _index_candidates(
        self,
        candidates: tuple[FileCandidate, ...],
    ) -> dict[str, tuple[FileCandidate, ...]]:
        indexed: dict[str, list[FileCandidate]] = {}

        for candidate in candidates:
            keys = {
                self._normalizer.normalize(candidate.filename),
                self._normalizer.normalize(candidate.stem),
            }

            for key in keys:
                indexed.setdefault(key, []).append(candidate)

        return {key: tuple(value) for key, value in indexed.items()}


class ZipPlanner:
    _ZIP_BATCH_OVERHEAD_BYTES = 256
    _ZIP_FILE_OVERHEAD_BYTES = 128

    def plan(
        self,
        files: tuple[FileCandidate, ...],
        max_size_bytes: int,
        cancellation_token: CancellationToken | None = None,
    ) -> ZipPlan:
        if max_size_bytes <= 0:
            raise ValueError("Max size must be greater than zero.")

        sorted_files = sorted(files, key=lambda file: file.size_bytes, reverse=True)
        batches: list[list[FileCandidate]] = []
        batch_sizes: list[int] = []
        remaining_by_batch: list[tuple[int, int]] = []
        effective_max_size_bytes = max(1, max_size_bytes - self._ZIP_BATCH_OVERHEAD_BYTES)

        for file in sorted_files:
            if cancellation_token:
                cancellation_token.raise_if_cancelled()

            planned_file_size = file.size_bytes + self._ZIP_FILE_OVERHEAD_BYTES

            if planned_file_size > effective_max_size_bytes:
                batches.append([file])
                batch_sizes.append(file.size_bytes)
                continue

            position = bisect_left(remaining_by_batch, (planned_file_size, -1))

            if position == len(remaining_by_batch):
                batches.append([file])
                batch_sizes.append(file.size_bytes)
                insort(
                    remaining_by_batch,
                    (
                        effective_max_size_bytes - planned_file_size,
                        len(batches) - 1,
                    ),
                )
                continue

            remaining, batch_index = remaining_by_batch.pop(position)
            batches[batch_index].append(file)
            batch_sizes[batch_index] += file.size_bytes
            insort(remaining_by_batch, (remaining - planned_file_size, batch_index))

        zip_batches = tuple(
            ZipBatch(
                number=index + 1,
                files=tuple(batch),
                total_size_bytes=batch_sizes[index],
            )
            for index, batch in enumerate(batches)
        )

        return ZipPlan(
            batches=zip_batches,
            max_size_bytes=max_size_bytes,
            heuristic=(
                "Best-fit decreasing by source size with an ordered remaining-space "
                "index. Files are sorted largest first and each file is placed in "
                "the tightest batch that still fits without scanning every batch. "
                "The planner also reserves a small safety margin for zip metadata "
                "per batch and per file."
            ),
        )

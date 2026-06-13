from __future__ import annotations

from .entities import FileCandidate, MatchedFiles, RequestedName, ZipBatch, ZipPlan


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
    def plan(
        self,
        files: tuple[FileCandidate, ...],
        max_size_bytes: int,
    ) -> ZipPlan:
        if max_size_bytes <= 0:
            raise ValueError("Max size must be greater than zero.")

        sorted_files = sorted(files, key=lambda file: file.size_bytes, reverse=True)
        batches: list[list[FileCandidate]] = []
        batch_sizes: list[int] = []

        for file in sorted_files:
            if file.size_bytes > max_size_bytes:
                batches.append([file])
                batch_sizes.append(file.size_bytes)
                continue

            best_index = self._find_best_fit(batch_sizes, file.size_bytes, max_size_bytes)

            if best_index is None:
                batches.append([file])
                batch_sizes.append(file.size_bytes)
                continue

            batches[best_index].append(file)
            batch_sizes[best_index] += file.size_bytes

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
                "Best-fit decreasing by source size. Files are sorted largest first "
                "and each file is placed in the tightest batch that still fits."
            ),
        )

    def _find_best_fit(
        self,
        batch_sizes: list[int],
        file_size: int,
        max_size_bytes: int,
    ) -> int | None:
        best_index = None
        best_remaining = max_size_bytes + 1

        for index, batch_size in enumerate(batch_sizes):
            remaining = max_size_bytes - batch_size - file_size
            if remaining < 0 or remaining >= best_remaining:
                continue

            best_index = index
            best_remaining = remaining

        return best_index

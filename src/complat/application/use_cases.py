from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
from os import cpu_count
from pathlib import Path
from threading import Lock
from time import monotonic

from complat.application.cancellation import CancellationToken
from complat.application.errors import ArchiveAlreadyExists, FileExceedsZipLimit
from complat.application.ports import ArchiveWriter, FileFinder
from complat.domain.entities import MatchedFiles, ZipArchive, ZipPlan
from complat.domain.services import FileNameMatcher, NameNormalizer, ZipPlanner


@dataclass(frozen=True)
class AnalysisResult:
    matched: MatchedFiles
    plan: ZipPlan
    total_size_bytes: int


@dataclass(frozen=True)
class CreateZipsResult:
    analysis: AnalysisResult
    archives: tuple[ZipArchive, ...]


class CompareNamesUseCase:
    def __init__(
        self,
        file_finder: FileFinder,
        matcher: FileNameMatcher,
        normalizer: NameNormalizer,
    ) -> None:
        self._file_finder = file_finder
        self._matcher = matcher
        self._normalizer = normalizer

    def execute(
        self,
        folder: Path,
        raw_names: list[str],
        cancellation_token: CancellationToken | None = None,
    ) -> MatchedFiles:
        if cancellation_token:
            cancellation_token.raise_if_cancelled()

        display_names_by_key = self._normalizer.unique_originals_by_normalized(raw_names)
        lookup_names_by_key = {key: key for key in display_names_by_key}
        candidates = self._file_finder.find(
            folder,
            lookup_names_by_key,
            cancellation_token,
        )
        if cancellation_token:
            cancellation_token.raise_if_cancelled()

        matched = self._matcher.match(tuple(display_names_by_key), candidates)
        missing_keys = set(matched.missing_names)

        return MatchedFiles(
            requested_names=tuple(display_names_by_key.values()),
            files=matched.files,
            missing_names=tuple(original for key, original in display_names_by_key.items() if key in missing_keys),
        )


class AnalyzeZipPlanUseCase:
    def __init__(
        self,
        compare_names: CompareNamesUseCase,
        planner: ZipPlanner,
    ) -> None:
        self._compare_names = compare_names
        self._planner = planner

    def execute(
        self,
        folder: Path,
        raw_names: list[str],
        max_size_bytes: int,
        cancellation_token: CancellationToken | None = None,
    ) -> AnalysisResult:
        matched = self._compare_names.execute(folder, raw_names, cancellation_token)
        plan = self._planner.plan(matched.files, max_size_bytes, cancellation_token)

        return AnalysisResult(
            matched=matched,
            plan=plan,
            total_size_bytes=sum(file.size_bytes for file in matched.files),
        )


class CreateZipBatchesUseCase:
    def __init__(
        self,
        analyze_plan: AnalyzeZipPlanUseCase,
        archive_writer: ArchiveWriter,
        max_workers: int | None = None,
    ) -> None:
        self._analyze_plan = analyze_plan
        self._archive_writer = archive_writer
        self._max_workers = max_workers

    def execute(
        self,
        folder: Path,
        raw_names: list[str],
        output_folder: Path,
        max_size_bytes: int,
        progress_callback: Callable[[int, int, str], None] | None = None,
        cancellation_token: CancellationToken | None = None,
    ) -> CreateZipsResult:
        analysis = self._analyze_plan.execute(
            folder,
            raw_names,
            max_size_bytes,
            cancellation_token,
        )
        return self.execute_from_analysis(
            analysis,
            output_folder,
            progress_callback,
            cancellation_token,
        )

    def execute_from_analysis(
        self,
        analysis: AnalysisResult,
        output_folder: Path,
        progress_callback: Callable[[int, int, str], None] | None = None,
        cancellation_token: CancellationToken | None = None,
    ) -> CreateZipsResult:
        total_batches = len(analysis.plan.batches)

        if cancellation_token:
            cancellation_token.raise_if_cancelled()

        if total_batches == 0:
            return CreateZipsResult(analysis=analysis, archives=())

        for batch in analysis.plan.batches:
            for file in batch.files:
                if file.size_bytes > analysis.plan.max_size_bytes:
                    raise FileExceedsZipLimit(f"{file.filename} is larger than the configured zip limit.")

        self._ensure_output_paths_available(output_folder, analysis)

        worker_count = self._worker_count(total_batches)
        archives_by_number: dict[int, ZipArchive] = {}
        completed = 0
        written_bytes = 0
        last_progress_at = 0.0
        total_bytes = max(1, analysis.total_size_bytes)
        progress_lock = Lock()

        if progress_callback:
            progress_callback(0, total_bytes, f"Creating {total_batches} zip part(s)")

        def report_bytes(delta_bytes: int, message: str) -> None:
            nonlocal last_progress_at, written_bytes
            if progress_callback is None:
                return

            if cancellation_token:
                cancellation_token.raise_if_cancelled()

            with progress_lock:
                written_bytes = min(total_bytes, written_bytes + delta_bytes)
                now = monotonic()
                should_emit = last_progress_at == 0.0 or now - last_progress_at >= 0.15 or written_bytes >= total_bytes
                if should_emit:
                    last_progress_at = now
                    progress_callback(written_bytes, total_bytes, message)

        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(
                    self._archive_writer.write_batch,
                    output_folder,
                    batch,
                    analysis.plan.max_size_bytes,
                    report_bytes,
                    cancellation_token,
                ): batch
                for batch in analysis.plan.batches
            }

            for future in as_completed(futures):
                if cancellation_token:
                    cancellation_token.raise_if_cancelled()

                batch = futures[future]
                archive = future.result()

                if not archive.fits_limit:
                    archive.path.unlink(missing_ok=True)
                    raise FileExceedsZipLimit(
                        "A generated zip exceeded the limit after compression overhead. "
                        "Lower the limit or split that file manually."
                    )

                archives_by_number[batch.number] = archive
                completed += 1
                if progress_callback:
                    progress_callback(
                        written_bytes,
                        total_bytes,
                        f"Created part {batch.number:03d}",
                    )

        archives = tuple(archives_by_number[batch.number] for batch in analysis.plan.batches)

        return CreateZipsResult(analysis=analysis, archives=archives)

    def _worker_count(self, total_batches: int) -> int:
        configured = self._max_workers
        if configured is None:
            configured = min(8, max(1, cpu_count() or 2))

        return max(1, min(total_batches, configured))

    def _ensure_output_paths_available(
        self,
        output_folder: Path,
        analysis: AnalysisResult,
    ) -> None:
        for batch in analysis.plan.batches:
            path = output_folder / f"complat_part_{batch.number:03d}.zip"
            if path.exists():
                raise ArchiveAlreadyExists(f"Output archive already exists: {path}")

            temp_path = path.with_suffix(path.suffix + ".tmp")
            temp_path.unlink(missing_ok=True)

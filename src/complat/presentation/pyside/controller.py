from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from complat.application.cancellation import CancellationToken
from complat.application.use_cases import AnalysisResult, CreateZipsResult
from complat.presentation.composition import ApplicationServices


@dataclass(frozen=True)
class TimedAnalysisResult:
    analysis: AnalysisResult
    elapsed_seconds: float


@dataclass(frozen=True)
class TimedCreateResult:
    result: CreateZipsResult
    elapsed_seconds: float


class CompactFilesController:
    def __init__(self, services: ApplicationServices) -> None:
        self._services = services

    def analyze(
        self,
        folder: Path,
        raw_names: list[str],
        max_size_mb: int,
        cancellation_token: CancellationToken | None = None,
    ) -> TimedAnalysisResult:
        started_at = perf_counter()
        analysis = self._services.analyze_zip_plan.execute(
            folder=folder,
            raw_names=raw_names,
            max_size_bytes=max_size_mb * 1024 * 1024,
            cancellation_token=cancellation_token,
        )

        return TimedAnalysisResult(
            analysis=analysis,
            elapsed_seconds=perf_counter() - started_at,
        )

    def create_zips_from_analysis(
        self,
        analysis: AnalysisResult,
        output_folder: Path,
        progress_callback: Callable[[int, int, str], None] | None = None,
        cancellation_token: CancellationToken | None = None,
    ) -> TimedCreateResult:
        started_at = perf_counter()
        result = self._services.create_zip_batches.execute_from_analysis(
            analysis=analysis,
            output_folder=output_folder,
            progress_callback=progress_callback,
            cancellation_token=cancellation_token,
        )

        return TimedCreateResult(
            result=result,
            elapsed_seconds=perf_counter() - started_at,
        )

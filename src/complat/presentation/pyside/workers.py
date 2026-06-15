from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from complat.application.cancellation import CancellationToken
from complat.application.use_cases import AnalysisResult
from complat.presentation.pyside.controller import (
    CompactFilesController,
    TimedAnalysisResult,
    TimedCreateResult,
)


class AnalysisWorker(QObject):
    succeeded = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(
        self,
        controller: CompactFilesController,
        folder: Path,
        raw_names: list[str],
        max_size_mb: int,
    ) -> None:
        super().__init__()
        self._controller = controller
        self._folder = folder
        self._raw_names = raw_names
        self._max_size_mb = max_size_mb
        self._cancellation_token = CancellationToken()

    def cancel(self) -> None:
        self._cancellation_token.cancel()

    @Slot()
    def run(self) -> None:
        try:
            result = self._analyze()
        except Exception as error:
            self.failed.emit(str(error))
        else:
            self.succeeded.emit(result)
        finally:
            self.finished.emit()

    def _analyze(self) -> TimedAnalysisResult:
        return self._controller.analyze(
            folder=self._folder,
            raw_names=self._raw_names,
            max_size_mb=self._max_size_mb,
            cancellation_token=self._cancellation_token,
        )


class ZipCreationWorker(QObject):
    progress = Signal(object, object, str)
    succeeded = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(
        self,
        controller: CompactFilesController,
        output_folder: Path,
        analysis: AnalysisResult,
    ) -> None:
        super().__init__()
        self._controller = controller
        self._analysis = analysis
        self._output_folder = output_folder
        self._cancellation_token = CancellationToken()

    def cancel(self) -> None:
        self._cancellation_token.cancel()

    @Slot()
    def run(self) -> None:
        try:
            result = self._create()
        except Exception as error:
            self.failed.emit(str(error))
        else:
            self.succeeded.emit(result)
        finally:
            self.finished.emit()

    def _create(self) -> TimedCreateResult:
        return self._controller.create_zips_from_analysis(
            analysis=self._analysis,
            output_folder=self._output_folder,
            progress_callback=self.progress.emit,
            cancellation_token=self._cancellation_token,
        )

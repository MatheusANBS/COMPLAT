from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from complat.application.use_cases import AnalysisResult
from complat.presentation.pyside.controller import CompactFilesController, TimedCreateResult


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
        )

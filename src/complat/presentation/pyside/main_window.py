from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QThread, Qt
from PySide6.QtGui import QGuiApplication, QIcon, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QProgressBar,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from complat.application.use_cases import AnalysisResult, CreateZipsResult
from complat.domain.entities import MatchedFiles
from complat.domain.services import NameNormalizer
from complat.presentation.assets import app_logo_path
from complat.presentation.composition import build_services
from complat.presentation.pyside.controller import CompactFilesController, TimedAnalysisResult
from complat.presentation.pyside.workers import ZipCreationWorker


DEFAULT_LIMIT_MB = 9


class MainWindow(QMainWindow):
    def __init__(self, app_icon: QIcon | None = None) -> None:
        super().__init__()
        self.setWindowTitle("COMPLAT")
        if app_icon:
            self.setWindowIcon(app_icon)
        self.resize(1280, 780)
        self.setMinimumSize(900, 560)

        self._controller = CompactFilesController(build_services())
        self._last_analysis: AnalysisResult | None = None
        self._zip_thread: QThread | None = None
        self._zip_worker: ZipCreationWorker | None = None
        self._name_normalizer = NameNormalizer()
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        self.source_input = QLineEdit()
        self.source_input.setPlaceholderText("Folder to analyze")
        self.source_button = QPushButton("Browse")

        self.output_input = QLineEdit()
        self.output_input.setPlaceholderText("Folder where zip parts will be created")
        self.output_button = QPushButton("Browse")

        self.max_size_input = QSpinBox()
        self.max_size_input.setRange(1, 2048)
        self.max_size_input.setValue(DEFAULT_LIMIT_MB)
        self.max_size_input.setSuffix(" MB")
        self.max_size_input.setFixedWidth(120)

        self.recursive_input = QCheckBox("Include subfolders")

        self.names_input = QPlainTextEdit()
        self.names_input.setPlaceholderText("Paste one file/person name per line")
        self.names_input.setMinimumWidth(260)

        self.paste_button = QPushButton("Paste")
        self.clear_button = QPushButton("Clear")
        self.analyze_button = QPushButton("Analyze plan")
        self.create_button = QPushButton("Create zips")
        self.create_button.setEnabled(False)

        self.requested_count_label = QLabel("Names 0")
        self.found_count_label = QLabel("Found 0")
        self.missing_count_label = QLabel("Missing 0")
        self.zip_count_label = QLabel("Zips 0")
        self.size_label = QLabel("Source 0 B")
        self.time_label = QLabel("Time -")
        self.progress_label = QLabel("Idle")
        self.progress_label.setObjectName("progressLabel")
        self.copy_feedback_label = QLabel("")
        self.copy_feedback_label.setObjectName("copyFeedback")
        self.copy_feedback_label.setVisible(False)
        self._copy_feedback_effect = QGraphicsOpacityEffect(self.copy_feedback_label)
        self.copy_feedback_label.setGraphicsEffect(self._copy_feedback_effect)
        self._copy_feedback_animation = QPropertyAnimation(
            self._copy_feedback_effect,
            b"opacity",
            self,
        )
        self._copy_feedback_animation.setDuration(1400)
        self._copy_feedback_animation.setEasingCurve(QEasingCurve.OutCubic)
        self._copy_feedback_animation.finished.connect(self._hide_copy_feedback)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)

        self.plan_table = self._create_table(["Zip", "Files", "Estimated", "Actual", "Status"])
        self.found_table = self._create_table(["Name", "File", "Size", "Path"])
        self.missing_table = self._create_table(["Code", "Name"])
        self.heuristic_output = QPlainTextEdit()
        self.heuristic_output.setReadOnly(True)

        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(16, 16, 16, 12)
        root_layout.setSpacing(12)
        root_layout.addWidget(self._build_header())
        root_layout.addWidget(self._build_controls())
        root_layout.addWidget(self._build_summary())
        root_layout.addWidget(self._build_workspace(), stretch=1)

        container = QWidget()
        container.setObjectName("root")
        container.setLayout(root_layout)
        self.setCentralWidget(container)
        self.statusBar().showMessage("Ready")
        self._apply_styles()

    def _build_header(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("header")

        icon_label = QLabel()
        logo_path = app_logo_path()
        if logo_path:
            pixmap = QPixmap(str(logo_path))
            if not pixmap.isNull():
                icon_label.setPixmap(
                    pixmap.scaled(34, 34, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )

        title = QLabel("COMPLAT")
        title.setObjectName("appTitle")
        subtitle = QLabel("Analyze names, plan ZIP parts, and package files safely.")
        subtitle.setObjectName("appSubtitle")

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)
        text_layout.addWidget(title)
        text_layout.addWidget(subtitle)

        layout = QHBoxLayout()
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(10)
        layout.addWidget(icon_label)
        layout.addLayout(text_layout)
        layout.addStretch()

        panel.setLayout(layout)
        return panel

    def _build_controls(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("panel")

        form = QGridLayout()
        form.setContentsMargins(14, 14, 14, 14)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(10)
        form.setColumnStretch(1, 1)

        form.addWidget(QLabel("Source"), 0, 0)
        form.addWidget(self.source_input, 0, 1)
        form.addWidget(self.source_button, 0, 2)
        form.addWidget(QLabel("Output"), 1, 0)
        form.addWidget(self.output_input, 1, 1)
        form.addWidget(self.output_button, 1, 2)
        form.addWidget(QLabel("Limit"), 2, 0)
        form.addWidget(self.max_size_input, 2, 1, alignment=Qt.AlignLeft)
        form.addWidget(self.recursive_input, 2, 2, alignment=Qt.AlignLeft)

        panel.setLayout(form)
        return panel

    def _build_summary(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("panel")

        metrics = QHBoxLayout()
        metrics.setContentsMargins(14, 10, 14, 10)
        metrics.setSpacing(10)

        for label in (
            self.requested_count_label,
            self.found_count_label,
            self.missing_count_label,
            self.zip_count_label,
            self.size_label,
            self.time_label,
        ):
            label.setObjectName("metric")
            metrics.addWidget(label)

        metrics.addStretch()
        metrics.addWidget(self.copy_feedback_label)
        metrics.addWidget(self.progress_label)
        metrics.addWidget(self.progress_bar)
        metrics.addWidget(self.analyze_button)
        metrics.addWidget(self.create_button)

        panel.setLayout(metrics)
        return panel

    def _build_workspace(self) -> QWidget:
        names_panel = QWidget()
        names_panel.setObjectName("panel")
        names_panel.setMinimumWidth(280)

        names_actions = QHBoxLayout()
        names_actions.addWidget(self.paste_button)
        names_actions.addWidget(self.clear_button)
        names_actions.addStretch()

        names_layout = QVBoxLayout()
        names_layout.setContentsMargins(14, 14, 14, 14)
        names_layout.addWidget(QLabel("Names"))
        names_layout.addWidget(self.names_input, stretch=1)
        names_layout.addLayout(names_actions)
        names_panel.setLayout(names_layout)

        tabs = QTabWidget()
        tabs.setObjectName("resultTabs")
        tabs.addTab(self.plan_table, "Plan")
        tabs.addTab(self.found_table, "Found")
        tabs.addTab(self.missing_table, "Not found")
        tabs.addTab(self.heuristic_output, "Heuristic")

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(names_panel)
        splitter.addWidget(tabs)
        splitter.setSizes([340, 900])
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)
        splitter.setChildrenCollapsible(False)
        return splitter

    def _create_table(self, headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSortingEnabled(True)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        return table

    def _connect_signals(self) -> None:
        self.source_button.clicked.connect(self._choose_source_folder)
        self.output_button.clicked.connect(self._choose_output_folder)
        self.paste_button.clicked.connect(self._paste_names)
        self.clear_button.clicked.connect(self._clear)
        self.analyze_button.clicked.connect(self._analyze)
        self.create_button.clicked.connect(self._create_zips)
        self.recursive_input.stateChanged.connect(self._rebuild_controller)
        self.names_input.textChanged.connect(self._update_requested_count)
        self.names_input.textChanged.connect(self._invalidate_analysis)
        self.source_input.textChanged.connect(self._invalidate_analysis)
        self.max_size_input.valueChanged.connect(self._invalidate_analysis)
        self.missing_table.itemClicked.connect(self._copy_missing_name)

    def _choose_source_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose source folder")
        if not folder:
            return

        self.source_input.setText(folder)
        if not self.output_input.text().strip():
            self.output_input.setText(str(Path(folder) / "complat_output"))

    def _choose_output_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose output folder")
        if folder:
            self.output_input.setText(folder)

    def _paste_names(self) -> None:
        text = QGuiApplication.clipboard().text()
        if text:
            self.names_input.setPlainText(text)

    def _clear(self) -> None:
        self.names_input.clear()
        self._last_analysis = None
        self._clear_tables()
        self.heuristic_output.clear()
        self._set_summary()
        self.statusBar().showMessage("Ready")

    def _analyze(self) -> None:
        if not self._validate_inputs(require_output=False):
            return

        self._set_busy(True, "Analyzing plan...")
        try:
            result = self._controller.analyze(
                folder=self._source_folder(),
                raw_names=self._raw_names(),
                max_size_mb=self.max_size_input.value(),
            )
        except Exception as error:
            self._show_error(str(error))
            return
        finally:
            self._set_busy(False)

        self._last_analysis = result.analysis
        self._render_analysis(result)
        self.create_button.setEnabled(True)
        self.statusBar().showMessage("Plan ready")

    def _create_zips(self) -> None:
        if not self._validate_inputs(require_output=True):
            return

        if self._zip_thread and self._zip_thread.isRunning():
            return

        if self._last_analysis is None:
            self._show_error("Analyze the plan before creating zips.")
            return

        self._set_creating(True)
        self._mark_plan_pending()

        self._zip_thread = QThread(self)
        self._zip_worker = ZipCreationWorker(
            controller=self._controller,
            output_folder=self._output_folder(),
            analysis=self._last_analysis,
        )
        self._zip_worker.moveToThread(self._zip_thread)

        self._zip_thread.started.connect(self._zip_worker.run)
        self._zip_worker.progress.connect(self._on_zip_progress)
        self._zip_worker.succeeded.connect(self._on_zip_created)
        self._zip_worker.failed.connect(self._on_zip_failed)
        self._zip_worker.finished.connect(self._zip_thread.quit)
        self._zip_worker.finished.connect(self._zip_worker.deleteLater)
        self._zip_thread.finished.connect(self._zip_thread.deleteLater)
        self._zip_thread.finished.connect(self._on_zip_thread_finished)
        self._zip_thread.start()

    def _render_analysis(self, result: TimedAnalysisResult) -> None:
        self._render_found(result.analysis.matched)
        self._render_missing(result.analysis.matched.missing_names)
        self._render_plan(result.analysis)
        self._render_heuristic(result.analysis, result.elapsed_seconds, created=False)
        self._set_summary(
            analysis=result.analysis,
            elapsed_seconds=result.elapsed_seconds,
        )

    def _render_created(self, result: CreateZipsResult, elapsed_seconds: float) -> None:
        self._render_found(result.analysis.matched)
        self._render_missing(result.analysis.matched.missing_names)
        self._render_plan(result.analysis, result.archives)
        self._render_heuristic(result.analysis, elapsed_seconds, created=True)
        self._set_summary(
            analysis=result.analysis,
            elapsed_seconds=elapsed_seconds,
        )

    def _mark_plan_pending(self) -> None:
        if self._last_analysis is None:
            return

        for row in range(self.plan_table.rowCount()):
            self.plan_table.setItem(row, 3, QTableWidgetItem("-"))
            self.plan_table.setItem(row, 4, QTableWidgetItem("Queued"))

    def _on_zip_progress(self, completed: int, total: int, message: str) -> None:
        if total <= 0:
            self.progress_bar.setRange(0, 0)
            percent = 0
        else:
            self.progress_bar.setRange(0, 100)
            percent = int((completed / total) * 100)
            self.progress_bar.setValue(percent)

        self.progress_label.setText(f"{completed}/{total}")
        self.statusBar().showMessage(message)
        self._update_plan_status(completed, total, message)

    def _update_plan_status(self, completed: int, total: int, message: str) -> None:
        if total <= 0 or self.plan_table.rowCount() == 0:
            return

        if message.startswith("Created part "):
            number = self._part_number_from_message(message)
            if number is not None and 0 <= number - 1 < self.plan_table.rowCount():
                self.plan_table.setItem(number - 1, 4, QTableWidgetItem("Created"))

    def _part_number_from_message(self, message: str) -> int | None:
        try:
            return int(message.rsplit(" ", 1)[1])
        except (IndexError, ValueError):
            return None

    def _on_zip_created(self, result) -> None:
        self._last_analysis = result.result.analysis
        self._render_created(result.result, result.elapsed_seconds)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.progress_label.setText("Done")
        self.statusBar().showMessage(f"Created {len(result.result.archives)} zip part(s)")
        QMessageBox.information(self, "COMPLAT", "Zip parts created.")

    def _on_zip_failed(self, message: str) -> None:
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_label.setText("Failed")
        self.statusBar().showMessage("Zip creation failed")
        self._show_error(message)

    def _on_zip_thread_finished(self) -> None:
        self._zip_thread = None
        self._zip_worker = None
        self._set_creating(False)

    def _render_plan(self, analysis: AnalysisResult, archives=()) -> None:
        actual_by_number = {
            index + 1: archive.actual_size_bytes
            for index, archive in enumerate(archives)
        }
        self.plan_table.setSortingEnabled(False)
        self.plan_table.setRowCount(len(analysis.plan.batches))

        for row, batch in enumerate(analysis.plan.batches):
            actual = actual_by_number.get(batch.number)
            status = "Ready" if actual is None else "Created"
            values = [
                f"part {batch.number:03d}",
                str(batch.file_count),
                _format_bytes(batch.total_size_bytes),
                "-" if actual is None else _format_bytes(actual),
                status,
            ]
            for column, value in enumerate(values):
                self.plan_table.setItem(row, column, QTableWidgetItem(value))

        self.plan_table.resizeColumnsToContents()
        self.plan_table.horizontalHeader().setStretchLastSection(True)
        self.plan_table.setSortingEnabled(True)

    def _render_found(self, matched: MatchedFiles) -> None:
        self.found_table.setSortingEnabled(False)
        self.found_table.setRowCount(len(matched.files))

        for row, file in enumerate(matched.files):
            values = [file.stem, file.filename, _format_bytes(file.size_bytes), str(file.path)]
            for column, value in enumerate(values):
                self.found_table.setItem(row, column, QTableWidgetItem(value))

        self.found_table.resizeColumnsToContents()
        self.found_table.horizontalHeader().setStretchLastSection(True)
        self.found_table.setSortingEnabled(True)

    def _render_missing(self, missing_names: tuple[str, ...]) -> None:
        self.missing_table.setSortingEnabled(False)
        self.missing_table.setRowCount(len(missing_names))

        for row, name in enumerate(missing_names):
            code, person_name = self._split_display_name(name)
            self.missing_table.setItem(row, 0, QTableWidgetItem(code))
            self.missing_table.setItem(row, 1, QTableWidgetItem(person_name))

        self.missing_table.resizeColumnsToContents()
        self.missing_table.horizontalHeader().setStretchLastSection(True)
        self.missing_table.setSortingEnabled(True)

    def _split_display_name(self, value: str) -> tuple[str, str]:
        requested_name = self._name_normalizer.parse_requested_name(value)
        if requested_name.display_name == requested_name.lookup_name:
            return "", requested_name.lookup_name

        parts = requested_name.display_name.split(None, 1)
        if len(parts) != 2:
            return "", requested_name.display_name

        return parts[0], parts[1]

    def _copy_missing_name(self, item: QTableWidgetItem) -> None:
        value = item.text().strip()
        if not value:
            return

        QGuiApplication.clipboard().setText(value)
        copied_kind = "code" if item.column() == 0 else "name"
        self.copy_feedback_label.setText(f"✓ Copied {copied_kind}")
        self.copy_feedback_label.setVisible(True)
        self._copy_feedback_animation.stop()
        self._copy_feedback_effect.setOpacity(1.0)
        self._copy_feedback_animation.setStartValue(1.0)
        self._copy_feedback_animation.setEndValue(0.0)
        self._copy_feedback_animation.start()
        self.statusBar().showMessage(f"Copied: {value}")

    def _hide_copy_feedback(self) -> None:
        self.copy_feedback_label.setVisible(False)

    def _render_heuristic(
        self,
        analysis: AnalysisResult,
        elapsed_seconds: float,
        created: bool,
    ) -> None:
        largest = max((file.size_bytes for file in analysis.matched.files), default=0)
        lines = [
            "Strategy",
            analysis.plan.heuristic,
            "",
            "Why this is fast",
            "- The app normalizes the pasted names first.",
            "- The folder scan checks filename/stem before reading file size.",
            "- Only matched files are planned and zipped.",
            "- Zip parts are created on a worker thread so the UI stays responsive.",
            "- Independent zip parts are written in parallel with fast compression.",
            "",
            "Verification",
            "- Planning uses source file sizes as a conservative estimate.",
            "- Creation writes each zip part to disk and checks the real .zip size.",
            "- If a real zip exceeds the limit, the app stops and reports it.",
            "",
            "Numbers",
            f"- Requested names: {len(analysis.matched.requested_names)}",
            f"- Found files: {len(analysis.matched.files)}",
            f"- Missing names: {len(analysis.matched.missing_names)}",
            f"- Planned zip parts: {len(analysis.plan.batches)}",
            f"- Source size: {_format_bytes(analysis.total_size_bytes)}",
            f"- Largest file: {_format_bytes(largest)}",
            f"- Limit per zip: {_format_bytes(analysis.plan.max_size_bytes)}",
            f"- {'Creation' if created else 'Analysis'} time: {elapsed_seconds:.2f}s",
        ]
        self.heuristic_output.setPlainText("\n".join(lines))

    def _clear_tables(self) -> None:
        self.plan_table.setRowCount(0)
        self.found_table.setRowCount(0)
        self.missing_table.setRowCount(0)

    def _set_summary(
        self,
        analysis: AnalysisResult | None = None,
        elapsed_seconds: float | None = None,
    ) -> None:
        if analysis is None:
            requested = len(self._raw_names())
            found = missing = zips = source_size = 0
        else:
            requested = len(analysis.matched.requested_names)
            found = len(analysis.matched.files)
            missing = len(analysis.matched.missing_names)
            zips = len(analysis.plan.batches)
            source_size = analysis.total_size_bytes

        self.requested_count_label.setText(f"Names {requested}")
        self.found_count_label.setText(f"Found {found}")
        self.missing_count_label.setText(f"Missing {missing}")
        self.zip_count_label.setText(f"Zips {zips}")
        self.size_label.setText(f"Source {_format_bytes(source_size)}")
        self.time_label.setText("Time -" if elapsed_seconds is None else f"Time {elapsed_seconds:.2f}s")

    def _update_requested_count(self) -> None:
        self.requested_count_label.setText(f"Names {len(self._raw_names())}")

    def _invalidate_analysis(self, *_args) -> None:
        self._last_analysis = None
        self.create_button.setEnabled(False)
        self.progress_label.setText("Idle")
        self.progress_bar.setValue(0)

    def _validate_inputs(self, require_output: bool) -> bool:
        if not self.source_input.text().strip():
            self._show_error("Choose a source folder first.")
            return False

        if not self.names_input.toPlainText().strip():
            self._show_error("Paste at least one name.")
            return False

        if require_output and not self.output_input.text().strip():
            self._show_error("Choose an output folder.")
            return False

        return True

    def _rebuild_controller(self) -> None:
        services = build_services(recursive=self.recursive_input.isChecked())
        self._controller = CompactFilesController(services)
        self._invalidate_analysis()
        self.statusBar().showMessage("Search mode updated")

    def _source_folder(self) -> Path:
        return Path(self.source_input.text().strip())

    def _output_folder(self) -> Path:
        return Path(self.output_input.text().strip())

    def _raw_names(self) -> list[str]:
        return [
            line.strip()
            for line in self.names_input.toPlainText().splitlines()
            if line.strip()
        ]

    def _set_busy(self, busy: bool, message: str = "") -> None:
        self.analyze_button.setEnabled(not busy)
        self.create_button.setEnabled(not busy)
        self.statusBar().showMessage(message if busy else "Ready")
        if busy:
            QGuiApplication.setOverrideCursor(Qt.WaitCursor)
        else:
            QGuiApplication.restoreOverrideCursor()

    def _set_creating(self, creating: bool) -> None:
        self.analyze_button.setEnabled(not creating)
        self.create_button.setEnabled(not creating)
        self.source_button.setEnabled(not creating)
        self.output_button.setEnabled(not creating)
        self.names_input.setEnabled(not creating)
        self.max_size_input.setEnabled(not creating)
        self.recursive_input.setEnabled(not creating)
        if creating:
            self.progress_bar.setValue(0)
            self.progress_label.setText("Starting")

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "COMPLAT", message)

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QWidget {
                background: #0f172a;
                color: #e5e7eb;
                font-size: 13px;
            }
            QWidget#root {
                background: #0f172a;
            }
            QWidget#panel, QTabWidget::pane {
                background: #111827;
                border: 1px solid #253044;
                border-radius: 8px;
            }
            QLabel {
                background: transparent;
                color: #cbd5e1;
            }
            QWidget#header {
                background: transparent;
            }
            QLabel#appTitle {
                color: #f8fafc;
                font-size: 18px;
                font-weight: 900;
                letter-spacing: 0;
            }
            QLabel#appSubtitle {
                color: #94a3b8;
                font-size: 12px;
            }
            QLabel#metric {
                background: #172033;
                border: 1px solid #263449;
                border-radius: 6px;
                color: #f8fafc;
                padding: 8px 10px;
                font-weight: 600;
            }
            QLabel#progressLabel {
                background: transparent;
                color: #93c5fd;
                font-weight: 700;
                min-width: 64px;
            }
            QLabel#copyFeedback {
                background: #064e3b;
                border: 1px solid #10b981;
                border-radius: 999px;
                color: #bbf7d0;
                font-weight: 800;
                padding: 6px 12px;
            }
            QProgressBar {
                background: #0b1220;
                border: 1px solid #334155;
                border-radius: 6px;
                min-width: 180px;
                max-width: 240px;
                min-height: 10px;
            }
            QProgressBar::chunk {
                background: #3b82f6;
                border-radius: 5px;
            }
            QLineEdit, QPlainTextEdit, QSpinBox, QTableWidget {
                background: #0b1220;
                border: 1px solid #334155;
                border-radius: 6px;
                color: #f8fafc;
                padding: 7px;
                selection-background-color: #2563eb;
                selection-color: #ffffff;
            }
            QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QTableWidget:focus {
                border: 1px solid #3b82f6;
            }
            QCheckBox {
                background: transparent;
                color: #cbd5e1;
            }
            QPushButton {
                background: #2563eb;
                border: 1px solid #2563eb;
                border-radius: 6px;
                color: #ffffff;
                font-weight: 700;
                min-height: 32px;
                padding: 4px 14px;
            }
            QPushButton:hover {
                background: #1d4ed8;
                border-color: #1d4ed8;
            }
            QPushButton:disabled {
                background: #334155;
                border-color: #334155;
                color: #94a3b8;
            }
            QTabBar::tab {
                background: #111827;
                border: 1px solid #253044;
                color: #94a3b8;
                padding: 9px 14px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
            QTabBar::tab:selected {
                background: #1e293b;
                color: #f8fafc;
                border-bottom-color: #1e293b;
            }
            QTableWidget {
                gridline-color: #253044;
                alternate-background-color: #101a2e;
            }
            QTableWidget::item {
                padding: 4px;
            }
            QHeaderView::section {
                background: #1e293b;
                border: 0;
                border-right: 1px solid #334155;
                color: #f8fafc;
                font-weight: 700;
                padding: 8px;
            }
            QSplitter::handle {
                background: #253044;
            }
            QSplitter::handle:horizontal {
                width: 6px;
            }
            QStatusBar {
                background: #0f172a;
                color: #94a3b8;
            }
            """
        )


def _format_bytes(value: int) -> str:
    if value < 1024:
        return f"{value} B"
    if value < 1024 * 1024:
        return f"{value / 1024:.1f} KB"
    return f"{value / (1024 * 1024):.1f} MB"

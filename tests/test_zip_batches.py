from pathlib import Path
from zipfile import ZIP_STORED, ZipFile

import pytest

from complat.application.cancellation import CancellationToken
from complat.application.errors import ArchiveAlreadyExists, FileExceedsZipLimit
from complat.application.errors import OperationCancelled
from complat.application.use_cases import AnalyzeZipPlanUseCase, CompareNamesUseCase, CreateZipBatchesUseCase
from complat.domain.entities import FileCandidate
from complat.domain.services import FileNameMatcher, NameNormalizer, ZipPlanner
from complat.infrastructure.filesystem import LocalFileFinder
from complat.infrastructure.zip_writer import ZipArchiveWriter


def test_create_zip_batches_creates_multiple_parts(tmp_path: Path) -> None:
    source = tmp_path / "source"
    output = tmp_path / "out"
    source.mkdir()
    (source / "alpha.txt").write_text("a" * 100, encoding="utf-8")
    (source / "beta.txt").write_text("b" * 100, encoding="utf-8")

    use_case = _build_create_use_case()
    result = use_case.execute(
        folder=source,
        raw_names=["alpha.txt", "beta.txt"],
        output_folder=output,
        max_size_bytes=160,
    )

    assert len(result.archives) == 2
    assert all(archive.path.exists() for archive in result.archives)


def test_create_zip_batches_returns_archives_in_plan_order(tmp_path: Path) -> None:
    source = tmp_path / "source"
    output = tmp_path / "out"
    source.mkdir()

    for name in ("alpha.txt", "beta.txt", "gamma.txt"):
        (source / name).write_text("x" * 100, encoding="utf-8")

    use_case = _build_create_use_case()
    result = use_case.execute(
        folder=source,
        raw_names=["alpha.txt", "beta.txt", "gamma.txt"],
        output_folder=output,
        max_size_bytes=180,
    )

    assert [archive.path.name for archive in result.archives] == [
        "complat_part_001.zip",
        "complat_part_002.zip",
        "complat_part_003.zip",
    ]


def test_create_zip_batches_reports_realtime_byte_progress(tmp_path: Path) -> None:
    source = tmp_path / "source"
    output = tmp_path / "out"
    source.mkdir()
    (source / "alpha.bin").write_bytes(b"x" * ((1024 * 1024 * 2) + 512))
    events: list[tuple[int, int, str]] = []

    use_case = _build_create_use_case()
    use_case.execute(
        folder=source,
        raw_names=["alpha.bin"],
        output_folder=output,
        max_size_bytes=3 * 1024 * 1024,
        progress_callback=lambda completed, total, message: events.append((completed, total, message)),
    )

    writing_events = [event for event in events if event[2].startswith("Writing part 001:")]

    assert len(writing_events) >= 2
    assert writing_events[-1][0] == writing_events[-1][1]


def test_create_zip_batches_rejects_single_file_over_limit(tmp_path: Path) -> None:
    source = tmp_path / "source"
    output = tmp_path / "out"
    source.mkdir()
    (source / "alpha.txt").write_text("content", encoding="utf-8")

    use_case = _build_create_use_case()

    with pytest.raises(FileExceedsZipLimit):
        use_case.execute(
            folder=source,
            raw_names=["alpha.txt"],
            output_folder=output,
            max_size_bytes=1,
        )


def test_compare_names_keeps_original_missing_name_text(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "alpha.txt").write_text("content", encoding="utf-8")

    use_case = _build_compare_use_case()
    result = use_case.execute(source, ["Alpha", "Maria Silva"])

    assert result.missing_names == ("Maria Silva",)


def test_compare_names_searches_name_but_keeps_number_for_missing(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "RICARDO DOS SANTOS GUIMARAES.pdf").write_text("content", encoding="utf-8")

    use_case = _build_compare_use_case()
    result = use_case.execute(
        source,
        [
            "45119983\tRICARDO DOS SANTOS GUIMARAES",
            "43479201\tMAYCON FERREIRA VALENTE",
        ],
    )

    assert len(result.files) == 1
    assert result.missing_names == ("43479201\tMAYCON FERREIRA VALENTE",)


def test_analyze_zip_plan_defaults_to_requested_order_for_missing_names(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "alpha.txt").write_text("content", encoding="utf-8")

    use_case = _build_analyze_use_case()
    result = use_case.execute(source, ["Maria Silva", "alpha.txt"], 1024)

    assert result.matched.missing_names == ("Maria Silva",)
    assert len(result.plan.batches) == 1


def test_zip_planner_reserves_zip_metadata_overhead() -> None:
    files = (
        FileCandidate(Path("alpha.txt"), 400),
        FileCandidate(Path("beta.txt"), 400),
    )

    plan = ZipPlanner().plan(files, 1000)

    assert len(plan.batches) == 2
    assert "safety margin" in plan.heuristic


def test_local_file_finder_reuses_folder_index_for_different_queries(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "alpha.txt").write_text("alpha", encoding="utf-8")
    (source / "beta.txt").write_text("beta", encoding="utf-8")
    finder = LocalFileFinder()

    first = finder.find(source, {"alpha.txt": "alpha.txt"})
    second = finder.find(source, {"beta.txt": "beta.txt"})

    assert [file.filename for file in first] == ["alpha.txt"]
    assert [file.filename for file in second] == ["beta.txt"]


def test_local_file_finder_clear_cache_refreshes_folder_index(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    finder = LocalFileFinder()

    assert finder.find(source, {"alpha.txt": "alpha.txt"}) == ()

    (source / "alpha.txt").write_text("alpha", encoding="utf-8")
    finder.clear_cache()
    result = finder.find(source, {"alpha.txt": "alpha.txt"})

    assert [file.filename for file in result] == ["alpha.txt"]


def test_local_file_finder_matches_folders_when_enabled(tmp_path: Path) -> None:
    source = tmp_path / "source"
    folder = source / "Cliente A"
    source.mkdir()
    folder.mkdir()
    (folder / "contrato.pdf").write_bytes(b"contract")
    finder = LocalFileFinder(scan_mode="folders")

    result = finder.find(source, {"cliente a": "cliente a"})

    assert len(result) == 1
    assert result[0].filename == "Cliente A"
    assert result[0].is_directory
    assert result[0].size_bytes == len(b"contract")


def test_create_zip_batches_can_zip_matched_folder_tree(tmp_path: Path) -> None:
    source = tmp_path / "source"
    output = tmp_path / "out"
    folder = source / "Cliente A"
    nested = folder / "documentos"
    nested.mkdir(parents=True)
    (folder / "contrato.pdf").write_bytes(b"contract")
    (nested / "rg.txt").write_text("rg", encoding="utf-8")

    use_case = _build_create_use_case(scan_mode="folders")
    result = use_case.execute(
        folder=source,
        raw_names=["Cliente A"],
        output_folder=output,
        max_size_bytes=1024,
    )

    with ZipFile(result.archives[0].path) as archive:
        names = set(archive.namelist())

    assert "Cliente A/contrato.pdf" in names
    assert "Cliente A/documentos/rg.txt" in names


def test_create_zip_batches_stops_when_cancelled_before_creation(tmp_path: Path) -> None:
    source = tmp_path / "source"
    output = tmp_path / "out"
    source.mkdir()
    (source / "alpha.txt").write_text("content", encoding="utf-8")
    analysis = _build_analyze_use_case().execute(source, ["alpha.txt"], 1024)
    token = CancellationToken()
    token.cancel()

    with pytest.raises(OperationCancelled):
        _build_create_use_case().execute_from_analysis(
            analysis=analysis,
            output_folder=output,
            cancellation_token=token,
        )


def test_create_zip_batches_rejects_existing_output_archive(tmp_path: Path) -> None:
    source = tmp_path / "source"
    output = tmp_path / "out"
    source.mkdir()
    output.mkdir()
    (source / "alpha.txt").write_text("content", encoding="utf-8")
    (output / "complat_part_001.zip").write_text("existing", encoding="utf-8")

    with pytest.raises(ArchiveAlreadyExists):
        _build_create_use_case().execute(
            folder=source,
            raw_names=["alpha.txt"],
            output_folder=output,
            max_size_bytes=1024,
        )


def test_create_zip_batches_removes_temp_archive_after_success(tmp_path: Path) -> None:
    source = tmp_path / "source"
    output = tmp_path / "out"
    source.mkdir()
    (source / "alpha.txt").write_text("content", encoding="utf-8")

    result = _build_create_use_case().execute(
        folder=source,
        raw_names=["alpha.txt"],
        output_folder=output,
        max_size_bytes=1024,
    )

    assert result.archives[0].path.exists()
    assert not (output / "complat_part_001.zip.tmp").exists()


def test_fast_compression_stores_already_compressed_extensions(tmp_path: Path) -> None:
    source = tmp_path / "source"
    output = tmp_path / "out"
    source.mkdir()
    (source / "document.pdf").write_bytes(b"%PDF-1.4 content")

    result = _build_create_use_case().execute(
        folder=source,
        raw_names=["document.pdf"],
        output_folder=output,
        max_size_bytes=1024,
    )

    with ZipFile(result.archives[0].path) as archive:
        info = archive.getinfo("document.pdf")

    assert info.compress_type == ZIP_STORED


def _build_compare_use_case(scan_mode: str = "files") -> CompareNamesUseCase:
    normalizer = NameNormalizer()
    matcher = FileNameMatcher(normalizer)
    file_finder = LocalFileFinder(scan_mode=scan_mode)
    return CompareNamesUseCase(file_finder, matcher, normalizer)


def _build_analyze_use_case(scan_mode: str = "files") -> AnalyzeZipPlanUseCase:
    return AnalyzeZipPlanUseCase(_build_compare_use_case(scan_mode), ZipPlanner())


def _build_create_use_case(scan_mode: str = "files") -> CreateZipBatchesUseCase:
    return CreateZipBatchesUseCase(_build_analyze_use_case(scan_mode), ZipArchiveWriter())

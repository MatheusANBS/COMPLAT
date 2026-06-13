from pathlib import Path

import pytest

from complat.application.errors import FileExceedsZipLimit
from complat.application.use_cases import AnalyzeZipPlanUseCase, CompareNamesUseCase, CreateZipBatchesUseCase
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


def _build_compare_use_case() -> CompareNamesUseCase:
    normalizer = NameNormalizer()
    matcher = FileNameMatcher(normalizer)
    file_finder = LocalFileFinder()
    return CompareNamesUseCase(file_finder, matcher, normalizer)


def _build_analyze_use_case() -> AnalyzeZipPlanUseCase:
    return AnalyzeZipPlanUseCase(_build_compare_use_case(), ZipPlanner())


def _build_create_use_case() -> CreateZipBatchesUseCase:
    return CreateZipBatchesUseCase(_build_analyze_use_case(), ZipArchiveWriter())

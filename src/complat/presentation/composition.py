from __future__ import annotations

from dataclasses import dataclass

from complat.application.use_cases import (
    AnalyzeZipPlanUseCase,
    CompareNamesUseCase,
    CreateZipBatchesUseCase,
)
from complat.domain.services import FileNameMatcher, NameNormalizer, ZipPlanner
from complat.infrastructure.filesystem import LocalFileFinder
from complat.infrastructure.zip_writer import ZipArchiveWriter


@dataclass(frozen=True)
class ApplicationServices:
    compare_names: CompareNamesUseCase
    analyze_zip_plan: AnalyzeZipPlanUseCase
    create_zip_batches: CreateZipBatchesUseCase


def build_services(recursive: bool = False) -> ApplicationServices:
    file_finder = LocalFileFinder(recursive=recursive)
    normalizer = NameNormalizer()
    matcher = FileNameMatcher(normalizer)
    compare_names = CompareNamesUseCase(file_finder, matcher, normalizer)
    analyze_zip_plan = AnalyzeZipPlanUseCase(compare_names, ZipPlanner())

    return ApplicationServices(
        compare_names=compare_names,
        analyze_zip_plan=analyze_zip_plan,
        create_zip_batches=CreateZipBatchesUseCase(
            analyze_zip_plan,
            ZipArchiveWriter(),
            max_workers=4,
        ),
    )

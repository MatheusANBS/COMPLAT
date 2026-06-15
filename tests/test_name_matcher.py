from pathlib import Path

from complat.domain.entities import FileCandidate
from complat.domain.services import FileNameMatcher, NameNormalizer


def test_matcher_finds_files_by_exact_filename() -> None:
    normalizer = NameNormalizer()
    matcher = FileNameMatcher(normalizer)
    files = (FileCandidate(Path("Contract.PDF"), 10),)

    result = matcher.match(("contract.pdf",), files)

    assert result.files == files
    assert result.missing_names == ()


def test_matcher_finds_files_by_stem() -> None:
    normalizer = NameNormalizer()
    matcher = FileNameMatcher(normalizer)
    files = (FileCandidate(Path("invoice-001.xlsx"), 10),)

    result = matcher.match(("invoice-001",), files)

    assert result.files == files
    assert result.missing_names == ()


def test_normalizer_removes_blank_and_duplicate_names() -> None:
    normalizer = NameNormalizer()

    result = normalizer.normalize_many([" Report ", "", "report", "Other"])

    assert result == ("report", "other")


def test_normalizer_parses_number_and_name_line() -> None:
    normalizer = NameNormalizer()

    result = normalizer.parse_requested_name("45119983\tRICARDO DOS SANTOS GUIMARAES")

    assert result.lookup_name == "RICARDO DOS SANTOS GUIMARAES"
    assert result.display_name == "45119983\tRICARDO DOS SANTOS GUIMARAES"


def test_normalizer_parses_plain_name_line() -> None:
    normalizer = NameNormalizer()

    result = normalizer.parse_requested_name("MARIA SILVA")

    assert result.lookup_name == "MARIA SILVA"
    assert result.display_name == "MARIA SILVA"

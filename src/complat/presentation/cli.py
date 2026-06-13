from __future__ import annotations

import argparse
import sys
from pathlib import Path

from complat.application.errors import ApplicationError
from complat.presentation.composition import build_services


def main() -> None:
    args = _parse_args()

    if not args.folder:
        raise SystemExit("Pass --folder, or use the PySide UI with complat-ui.")

    output_folder = args.output_folder or args.folder / "complat_output"
    raw_names = _read_names(args)
    max_size_bytes = args.max_mb * 1024 * 1024
    services = build_services(recursive=args.recursive)

    try:
        if args.analyze_only:
            analysis = services.analyze_zip_plan.execute(
                args.folder,
                raw_names,
                max_size_bytes,
            )
            _print_analysis(analysis)
            return

        result = services.create_zip_batches.execute(
            args.folder,
            raw_names,
            output_folder,
            max_size_bytes,
        )
    except ApplicationError as error:
        raise SystemExit(f"Could not create zip parts: {error}") from error

    _print_analysis(result.analysis)
    print("Created archives:")
    for archive in result.archives:
        print(f"- {archive.path} ({_format_bytes(archive.actual_size_bytes)})")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Split named files from a folder into size-limited zip parts."
    )
    parser.add_argument("--folder", type=Path, help="Folder to scan.")
    parser.add_argument("--names-file", type=Path, help="Text file with one name per line.")
    parser.add_argument("--output-folder", type=Path, help="Destination folder for zip parts.")
    parser.add_argument("--max-mb", type=int, default=9, help="Maximum size per zip in MB.")
    parser.add_argument("--analyze-only", action="store_true", help="Only show the zip plan.")
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Scan subfolders too.",
    )

    return parser.parse_args()


def _read_names(args: argparse.Namespace) -> list[str]:
    if args.names_file:
        return args.names_file.read_text(encoding="utf-8").splitlines()

    print("Paste one file name per line. Finish with Ctrl+Z then Enter on Windows.")
    return [line.rstrip("\n") for line in sys.stdin]


def _print_analysis(analysis) -> None:
    print(f"Matched files: {len(analysis.matched.files)}")
    print(f"Missing names: {len(analysis.matched.missing_names)}")
    print(f"Planned zip parts: {len(analysis.plan.batches)}")
    print(f"Source size: {_format_bytes(analysis.total_size_bytes)}")

    if analysis.matched.missing_names:
        print("Missing:")
        for name in analysis.matched.missing_names:
            print(f"- {name}")

    print("Plan:")
    for batch in analysis.plan.batches:
        print(
            f"- part {batch.number:03d}: "
            f"{batch.file_count} file(s), {_format_bytes(batch.total_size_bytes)} estimated"
        )


def _format_bytes(value: int) -> str:
    if value < 1024:
        return f"{value} B"
    if value < 1024 * 1024:
        return f"{value / 1024:.1f} KB"
    return f"{value / (1024 * 1024):.1f} MB"


if __name__ == "__main__":
    main()

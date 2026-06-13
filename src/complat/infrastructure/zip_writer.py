from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from complat.domain.entities import FileCandidate, ZipArchive, ZipBatch


class ZipArchiveWriter:
    def __init__(self, compresslevel: int = 1) -> None:
        self._compresslevel = compresslevel

    def write_batch(
        self,
        output_folder: Path,
        batch: ZipBatch,
        max_size_bytes: int,
    ) -> ZipArchive:
        output_folder.mkdir(parents=True, exist_ok=True)
        output_path = output_folder / f"complat_part_{batch.number:03d}.zip"

        with ZipFile(
            output_path,
            mode="w",
            compression=ZIP_DEFLATED,
            compresslevel=self._compresslevel,
        ) as archive:
            for arcname, file in self._unique_archive_names(batch):
                archive.write(file.path, arcname=arcname)

        return ZipArchive(
            path=output_path,
            file_count=batch.file_count,
            max_size_bytes=max_size_bytes,
            estimated_size_bytes=batch.total_size_bytes,
            actual_size_bytes=output_path.stat().st_size,
        )

    def _unique_archive_names(
        self,
        batch: ZipBatch,
    ) -> tuple[tuple[str, FileCandidate], ...]:
        names: list[tuple[str, FileCandidate]] = []
        used_names: dict[str, int] = {}

        for file in batch.files:
            filename = file.filename
            count = used_names.get(filename.casefold(), 0)
            used_names[filename.casefold()] = count + 1

            if count:
                filename = f"{file.path.stem}_{count + 1}{file.path.suffix}"

            names.append((filename, file))

        return tuple(names)

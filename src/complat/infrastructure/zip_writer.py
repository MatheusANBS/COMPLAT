from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile, ZipInfo

from complat.application.cancellation import CancellationToken
from complat.domain.entities import FileCandidate, ZipArchive, ZipBatch


class ZipArchiveWriter:
    _CHUNK_SIZE = 1024 * 1024
    _STORED_EXTENSIONS = {
        ".7z",
        ".avi",
        ".jpeg",
        ".jpg",
        ".mp4",
        ".pdf",
        ".png",
        ".rar",
        ".webp",
        ".zip",
    }

    def __init__(
        self,
        compression_mode: CompressionMode | str = "fast",
    ) -> None:
        self._compression_mode = CompressionMode.from_value(compression_mode)
        self._compresslevel = self._compression_mode.compresslevel

    def write_batch(
        self,
        output_folder: Path,
        batch: ZipBatch,
        max_size_bytes: int,
        progress_callback: Callable[[int, str], None] | None = None,
        cancellation_token: CancellationToken | None = None,
    ) -> ZipArchive:
        output_folder.mkdir(parents=True, exist_ok=True)
        output_path = output_folder / f"complat_part_{batch.number:03d}.zip"
        temp_path = output_path.with_suffix(output_path.suffix + ".tmp")

        try:
            with ZipFile(
                temp_path,
                mode="w",
                compression=ZIP_DEFLATED,
                compresslevel=self._compresslevel,
            ) as archive:
                for arcname, file in self._unique_archive_names(batch):
                    if cancellation_token:
                        cancellation_token.raise_if_cancelled()

                    zip_info = ZipInfo.from_file(file.path, arcname)
                    zip_info.compress_type = self._compression_for(file)
                    self._write_file(
                        archive=archive,
                        file=file,
                        zip_info=zip_info,
                        batch_number=batch.number,
                        progress_callback=progress_callback,
                        cancellation_token=cancellation_token,
                    )
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise

        actual_size_bytes = temp_path.stat().st_size
        temp_path.replace(output_path)

        return ZipArchive(
            path=output_path,
            file_count=batch.file_count,
            max_size_bytes=max_size_bytes,
            estimated_size_bytes=batch.total_size_bytes,
            actual_size_bytes=actual_size_bytes,
        )

    def _write_file(
        self,
        archive: ZipFile,
        file: FileCandidate,
        zip_info: ZipInfo,
        batch_number: int,
        progress_callback: Callable[[int, str], None] | None,
        cancellation_token: CancellationToken | None,
    ) -> None:
        message = f"Writing part {batch_number:03d}: {file.filename}"
        with file.path.open("rb") as source, archive.open(zip_info, "w") as target:
            while True:
                if cancellation_token:
                    cancellation_token.raise_if_cancelled()

                chunk = source.read(self._CHUNK_SIZE)
                if not chunk:
                    break

                target.write(chunk)
                if progress_callback:
                    progress_callback(len(chunk), message)

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

    def _compression_for(self, file: FileCandidate) -> int:
        if self._compression_mode == CompressionMode.FAST and file.path.suffix.casefold() in self._STORED_EXTENSIONS:
            return ZIP_STORED

        return ZIP_DEFLATED


class CompressionMode(StrEnum):
    FAST = "fast"
    BALANCED = "balanced"
    SMALLER = "smaller"

    @classmethod
    def from_value(cls, value: CompressionMode | str) -> CompressionMode:
        if isinstance(value, cls):
            return value

        normalized = value.strip().casefold()
        for mode in cls:
            if mode.value == normalized:
                return mode

        raise ValueError(f"Unknown compression mode: {value}")

    @property
    def compresslevel(self) -> int:
        if self == CompressionMode.FAST:
            return 1
        if self == CompressionMode.BALANCED:
            return 5
        return 9

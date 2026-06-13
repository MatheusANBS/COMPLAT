class ApplicationError(Exception):
    """Base exception for expected application failures."""


class FileExceedsZipLimit(ApplicationError):
    """Raised when a single file cannot fit in one zip under the configured limit."""

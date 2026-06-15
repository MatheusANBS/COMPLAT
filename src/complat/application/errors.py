class ApplicationError(Exception):
    """Base exception for expected application failures."""


class FileExceedsZipLimit(ApplicationError):
    """Raised when a single file cannot fit in one zip under the configured limit."""


class ArchiveAlreadyExists(ApplicationError):
    """Raised when a target archive already exists and would be overwritten."""


class OperationCancelled(ApplicationError):
    """Raised when the user cancels a long-running operation."""

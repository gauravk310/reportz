"""Custom exceptions for reportz."""


class ReportzError(Exception):
    """Base exception class for reportz."""


class ReportGenerationError(ReportzError):
    """Raised when report generation fails."""


class ReportSaveError(ReportzError):
    """Raised when saving a report fails."""

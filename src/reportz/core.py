"""Core abstractions and base classes for reportz."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Union


class BaseReport(ABC):
    """Abstract base class for all report generators in reportz."""

    @abstractmethod
    def generate_html(self, **kwargs: Any) -> str:
        """Generate and return standalone HTML markup for the report."""
        raise NotImplementedError

    @abstractmethod
    def save(
        self,
        filename: str = "report.html",
        save_file_path: Union[str, Path] = ".",
        open_browser: bool = False,
        **kwargs: Any,
    ) -> str:

        """Save the report to an HTML file and return its absolute path."""
        raise NotImplementedError

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Return the collected report data as a Python dictionary."""
        raise NotImplementedError

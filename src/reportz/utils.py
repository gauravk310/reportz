"""Utility functions and helpers for reportz."""

import os
import webbrowser
from pathlib import Path
from typing import Union


def resolve_report_path(
    filename: str = "system_report.html",
    save_file_path: Union[str, Path] = ".",
) -> Path:
    """Resolve destination file path given a filename and directory or file path.

    Handles flexible combinations:
    - filename='system_report.html', save_file_path='.'
    - filename='my_report.html', save_file_path='./reports'
    - filename='.', save_file_path='.' (resolves to ./system_report.html)
    - filename='path/to/my_report.html' (respects nested paths)
    """
    if not filename:
        filename = "system_report.html"

    file_p = Path(filename)
    save_p = Path(save_file_path).expanduser()

    # If user passed a directory path in the first argument, e.g. sys.save(".")
    if (
        str(filename) in (".", "..")
        or str(filename).endswith(("/", "\\"))
        or file_p.is_dir()
    ):
        save_p = file_p
        filename = "system_report.html"
        file_p = Path(filename)

    # If save_p is already an HTML file path:
    if save_p.suffix.lower() == ".html":
        target = save_p
    # If filename contains a path with directories (e.g. "out/my_report.html")
    elif len(file_p.parts) > 1:
        target = save_p / file_p
    else:
        if not filename.lower().endswith(".html"):
            filename = f"{filename}.html"
        target = save_p / filename

    target = target.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def open_in_browser(file_path: Union[str, Path]) -> bool:
    """Open a local file in the default web browser."""
    path = Path(file_path).resolve()
    try:
        return webbrowser.open(path.as_uri())
    except Exception:
        return webbrowser.open(str(path))


def format_bytes(bytes_value: float, suffix: str = "B") -> str:
    """Format bytes into a readable string (e.g. 16.00 GB)."""
    for unit in ["", "K", "M", "G", "T", "P"]:
        if abs(bytes_value) < 1024.0:
            return f"{bytes_value:.2f} {unit}{suffix}"
        bytes_value /= 1024.0
    return f"{bytes_value:.2f} E{suffix}"

from pathlib import Path
from reportz import utils


def test_utils_module_exists():
    assert utils is not None


def test_resolve_report_path():
    path = utils.resolve_report_path("my_report.html", ".")
    assert path.name == "my_report.html"
    assert path.is_absolute()

    # Automatic .html extension append
    path2 = utils.resolve_report_path("report_no_ext", ".")
    assert path2.name == "report_no_ext.html"


def test_format_bytes():
    assert "1.00 GB" in utils.format_bytes(1024**3)

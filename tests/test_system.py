"""Tests for SysInfo, SystemReport, and CLI."""

from pathlib import Path
import tempfile
import pytest

from reportz import SysInfo, SystemReport
from reportz.cli import build_parser, main


def test_sys_info_structure():
    """Verify that SysInfo collects all expected sections and keys."""
    info = SysInfo()
    data = info.all()

    assert "system" in data
    assert "cpu" in data
    assert "memory" in data
    assert "disk" in data
    assert "battery" in data
    assert "network" in data
    assert "uptime" in data
    assert "gpu" in data
    assert "processes" in data
    assert "drivers" in data
    assert "health" in data

    # Check system section
    sys_dict = info.system()
    assert "system" in sys_dict
    assert "node_name" in sys_dict
    assert "machine" in sys_dict

    # Check cpu section
    cpu_dict = info.cpu()
    assert "total_cores" in cpu_dict
    assert "cpu_usage_percent" in cpu_dict
    assert "cpu_per_core_usage" in cpu_dict

    # Check memory section
    mem_dict = info.memory()
    assert "total_ram_gb" in mem_dict
    assert "used_ram_gb" in mem_dict
    assert "ram_usage_percent" in mem_dict

    # Check disk section
    disks = info.disk()
    assert isinstance(disks, list)

    # Check uptime section
    uptime = info.uptime()
    assert "uptime_seconds" in uptime
    assert "uptime" in uptime


def test_system_report_save():
    """Verify that SystemReport generates and saves HTML matching advanced template."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        report = SystemReport()
        html = report.generate_html()

        assert "<!DOCTYPE html>" in html
        assert 'data-theme="dark"' in html
        assert "System Report" in html
        assert "cpuChart" in html
        assert "ramChart" in html
        assert "diskChart" in html
        assert "procChart" not in html
        assert "Driver Report" not in html
        assert "Connect Author :" in html
        assert "https://github.com/gauravk310" in html

        # Test light mode
        html_light = report.generate_html(dark_mode=False)
        assert 'data-theme="light"' in html_light

        # Save to custom directory and filename
        saved_path = report.save("test_report.html", tmp_dir, open_browser=False)
        saved_file = Path(saved_path)

        assert saved_file.exists()
        assert saved_file.name == "test_report.html"
        assert saved_file.parent == Path(tmp_dir).resolve()
        assert "<!DOCTYPE html>" in saved_file.read_text(encoding="utf-8")


def test_cli_parser_options():
    """Verify that CLI parser parses 'sys -o .' correctly."""
    parser = build_parser()

    # Case 1: reportz sys -o .
    args = parser.parse_args(["sys", "-o", "."])
    assert args.subcommand == "sys"
    assert args.open_browser is True
    assert args.path == "."

    # Case 2: reportz sys (defaults)
    args_default = parser.parse_args(["sys"])
    assert args_default.subcommand == "sys"
    assert args_default.open_browser is False
    assert args_default.path == "."

    # Case 3: reportz sys ./custom -o
    args_custom = parser.parse_args(["sys", "./custom", "-o"])
    assert args_custom.subcommand == "sys"
    assert args_custom.open_browser is True
    assert args_custom.path == "./custom"

    # Case 4: reportz sys --light
    args_light = parser.parse_args(["sys", "--light"])
    assert args_light.light_mode is True


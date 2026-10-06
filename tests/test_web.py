"""Tests for WebReport module and CLI web subcommand."""

from pathlib import Path
import tempfile
from unittest.mock import MagicMock, patch
import pytest

from reportz import WebReport
from reportz.cli import build_parser, handle_web_command


@pytest.fixture
def sample_scan_data():
    """Mock scan data dictionary for testing report builders without network requests."""
    return {
        "url": "https://example.com",
        "final_url": "https://example.com",
        "domain": "example.com",
        "ip": "93.184.216.34",
        "scheme": "https",
        "status_code": 200,
        "server": "ECS (dcb/7f83)",
        "content_type": "text/html; charset=UTF-8",
        "encoding": "UTF-8",
        "page_size_kb": 1.2,
        "ttfb": 120.5,
        "redirect_chain": ["https://example.com"],
        "has_robots": True,
        "has_sitemap": False,
        "fav": True,
        "headers": {
            "Server": "ECS (dcb/7f83)",
            "Content-Type": "text/html; charset=UTF-8",
            "Content-Encoding": "gzip",
            "Cache-Control": "max-age=604800",
        },
        "security_score": 75,
        "seo_score": 82,
        "perf_score": 90,
        "a11y_score": 85,
        "overall_score": 83,
        "risk_level": "Low",
        "sec": {
            "https": True,
            "hsts": False,
            "csp": False,
            "xframe": False,
            "ref": False,
            "xcto": False,
            "perms": False,
            "xxss": False,
            "ssl": {
                "issuer": "DigiCert Global Root G2",
                "subject": "example.com",
                "not_after": "Jan 15 12:00:00 2027 GMT",
                "not_before": "Jan 15 12:00:00 2025 GMT",
                "tls_version": "TLSv1.3",
                "days_left": 120,
                "valid": True,
            },
            "cookies": [],
            "disclosure": {},
            "cors": "Not Set",
            "exposed_paths": [],
        },
        "sec_issues": [
            {"severity": "high", "issue": "HSTS missing", "detail": "Add HSTS header"}
        ],
        "seo": {
            "title": "Example Domain",
            "title_len": 14,
            "meta_desc": "Illustrative domain for documentation examples",
            "meta_desc_len": 46,
            "headings": {"h1": ["Example Domain"], "h2": [], "h3": [], "h4": [], "h5": [], "h6": []},
            "canonical": "",
            "og": {"og:title": "Example Domain"},
            "twitter": {},
            "structured_data": 0,
            "internal_links": 1,
            "external_links": 1,
            "images_total": 0,
            "images_no_alt": 0,
            "viewport": True,
            "has_robots": True,
            "has_sitemap": False,
        },
        "seo_issues": ["No canonical URL specified"],
        "perf": {
            "ttfb": 120.5,
            "page_size_kb": 1.2,
            "compressed": True,
            "cache_control": "max-age=604800",
            "etag": "",
            "encoding": "gzip",
            "scripts": 0,
            "css": 0,
            "images": 0,
            "last_modified": "",
        },
        "perf_issues": [],
        "a11y": {
            "lang": True,
            "aria_labels": 0,
            "roles": 0,
            "unlabeled_inputs": 0,
            "empty_buttons": 0,
            "missing_alts": 0,
        },
        "a11y_issues": [],
        "techs": [{"name": "Cloudflare", "cat": "CDN", "via": "header"}],
        "dns": {"cdn": "Cloudflare", "A": ["93.184.216.34"]},
        "scan_time": "2026-10-06 12:00:00 UTC",
    }


def test_web_report_init_and_scan(sample_scan_data):
    """Test WebReport initialization and mocking scan execution."""
    with patch("reportz.modules.web.run_web_scan", return_value=sample_scan_data):
        web = WebReport("https://example.com")
        assert web.url == "https://example.com"
        assert web.dark_mode is True

        data = web.all()
        assert data["domain"] == "example.com"
        assert data["overall_score"] == 83
        assert data["security_score"] == 75

        summary = web.summary()
        assert summary["domain"] == "example.com"
        assert summary["overall_score"] == 83
        assert summary["risk_level"] == "Low"


def test_web_report_save_signature(sample_scan_data):
    """Verify web.save('filename', url, darkmode) works as requested."""
    with patch("reportz.modules.web.run_web_scan", return_value=sample_scan_data):
        with tempfile.TemporaryDirectory() as tmp_dir:
            web = WebReport()

            # Positional arguments: save("filename", url, darkmode)
            out_file = Path(tmp_dir) / "test_report.html"
            saved_path = web.save(
                str(out_file),
                "https://example.com",
                False,  # dark_mode = False (light mode)
                open_browser=False,
            )

            p = Path(saved_path)
            assert p.exists()
            assert p.is_file()
            assert p.name == "test_report.html"

            # Check that sections and assets directories were created
            base_dir = p.parent
            sections_dir = base_dir / "sections"
            assets_dir = base_dir / "assets"
            assert sections_dir.exists()
            assert assets_dir.exists()
            assert (assets_dir / "shared.css").exists()
            assert (sections_dir / "summary.html").exists()
            assert (sections_dir / "security.html").exists()
            assert (sections_dir / "seo.html").exists()
            assert (sections_dir / "performance.html").exists()
            assert (sections_dir / "accessibility.html").exists()
            assert (sections_dir / "technologies.html").exists()
            assert (sections_dir / "dns.html").exists()
            assert (sections_dir / "charts.html").exists()
            assert (base_dir / "summary.json").exists()

            content = p.read_text(encoding="utf-8")
            assert "data-theme=\"light\"" in content
            assert "WebAnalyzer" in content
            assert "example.com" in content
            assert "Connect Author" in content or "Gaurav Kadam" in content


def test_cli_web_parser():
    """Verify that CLI parser parses 'web <url> . -o --light' correctly."""
    parser = build_parser()

    # Case 1: reportz web https://example.com . -o --light
    args = parser.parse_args(["web", "https://example.com", ".", "-o", "--light"])
    assert args.subcommand == "web"
    assert args.url == "https://example.com"
    assert args.path == "."
    assert args.open_browser is True
    assert args.light_mode is True

    # Case 2: default options
    args_default = parser.parse_args(["web", "https://example.com"])
    assert args_default.subcommand == "web"
    assert args_default.url == "https://example.com"
    assert args_default.path == "."
    assert args_default.open_browser is False
    assert args_default.light_mode is False
    assert args_default.dark_mode is True
    assert args_default.filename == "web_report.html"
    assert args_default.delay == 0


def test_handle_web_command(sample_scan_data):
    """Test CLI handle_web_command execution."""
    parser = build_parser()
    args = parser.parse_args(["web", "https://example.com", "--light"])

    with patch("reportz.modules.web.run_web_scan", return_value=sample_scan_data):
        with tempfile.TemporaryDirectory() as tmp_dir:
            args.path = tmp_dir
            exit_code = handle_web_command(args)
            assert exit_code == 0
            assert (Path(tmp_dir) / "web_report.html").exists()

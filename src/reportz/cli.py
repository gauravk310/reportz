"""Command-line interface for reportz."""

import argparse
import os
from pathlib import Path
import sys
from typing import List, Optional

from reportz import __version__
from reportz.modules.system import SystemReport
from reportz.modules.web import WebReport


def build_parser() -> argparse.ArgumentParser:
    """Build and configure the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="reportz",
        description="reportz - Automated Diagnostic and Reporting Toolkit",
    )
    parser.add_argument(
        "-v", "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(
        dest="subcommand",
        title="commands",
        metavar="<command>",
    )

    # Subcommand: sys
    sys_parser = subparsers.add_parser(
        "sys",
        help="Generate an interactive HTML system diagnostic report",
        description="Collect system telemetry and generate an interactive HTML report.",
    )
    sys_parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Directory or file path where report should be saved (default: .)",
    )
    sys_parser.add_argument(
        "-o", "--open",
        action="store_true",
        dest="open_browser",
        help="Automatically open the generated report in default web browser",
    )
    sys_parser.add_argument(
        "-f", "--filename",
        default="system_report.html",
        help="Filename for the HTML report (default: system_report.html)",
    )
    sys_parser.add_argument(
        "--light",
        action="store_true",
        dest="light_mode",
        help="Generate report in light mode (default is dark mode)",
    )
    sys_parser.add_argument(
        "--dark",
        action="store_true",
        dest="dark_mode",
        default=True,
        help="Generate report in dark mode (default)",
    )

    # Subcommand: web
    web_parser = subparsers.add_parser(
        "web",
        help="Analyze a website and generate a multi-section interactive SPA report",
        description="Analyze webpage security, SEO, performance, accessibility, and tech stack.",
    )
    web_parser.add_argument(
        "url",
        help="Target webpage URL to analyze (e.g. https://example.com)",
    )
    web_parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Directory or file path where report should be saved (default: .)",
    )
    web_parser.add_argument(
        "-o", "--open",
        action="store_true",
        dest="open_browser",
        help="Automatically open the generated report in default web browser",
    )
    web_parser.add_argument(
        "-f", "--filename",
        default="web_report.html",
        help="Filename or directory for the report (default: web_report.html)",
    )
    web_parser.add_argument(
        "--light",
        action="store_true",
        dest="light_mode",
        help="Generate report in light mode (default is dark mode)",
    )
    web_parser.add_argument(
        "--dark",
        action="store_true",
        dest="dark_mode",
        default=True,
        help="Generate report in dark mode (default)",
    )
    web_parser.add_argument(
        "--delay",
        type=int,
        default=0,
        help="Delay in seconds before scanning (default: 0)",
    )

    return parser


def handle_sys_command(args: argparse.Namespace) -> int:
    """Execute the `reportz sys` command."""
    target_path_arg = args.path
    filename = args.filename
    open_browser = args.open_browser
    dark_mode = False if getattr(args, "light_mode", False) else True

    mode_label = "light" if not dark_mode else "dark"
    print(f"⚡ [reportz] Collecting system telemetry ({mode_label} mode)...")
    try:
        report = SystemReport(dark_mode=dark_mode)
        saved_file = report.save(
            filename=filename,
            save_file_path=target_path_arg,
            open_browser=open_browser,
            dark_mode=dark_mode,
        )
    except Exception as exc:
        print(f"❌ [reportz] Error generating system report: {exc}", file=sys.stderr)
        return 1

    print(f"✅ [reportz] System report successfully saved:")
    print(f"   -> {saved_file}")
    if open_browser:
        print("🌐 [reportz] Report opened in default browser.")

    return 0


def handle_web_command(args: argparse.Namespace) -> int:
    """Execute the `reportz web` command."""
    url = args.url
    target_path_arg = args.path
    filename = args.filename
    open_browser = args.open_browser
    dark_mode = False if getattr(args, "light_mode", False) else True
    delay = getattr(args, "delay", 0)

    mode_label = "light" if not dark_mode else "dark"
    print(f"🔍 [reportz] Analyzing webpage '{url}' ({mode_label} mode)...")
    try:
        report = WebReport(dark_mode=dark_mode, delay=delay)
        saved_file = report.save(
            filename=filename,
            url=url,
            save_file_path=target_path_arg,
            open_browser=open_browser,
            dark_mode=dark_mode,
            delay=delay,
        )
        summary = report.summary()
    except Exception as exc:
        print(f"❌ [reportz] Error generating web report: {exc}", file=sys.stderr)
        return 1

    print(f"✅ [reportz] Web analysis report successfully saved:")
    print(f"   -> {saved_file}")
    print(f"📊 [reportz] Overall Score: {summary['overall_score']}/100 ({summary['risk_level']} risk)")
    print(f"⚠️  [reportz] Total Findings: {summary['issues_total']} issue(s)")
    if open_browser:
        print("🌐 [reportz] Report opened in default browser.")

    return 0


def main(argv: Optional[List[str]] = None) -> int:
    """Main CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.subcommand:
        parser.print_help()
        return 0

    if args.subcommand == "sys":
        return handle_sys_command(args)

    if args.subcommand == "web":
        return handle_web_command(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())

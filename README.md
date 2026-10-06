# reportz

A modern Python diagnostic and reporting toolkit with interactive HTML exports.

## Installation

```bash
pip install -e .
```

## Features

- **System Diagnostics (`SysInfo` / `SystemReport`)**: Collect comprehensive hardware, CPU per-core usage, RAM, disk partitions, battery, network, and uptime metrics.
- **Interactive HTML Reports**: Standalone, modern glassmorphism dashboards with dark/light themes, telemetry graphs, and JSON export.
- **CLI & Code API**: Use directly from terminal or import into Python scripts.

## Usage

### 1. From Python Code

#### System Report
```python
from reportz import SystemReport

# Initialize and collect system telemetry
sys = SystemReport()

# Save interactive HTML report (Dark mode is True by default)
sys.save(filename="system_report.html", save_file_path=".")

# Generate in Light Mode:
sys.save("system_report.html", ".", dark_mode=False)

# Optional: open automatically in the default browser
sys.save("system_report.html", ".", open_browser=True)
```

You can also access the underlying collector directly:

```python
from reportz import SysInfo

info = SysInfo()
print(info.all())     # full telemetry dictionary
print(info.cpu())     # CPU usage & frequency
print(info.memory())  # RAM metrics
print(info.disk())    # Disk partitions
print(info.battery()) # Battery state
print(info.network()) # Hostname & IP
print(info.uptime())  # Boot time & uptime
```

#### Web Analyzer Report
```python
from reportz import WebReport

web = WebReport()
# Save report: save(filename, url, darkmode)
web.save("web_report.html", "https://example.com", dark_mode=True)

# Or initialize with URL and save:
web = WebReport("https://example.com")
web.save("my_report.html", dark_mode=False, open_browser=True)

# Access scan data and summary metrics
print(web.summary())
print(web.all())
```

### 2. From Command Line (CLI)

#### System Diagnostic Report
```bash
# Generate report in dark mode (default)
reportz sys -o .

# Generate report in light mode
reportz sys --light -o .

# Flags and path are optional:
reportz sys -o
reportz sys
reportz sys --light
```

#### Web Analyzer Report
```bash
# Analyze a website and output report in current directory
reportz web https://example.com . -o

# Light mode report
reportz web https://example.com . -o --light

# Custom filename or delay
reportz web https://example.com -f my_site.html --delay 2
```

## Running Tests

```bash
pytest
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

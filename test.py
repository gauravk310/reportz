from reportz import SystemReport

sys = SystemReport()

# Save report (filename and save_file_path)
sys.save("system_report.html", ".")

# Optional: open automatically in browser
sys.save("system_report.html", ".", open_browser=True)

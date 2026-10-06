from setuptools import find_packages, setup

setup(
    name="reportz",
    version="0.1.0",
    description="A modern Python diagnostic and reporting toolkit",
    author="Gaurav Kadam",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[
        "psutil>=5.9.0",
    ],
    entry_points={
        "console_scripts": [
            "reportz = reportz.cli:main",
        ],
    },
    python_requires=">=3.9",
)

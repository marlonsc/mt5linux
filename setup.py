"""MetaTrader5 for Linux users.

DEPRECATED: This file exists for backwards compatibility with pip install.
Use Poetry (pyproject.toml) as the primary package manager.

Author: Lucas Prett Campagna
License: MIT
URL: https://github.com/lucas-campagna/mt5linux
"""

from pathlib import Path

from setuptools import find_packages, setup

setup(
    name="mt5linux",
    packages=find_packages(include=["mt5linux"]),
    version="0.3.0",
    description="MetaTrader5 bridge for Linux via rpyc",
    long_description=Path("README.md").read_text(encoding="utf-8"),
    long_description_content_type="text/markdown",
    author="Lucas Prett Campagna",
    license="MIT",
    url="https://github.com/lucas-campagna/mt5linux",
    python_requires=">=3.12",
    install_requires=[
        "numpy>=1.26.4,<2.0",
        "rpyc>=6.0.2",
        "pydantic>=2.10.0",
        "structlog>=25.5.0",
    ],
    setup_requires=[],
    tests_require=[],
    test_suite="tests",
)

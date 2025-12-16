"""
MetaTrader5 for linux users
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
    description="MetaTrader5 for linux users",
    long_description=Path("README.md").read_text(encoding="utf-8"),
    long_description_content_type="text/markdown",
    author="Lucas Prett Campagna",
    license="MIT",
    url="https://github.com/lucas-campagna/mt5linux",
    install_requires=Path("requirements.txt").read_text(encoding="utf-8").split("\n"),
    setup_requires=[],
    tests_require=[],
    test_suite="tests",
)

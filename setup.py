"""
Setup script for the MT5Linux package.

This module provides the necessary configuration for installing the MT5Linux package.
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="mt5linux",
    version="0.1.0",
    author="Lucas Campagna",
    author_email="lucas.campagna@gmail.com",
    description="MetaTrader 5 for Linux using Wine and RPyC",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/lucas-campagna/mt5linux",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Financial and Insurance Industry",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Topic :: Office/Business :: Financial :: Investment",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.6",
    install_requires=[
        "rpyc>=5.0.1",
        "numpy>=1.19.0",
        "pandas>=1.0.0",
    ],
    entry_points={
        "console_scripts": [
            "mt5linux=mt5linux.__main__:main",
        ],
    },
)
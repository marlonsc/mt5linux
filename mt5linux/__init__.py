# flake8: noqa: E501
# fmt: off
# pylance: disable=reportLineTooLong
# pylint: disable=line-too-long
# noqa: E501
"""
MetaTrader5 Linux Integration Package

This module provides the main interface and constants for MetaTrader5 integration on Linux via RPyC and Wine.
It enables using the MetaTrader5 Python API on Linux systems by creating a bridge to a Windows
installation running under Wine.
"""

from .constants_mt5 import *
from .metatrader5 import MetaTrader5, mt5

__version__ = "1.0.0"
__author__ = "MT5Linux Contributors"
__all__ = ["MetaTrader5", "mt5"]

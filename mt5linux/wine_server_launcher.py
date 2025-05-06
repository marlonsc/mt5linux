"""
Wine Server Launcher Module.

Utilities for launching the MetaTrader5 RPyC server under Wine.

Note: For absolute imports to work correctly, execute with:
    PYTHONPATH=/path/to/mt5linux python -m mt5linux
"""

import os
from subprocess import Popen
from typing import List

from rpyc.utils.classic import DEFAULT_SERVER_PORT

from mt5linux.server_generator import generate_rpyc_server_script


def launch_wine_rpyc_server(
    win_python_path: str,
    host: str = "localhost",
    port: int = DEFAULT_SERVER_PORT,
    wine_cmd: str = "wine",
    server_dir: str = "/tmp/mt5linux",
) -> None:
    """
    Launch the MetaTrader5 RPyC server under Wine.
    
    This function generates an RPyC server script and launches it using Wine with the
    specified Windows Python executable. The server enables remote procedure calls to
    the MetaTrader5 API running on Windows from Linux.

    Args:
        win_python_path: Path to the Windows Python executable.
        host: Host address for the server to bind to.
        port: TCP port for the server to listen on.
        wine_cmd: Wine command to use.
        server_dir: Directory for building and running the server.
        
    Returns:
        None
        
    Example:
        >>> launch_wine_rpyc_server(
        ...     win_python_path="C:\\Python39\\python.exe",
        ...     host="0.0.0.0",
        ...     port=18812
        ... )
    """
    server_code = "server.py"
    Popen(["mkdir", "-p", server_dir], shell=True).wait()
    generate_rpyc_server_script(os.path.join(server_dir, server_code))
    cmd: List[str] = [
        wine_cmd,
        os.path.join(win_python_path),
        os.path.join(server_dir, server_code),
        "--host",
        host,
        "-p",
        str(port),
    ]
    Popen(cmd, shell=True).wait()

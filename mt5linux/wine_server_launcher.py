"""
wine_server_launcher.py - Wine RPyC Server Launcher for MetaTrader5

Utility to launch the MetaTrader5 RPyC server under Wine. For absolute imports to work, run with:
    PYTHONPATH=external/mt5linux python -m mt5linux
"""

import os
from subprocess import Popen

try:
    from rpyc.utils.classic import DEFAULT_SERVER_PORT
except ImportError:
    from rpyc import DEFAULT_SERVER_PORT

from mt5linux.server_generator import generate_rpyc_server_script


def launch_wine_rpyc_server(
    win_python_path: str,
    host: str = "localhost",
    port: int = DEFAULT_SERVER_PORT,
    wine_cmd: str = "wine",
    server_dir: str = "/tmp/mt5linux",
) -> None:
    """Lança o servidor RPyC do MetaTrader5 sob Wine.

    :param win_python_path: Caminho para o executável Python do Windows.
    :type win_python_path: str
    :param host: Host para o servidor. (Default value = "localhost")
    :type host: str
    :param port: Porta para o servidor. (Default value = DEFAULT_SERVER_PORT)
    :type port: int
    :param wine_cmd: Comando do Wine. (Default value = "wine")
    :type wine_cmd: str
    :param server_dir: Diretório para build e execução do servidor. (Default value = "/tmp/mt5linux")
    :type server_dir: str
    :rtype: None

    """
    server_code = "server.py"
    Popen(["mkdir", "-p", server_dir], shell=True).wait()
    generate_rpyc_server_script(os.path.join(server_dir, server_code))
    cmd: list[str] = [
        wine_cmd,
        os.path.join(win_python_path),
        os.path.join(server_dir, server_code),
        "--host",
        host,
        "-p",
        str(port),
    ]
    Popen(cmd, shell=True).wait()

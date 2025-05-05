"""
wine_server_launcher.py

Utilitários para lançar o servidor RPyC do MetaTrader5 sob Wine.

by <marlonsc@gmail.com>

Nota: Para que os imports absolutos funcionem, execute com:
    PYTHONPATH=external/mt5linux python -m mt5linux
"""

import os
from subprocess import Popen

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
    Lança o servidor RPyC do MetaTrader5 sob Wine.

    Args:
        win_python_path: Caminho para o executável Python do Windows.
        host: Host para o servidor.
        port: Porta para o servidor.
        wine_cmd: Comando do Wine.
        server_dir: Diretório para build e execução do servidor.
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

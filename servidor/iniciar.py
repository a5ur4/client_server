"""Inicia os dois Servidores (REST e gRPC) no mesmo processo.

Uso:
    python iniciar.py --server-team S02
    python iniciar.py --server-team S02 --rest-port 8080 --grpc-port 50051
"""
import argparse
import socket

import uvicorn
from config import CFG


def _ip_da_rede() -> str:
    """IP desta máquina na rede local, para informar às equipes Cliente."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sonda:
            sonda.connect(("10.255.255.255", 1))  # UDP: nenhum pacote é enviado
            return sonda.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def main() -> None:
    parser = argparse.ArgumentParser(description="Servidores ConectaShop: REST (FastAPI) e gRPC.")
    parser.add_argument("--server-team", default=CFG.server_team, help="código da equipe (env SERVER_TEAM)")
    parser.add_argument("--host", default=CFG.host, help="interface de escuta (env SERVER_HOST)")
    parser.add_argument("--rest-port", type=int, default=CFG.rest_port, help="porta REST (env REST_PORT)")
    parser.add_argument("--grpc-port", type=int, default=CFG.grpc_port, help="porta gRPC (env GRPC_PORT)")
    args = parser.parse_args()
    CFG.server_team, CFG.host = args.server_team.strip(), args.host
    CFG.rest_port, CFG.grpc_port = args.rest_port, args.grpc_port

    # Importados depois de aplicar a configuração da linha de comando.
    from servidor_grpc import criar_servidor
    from servidor_rest import BASE_PATH, app

    servidor_grpc = criar_servidor()
    ip = _ip_da_rede()
    print(f"Equipe Servidor : {CFG.server_team}")
    print(f"REST            : http://{ip}:{CFG.rest_port}   (base path {BASE_PATH}, docs em /docs)")
    print(f"gRPC            : {ip}:{CFG.grpc_port}")
    print(f"Log             : {CFG.log_file}")
    print("Ctrl+C para encerrar.\n", flush=True)
    try:
        uvicorn.run(app, host=CFG.host, port=CFG.rest_port, access_log=False, log_level="warning")
    finally:
        servidor_grpc.stop(grace=1)


if __name__ == "__main__":
    main()

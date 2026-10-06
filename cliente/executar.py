"""Executa todas as baterias configuradas: R1–R5 em cada Servidor REST e G1–G5 em cada Servidor gRPC.

Uso:
    python executar.py                          (lê os Servidores do arquivo .env)
    python executar.py --rest-base-url http://10.0.0.23:8080 --grpc-target 10.0.0.24:50051

Só roda o protocolo cujo endereço foi informado; se nenhum for informado, encerra com erro.
"""
import sys

from cliente_grpc import executar_bateria_grpc
from cliente_rest import executar_bateria_rest
from config import carregar_config
from registro import Registro, exibir_matriz


def main() -> int:
    cfg = carregar_config("Cliente ConectaShop: testes REST (R1-R5) e gRPC (G1-G5).")
    if not cfg.alvos_rest and not cfg.alvos_grpc:
        print("Informe REST_BASE_URL e/ou GRPC_TARGET no .env, no ambiente ou nos argumentos.", file=sys.stderr)
        return 2

    registro = Registro(cfg.client_team, cfg.log_file)
    baterias = [executar_bateria_rest(cfg, alvo, registro) for alvo in cfg.alvos_rest]
    baterias += [executar_bateria_grpc(cfg, alvo, registro) for alvo in cfg.alvos_grpc]
    exibir_matriz(cfg.client_team, baterias, cfg.log_file)
    return 0 if all(b.aprovada for b in baterias) else 1


if __name__ == "__main__":
    sys.exit(main())

"""Consulta o registro de chamadas do Servidor (tabela request_log do SQLite).

Serve para entregar à equipe Cliente as linhas correlacionadas pelo Request ID.

Uso:
    python consultar_logs.py --request-id C01-R3-1a2b3c4d5e6f
    python consultar_logs.py --client C01 --ultimos 20
"""
import argparse

import banco


def main() -> None:
    parser = argparse.ArgumentParser(description="Consulta o log de chamadas do Servidor.")
    parser.add_argument("--request-id", default="", help="filtra por Request ID")
    parser.add_argument("--client", default="", help="filtra por equipe Cliente, ex.: C01")
    parser.add_argument("--ultimos", type=int, default=50, help="quantidade máxima de linhas (padrão 50)")
    args = parser.parse_args()

    linhas = banco.consultar_chamadas(args.request_id, args.client, args.ultimos)
    print("\n".join(linhas) if linhas else "Nenhuma chamada encontrada.")


if __name__ == "__main__":
    main()

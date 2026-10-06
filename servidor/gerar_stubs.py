"""Gera os stubs gRPC (shipping_pb2.py e shipping_pb2_grpc.py) a partir de proto/shipping.proto.

Uso:  python gerar_stubs.py
"""
import sys
from pathlib import Path

from grpc_tools import protoc

RAIZ = Path(__file__).resolve().parent


def main() -> int:
    codigo = protoc.main([
        "grpc_tools.protoc",
        f"-I{RAIZ / 'proto'}",
        f"--python_out={RAIZ}",
        f"--grpc_python_out={RAIZ}",
        str(RAIZ / "proto" / "shipping.proto"),
    ])
    if codigo == 0:
        print("Stubs gerados: shipping_pb2.py e shipping_pb2_grpc.py")
    else:
        print("Falha ao gerar os stubs.", file=sys.stderr)
    return codigo


if __name__ == "__main__":
    sys.exit(main())

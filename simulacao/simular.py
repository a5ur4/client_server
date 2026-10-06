"""Simulação local da dinâmica IntegraLab.

Sobe dois Servidores independentes (equipes S01 e S02, cada um com REST e gRPC),
roda a autoverificação de contrato em cada um e depois executa o Cliente C01
contra os quatro serviços, como no dia do sorteio. Os logs ficam em simulacao/logs.

Uso (na raiz do projeto):
    .venv\\Scripts\\python.exe simulacao\\simular.py
    .venv\\Scripts\\python.exe simulacao\\simular.py --com-falha   (inclui um Servidor fora do ar)
"""
import argparse
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
LOGS = RAIZ / "simulacao" / "logs"
HOST = "127.0.0.1"
SERVIDORES = [
    {"equipe": "S01", "rest": 8081, "grpc": 50061},
    {"equipe": "S02", "rest": 8082, "grpc": 50062},
]
# Porta sem nenhum serviço, para simular um Servidor fora do ar.
PORTA_FORA_DO_AR = {"equipe": "S99", "rest": 8089, "grpc": 50069}


def ambiente(**variaveis: str) -> dict[str, str]:
    """Ambiente do processo filho: ignora os .env reais e usa só o que a simulação define."""
    return {**os.environ, "ENV_FILE": str(RAIZ / "simulacao" / "sem.env"), "PYTHONUNBUFFERED": "1", **variaveis}


def aguardar_porta(porta: int, limite_s: float = 15) -> None:
    fim = time.monotonic() + limite_s
    while time.monotonic() < fim:
        with socket.socket() as sonda:
            sonda.settimeout(0.5)
            if sonda.connect_ex((HOST, porta)) == 0:
                return
        time.sleep(0.2)
    raise RuntimeError(f"porta {porta} não abriu em {limite_s}s (já está em uso por outro programa?)")


def encerrar(processo: subprocess.Popen) -> None:
    """Encerra o Servidor. No Windows o python.exe do venv cria um processo filho, daí o /T."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(processo.pid), "/T", "/F"], capture_output=True)
    else:
        processo.terminate()
    processo.wait(timeout=10)


def titulo(texto: str) -> None:
    print(f"\n{'=' * 78}\n{texto}\n{'=' * 78}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Simulação local da dinâmica IntegraLab.")
    parser.add_argument("--com-falha", action="store_true", help="inclui um Servidor fora do ar no sorteio")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding=None if sys.stdout.isatty() else "utf-8", errors="replace")

    LOGS.mkdir(parents=True, exist_ok=True)
    for antigo in LOGS.glob("*"):
        antigo.unlink()

    processos = []
    codigo = 0
    try:
        titulo("1. Subindo os Servidores")
        for s in SERVIDORES:
            processos.append(subprocess.Popen(
                [sys.executable, "iniciar.py"], cwd=RAIZ / "servidor", stdout=subprocess.DEVNULL,
                env=ambiente(SERVER_TEAM=s["equipe"], SERVER_HOST=HOST, REST_PORT=str(s["rest"]),
                             GRPC_PORT=str(s["grpc"]),
                             SERVER_LOG_FILE=str(LOGS / f"servidor_{s['equipe']}.log"),
                             SERVER_DB_FILE=str(LOGS / f"servidor_{s['equipe']}.db"))))
        for s in SERVIDORES:
            aguardar_porta(s["rest"])
            aguardar_porta(s["grpc"])
            print(f"  {s['equipe']}: REST=UP http://{HOST}:{s['rest']}   gRPC=UP {HOST}:{s['grpc']}")

        titulo("2. Autoverificação de contrato de cada Servidor (verificar_contrato.py)")
        for s in SERVIDORES:
            saida = subprocess.run(
                [sys.executable, "verificar_contrato.py", "--rest-base-url", f"http://{HOST}:{s['rest']}",
                 "--grpc-target", f"{HOST}:{s['grpc']}"],
                cwd=RAIZ / "servidor", env=ambiente(), capture_output=True, text=True, encoding="utf-8")
            aprovados = len(re.findall(r"^\s+PASS", saida.stdout, re.MULTILINE))
            reprovados = len(re.findall(r"^\s+FAIL", saida.stdout, re.MULTILINE))
            print(f"  {s['equipe']}: {aprovados} verificações PASS, {reprovados} FAIL")
            if saida.returncode != 0:
                codigo = 1
                print(saida.stdout + saida.stderr)

        titulo("3. Cliente C01 contra os Servidores sorteados (executar.py)")
        sorteados = SERVIDORES + ([PORTA_FORA_DO_AR] if args.com_falha else [])
        equipes = ",".join(s["equipe"] for s in sorteados)
        log_cliente = LOGS / "cliente_C01.log"
        resultado = subprocess.run(
            [sys.executable, "executar.py"], cwd=RAIZ / "cliente",
            env=ambiente(CLIENT_TEAM="C01", CLIENT_TIMEOUT="2", CLIENT_LOG_FILE=str(log_cliente),
                         REST_BASE_URL=",".join(f"http://{HOST}:{s['rest']}" for s in sorteados),
                         REST_SERVER_TEAM=equipes,
                         GRPC_TARGET=",".join(f"{HOST}:{s['grpc']}" for s in sorteados),
                         GRPC_SERVER_TEAM=equipes))
        if resultado.returncode != 0 and not args.com_falha:
            codigo = 1

        titulo("4. Correlação pelo Request ID (teste R3 e teste G2 contra S01)")
        linhas_cliente = log_cliente.read_text(encoding="utf-8").splitlines()
        linhas_servidor = (LOGS / "servidor_S01.log").read_text(encoding="utf-8").splitlines()
        for teste in ("R3", "G2"):
            do_cliente = next(l for l in linhas_cliente if f"test={teste} " in l and "server=S01 " in l)
            request_id = re.search(r"requestId=(\S+)", do_cliente).group(1)
            do_servidor = next((l for l in linhas_servidor if f"requestId={request_id} " in l), "(não encontrado)")
            print(f"  Cliente : {do_cliente}\n  Servidor: {do_servidor}\n")
    finally:
        for processo in processos:
            encerrar(processo)

    titulo("Simulação concluída" if codigo == 0 else "Simulação concluída COM FALHAS")
    print(f"Logs em: {LOGS}")
    return codigo


if __name__ == "__main__":
    sys.exit(main())

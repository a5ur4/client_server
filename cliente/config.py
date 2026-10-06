"""Configuração do Cliente.

Nenhum endereço fica fixo no código. Cada valor é procurado nesta ordem:
argumento de linha de comando, variável de ambiente, arquivo .env, valor padrão.

    --rest-base-url     REST_BASE_URL     ex.: http://10.0.0.23:8080
    --grpc-target       GRPC_TARGET       ex.: 10.0.0.24:50051
    --client-team       CLIENT_TEAM       código da nossa equipe, ex.: C01
    --rest-server-team  REST_SERVER_TEAM  equipe do Servidor REST, ex.: S03
    --grpc-server-team  GRPC_SERVER_TEAM  equipe do Servidor gRPC, ex.: S04
    --timeout           CLIENT_TIMEOUT    segundos por chamada
    --log-file          CLIENT_LOG_FILE   arquivo onde as tentativas são gravadas
    --env-file          ENV_FILE          arquivo de configuração (padrão: .env desta pasta)

REST_BASE_URL e GRPC_TARGET aceitam mais de um Servidor, separados por vírgula;
os códigos de equipe seguem a mesma ordem. Assim os dois Servidores REST e os
dois Servidores gRPC sorteados cabem em um único .env.
"""
import argparse
import os
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
BASE_PATH = "/api/v1"


@dataclass(frozen=True)
class Alvo:
    """Um Servidor a ser testado: REST_BASE_URL ou GRPC_TARGET e o código da equipe parceira."""
    endereco: str
    server_team: str


@dataclass(frozen=True)
class Config:
    client_team: str
    alvos_rest: list[Alvo]
    alvos_grpc: list[Alvo]
    timeout: float
    log_file: Path


def url_api(rest_base_url: str) -> str:
    """URL base já com /api/v1, aceitando REST_BASE_URL com ou sem o base path."""
    base = rest_base_url.rstrip("/")
    if "://" not in base:
        base = "http://" + base
    return base if base.endswith(BASE_PATH) else base + BASE_PATH


def carregar_env(arquivo: Path) -> None:
    """Lê linhas CHAVE=valor do .env sem sobrescrever o que já está no ambiente."""
    if not arquivo.is_file():
        return
    for linha in arquivo.read_text(encoding="utf-8-sig").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        os.environ.setdefault(chave.strip(), valor.strip().strip('"').strip("'"))


def _lista(texto: str) -> list[str]:
    return [parte.strip() for parte in texto.split(",") if parte.strip()]


def _alvos(enderecos: str, equipes: str) -> list[Alvo]:
    codigos = _lista(equipes)
    return [Alvo(endereco, codigos[i] if i < len(codigos) else "")
            for i, endereco in enumerate(_lista(enderecos))]


def carregar_config(descricao: str) -> Config:
    """Monta a configuração a partir dos argumentos, do ambiente e do arquivo .env."""
    base = argparse.ArgumentParser(add_help=False)
    base.add_argument("--env-file", default=os.getenv("ENV_FILE", str(RAIZ / ".env")),
                      help="arquivo de configuração (env ENV_FILE, padrão .env desta pasta)")
    carregar_env(Path(base.parse_known_args()[0].env_file))

    parser = argparse.ArgumentParser(description=descricao, parents=[base])
    parser.add_argument("--rest-base-url", default=os.getenv("REST_BASE_URL", ""),
                        help="URL base do(s) Servidor(es) REST, separados por vírgula (env REST_BASE_URL)")
    parser.add_argument("--grpc-target", default=os.getenv("GRPC_TARGET", ""),
                        help="host:porta do(s) Servidor(es) gRPC, separados por vírgula (env GRPC_TARGET)")
    parser.add_argument("--client-team", default=os.getenv("CLIENT_TEAM", "C01"),
                        help="código da equipe Cliente (env CLIENT_TEAM, padrão C01)")
    parser.add_argument("--rest-server-team", default=os.getenv("REST_SERVER_TEAM", ""),
                        help="equipe de cada Servidor REST, na mesma ordem (env REST_SERVER_TEAM)")
    parser.add_argument("--grpc-server-team", default=os.getenv("GRPC_SERVER_TEAM", ""),
                        help="equipe de cada Servidor gRPC, na mesma ordem (env GRPC_SERVER_TEAM)")
    parser.add_argument("--timeout", type=float, default=float(os.getenv("CLIENT_TIMEOUT", "5")),
                        help="timeout por chamada, em segundos (env CLIENT_TIMEOUT, padrão 5)")
    parser.add_argument("--log-file", default=os.getenv("CLIENT_LOG_FILE", "logs/integracao_cliente.log"),
                        help="arquivo de log das integrações (env CLIENT_LOG_FILE)")
    args = parser.parse_args()

    log_file = Path(args.log_file)
    return Config(
        client_team=args.client_team.strip(),
        alvos_rest=_alvos(args.rest_base_url, args.rest_server_team),
        alvos_grpc=_alvos(args.grpc_target, args.grpc_server_team),
        timeout=args.timeout,
        # Caminho relativo é resolvido a partir da pasta do Cliente, não do diretório atual.
        log_file=log_file if log_file.is_absolute() else RAIZ / log_file,
    )

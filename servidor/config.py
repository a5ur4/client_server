"""Configuração do Servidor.

Cada valor é procurado nesta ordem: argumento de `iniciar.py`, variável de
ambiente, arquivo .env desta pasta, valor padrão.

    SERVER_TEAM      código da nossa equipe (padrão S01)
    SERVER_HOST      interface de escuta (padrão 0.0.0.0, acessível pela rede)
    REST_PORT        porta da API REST (padrão 8080)
    GRPC_PORT        porta do ShippingService (padrão 50051)
    SERVER_LOG_FILE  arquivo de log das chamadas recebidas
    SERVER_DB_FILE   arquivo SQLite com o registro das chamadas
    ENV_FILE         arquivo de configuração alternativo (padrão: .env desta pasta)
"""
import os
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parent


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


def _caminho(variavel: str, padrao: str) -> Path:
    """Caminho relativo é resolvido a partir da pasta do Servidor, não do diretório atual."""
    caminho = Path(os.getenv(variavel, padrao))
    return caminho if caminho.is_absolute() else RAIZ / caminho


@dataclass
class Config:
    server_team: str
    host: str
    rest_port: int
    grpc_port: int
    db_file: Path
    log_file: Path


carregar_env(Path(os.getenv("ENV_FILE", str(RAIZ / ".env"))))

CFG = Config(
    server_team=os.getenv("SERVER_TEAM", "S01").strip(),
    host=os.getenv("SERVER_HOST", "0.0.0.0").strip(),
    rest_port=int(os.getenv("REST_PORT", "8080")),
    grpc_port=int(os.getenv("GRPC_PORT", "50051")),
    db_file=_caminho("SERVER_DB_FILE", "dados/conectashop.db"),
    log_file=_caminho("SERVER_LOG_FILE", "logs/integracao_servidor.log"),
)

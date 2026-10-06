"""Registro das chamadas recebidas em SQLite (arquivo local, sem servidor de banco externo).

O banco é apenas auxiliar: guarda cada linha de log para que seja possível
recuperar, por Request ID ou equipe Cliente, os trechos pedidos no relatório.
O catálogo e as regras do contrato ficam em memória e não dependem dele.

Cada operação abre e fecha a própria conexão, o que mantém o acesso seguro tanto
para o FastAPI quanto para as threads do servidor gRPC.
"""
import sqlite3
from contextlib import closing

from config import CFG

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS request_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    moment      TEXT NOT NULL,
    protocol    TEXT NOT NULL,
    client_team TEXT NOT NULL,
    request_id  TEXT NOT NULL,
    operation   TEXT NOT NULL,
    status      TEXT NOT NULL,
    line        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_request_log_request_id ON request_log (request_id);
"""


def _conectar() -> sqlite3.Connection:
    CFG.db_file.parent.mkdir(parents=True, exist_ok=True)
    conexao = sqlite3.connect(CFG.db_file, timeout=5)
    conexao.executescript(_ESQUEMA)
    return conexao


def gravar_chamada(momento: str, protocolo: str, client_team: str, request_id: str,
                   operacao: str, status: str, linha: str) -> None:
    with closing(_conectar()) as conexao, conexao:
        conexao.execute(
            "INSERT INTO request_log (moment, protocol, client_team, request_id, operation, status, line)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (momento, protocolo, client_team, request_id, operacao, status, linha))


def consultar_chamadas(request_id: str = "", client_team: str = "", limite: int = 50) -> list[str]:
    """Linhas de log mais recentes, filtradas por Request ID e/ou equipe Cliente."""
    filtros, valores = [], []
    if request_id:
        filtros.append("request_id = ?")
        valores.append(request_id)
    if client_team:
        filtros.append("client_team = ?")
        valores.append(client_team)
    onde = f"WHERE {' AND '.join(filtros)}" if filtros else ""
    with closing(_conectar()) as conexao:
        linhas = conexao.execute(
            f"SELECT line FROM request_log {onde} ORDER BY id DESC LIMIT ?", (*valores, limite)).fetchall()
    return [linha[0] for linha in reversed(linhas)]

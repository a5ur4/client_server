"""Log das chamadas recebidas: terminal, arquivo de texto e tabela request_log do SQLite.

Formato (guia do grupo Servidor):
[horário] protocol=REST server=S03 client=C01 requestId=req-101 operation=GET_PRODUCT input=KB-100 status=200 result=OK
"""
import sys
import threading
from datetime import datetime

import banco
from config import CFG

_trava = threading.Lock()

if hasattr(sys.stdout, "reconfigure"):
    # Saída redirecionada para arquivo vai em UTF-8; no terminal, nunca falha por acentuação.
    sys.stdout.reconfigure(encoding=None if sys.stdout.isatty() else "utf-8", errors="replace")


def _valor(valor: object) -> str:
    texto = str(valor).replace("\r", " ").replace("\n", " ")
    if texto == "" or any(c in texto for c in ' "='):
        return '"' + texto.replace('"', "'") + '"'
    return texto


def registrar(protocolo: str, client_team: str, request_id: str, operacao: str,
              parametros: dict[str, object], status: str, **resultado: object) -> None:
    """Grava uma linha por chamada, correlacionável com o Cliente pelo requestId.

    `parametros` são os dados principais da entrada; `resultado` são os campos
    exibidos depois do status (result, code, priceCents, durationMs...).
    """
    momento = datetime.now().isoformat(timespec="seconds")
    campos: dict[str, object] = {
        "protocol": protocolo,
        "server": CFG.server_team,
        "client": client_team or "?",
        "requestId": request_id or "-",
        "operation": operacao,
        **parametros,
        "status": status,
        **resultado,
    }
    linha = f"[{momento}] " + " ".join(f"{k}={_valor(v)}" for k, v in campos.items())
    # O registro nunca pode derrubar o atendimento da chamada.
    try:
        with _trava:
            print(linha, flush=True)
            CFG.log_file.parent.mkdir(parents=True, exist_ok=True)
            with CFG.log_file.open("a", encoding="utf-8") as arquivo:
                arquivo.write(linha + "\n")
        banco.gravar_chamada(momento, protocolo, client_team or "?", request_id or "-", operacao, status, linha)
    except Exception as erro:
        print(f"[registro] falha ao gravar log: {erro}", file=sys.stderr)

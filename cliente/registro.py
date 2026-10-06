"""Registro das tentativas de integração: saída no terminal e arquivo de log."""
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# Etapas em que uma falha pode ocorrer (roteiro do grupo Cliente, passo 19).
CONEXAO = "conexao"
REQUEST = "request"
SERIALIZACAO = "serializacao"
CONTRATO = "contrato"
REGRA_NEGOCIO = "regra_negocio"
INTERPRETACAO = "interpretacao"


@dataclass
class Resultado:
    teste: str
    protocolo: str
    operacao: str
    destino: str
    request_id: str
    requisicao: str
    esperado: str
    status: str = "-"
    resposta: str = "-"
    duracao_ms: int = 0
    passou: bool = False
    etapa_falha: str = ""
    detalhe: str = ""
    observacoes: list[str] = field(default_factory=list)
    extras: dict[str, object] = field(default_factory=dict)

    def falhar(self, etapa: str, detalhe: str) -> None:
        """Marca a falha; a primeira etapa registrada é a que prevalece."""
        self.passou = False
        if not self.etapa_falha:
            self.etapa_falha = etapa
            self.detalhe = detalhe


def novo_request_id(client_team: str, teste: str) -> str:
    """Identificador único por chamada, legível para correlacionar com o log do Servidor."""
    return f"{client_team}-{teste}-{uuid.uuid4().hex[:12]}"


def _valor(valor: object) -> str:
    texto = str(valor).replace("\r", " ").replace("\n", " ")
    if texto == "" or any(c in texto for c in ' "='):
        return '"' + texto.replace('"', "'") + '"'
    return texto


class Registro:
    def __init__(self, client_team: str, log_file: Path):
        self.client_team = client_team
        self.log_file = log_file
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        if hasattr(sys.stdout, "reconfigure"):
            # Saída redirecionada para arquivo vai em UTF-8; no terminal, nunca falha por acentuação.
            sys.stdout.reconfigure(encoding=None if sys.stdout.isatty() else "utf-8", errors="replace")

    def registrar(self, r: Resultado, server_team: str) -> None:
        self._exibir(r, server_team)
        campos: dict[str, object] = {
            "protocol": r.protocolo,
            "client": self.client_team,
            "server": server_team or "?",
            "requestId": r.request_id,
            "test": r.teste,
            "operation": r.operacao,
            "target": r.destino,
            "status": r.status,
            "durationMs": r.duracao_ms,
        }
        campos.update(r.extras)
        campos["result"] = "PASS" if r.passou else "FAIL"
        if not r.passou:
            campos["failStage"] = r.etapa_falha
            campos["detail"] = r.detalhe
        if r.observacoes:
            campos["obs"] = "; ".join(r.observacoes)
        momento = datetime.now().isoformat(timespec="seconds")
        linha = f"[{momento}] " + " ".join(f"{k}={_valor(v)}" for k, v in campos.items())
        with self.log_file.open("a", encoding="utf-8") as arquivo:
            arquivo.write(linha + "\n")

    def _exibir(self, r: Resultado, server_team: str) -> None:
        print(f"[{r.teste}] {r.protocolo} {r.operacao} -> {r.destino} (servidor {server_team or '?'})")
        print(f"    request   : {r.requisicao}")
        print(f"    requestId : {r.request_id}")
        print(f"    esperado  : {r.esperado}")
        print(f"    status    : {r.status}")
        print(f"    resposta  : {r.resposta}")
        print(f"    duracao   : {r.duracao_ms} ms")
        for obs in r.observacoes:
            print(f"    obs       : {obs}")
        if r.passou:
            print("    resultado : PASS")
        else:
            print(f"    resultado : FAIL  [etapa: {r.etapa_falha}] {r.detalhe}")
        print()


@dataclass
class Bateria:
    """Resultado dos cinco testes de um protocolo contra um Servidor."""
    protocolo: str
    destino: str
    server_team: str
    resultados: list[Resultado]

    @property
    def aprovada(self) -> bool:
        return all(r.passou for r in self.resultados)


def exibir_matriz(client_team: str, baterias: list[Bateria], log_file: Path) -> None:
    """Resumo final no formato da matriz de execução do relatório."""
    linhas = []
    for b in baterias:
        aprovados = sum(1 for r in b.resultados if r.passou)
        falhas = ", ".join(f"{r.teste}({r.etapa_falha})" for r in b.resultados if not r.passou) or "-"
        testes = f"{b.resultados[0].teste}-{b.resultados[-1].teste}"
        situacao = "PASS" if b.aprovada else "FAIL"
        linhas.append((b.protocolo, b.server_team or "?", b.destino, testes,
                       f"{aprovados}/{len(b.resultados)} {situacao}", falhas))
    cabecalho = ("Protocolo", "Servidor", "Destino", "Testes", "Resultado", "Falhas (etapa)")
    larguras = [max(len(linha[i]) for linha in [cabecalho, *linhas]) for i in range(len(cabecalho))]
    print(f"== MATRIZ DE EXECUCAO - Cliente {client_team} ==")
    for linha in [cabecalho, *linhas]:
        print("  " + "  ".join(valor.ljust(larguras[i]) for i, valor in enumerate(linha)).rstrip())
    print()
    print(f"Log gravado em: {log_file}")

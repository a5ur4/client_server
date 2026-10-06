"""Cliente REST da Catalog & Quote API — executa os testes R1–R5.

Uso:
    python cliente_rest.py                      (lê REST_BASE_URL do arquivo .env)
    python cliente_rest.py --rest-base-url http://10.0.0.23:8080 --rest-server-team S03

As requisições e a leitura das respostas seguem apenas o contrato: nenhum SDK
ou código do grupo Servidor é utilizado.
"""
import json
import sys
import time
from dataclasses import dataclass, field

import httpx
from config import Alvo, Config, carregar_config, url_api
from registro import (
    CONEXAO,
    CONTRATO,
    INTERPRETACAO,
    REGRA_NEGOCIO,
    REQUEST,
    SERIALIZACAO,
    Bateria,
    Registro,
    Resultado,
    exibir_matriz,
    novo_request_id,
)


@dataclass(frozen=True)
class TesteRest:
    id: str
    operacao: str
    metodo: str
    caminho: str
    status_esperado: int
    # Campos da tabela de testes do contrato: definem PASS/FAIL.
    exigido: dict[str, object]
    # Etapa atribuída quando o valor de um campo exigido diverge do esperado.
    etapa_valor: str
    itens: list[dict[str, object]] | None = None
    # Demais campos do contrato: divergência vira observação no log.
    complementar: dict[str, object] = field(default_factory=dict)


TESTES = [
    TesteRest("R1", "GET_PRODUCT", "GET", "/products/KB-100", 200,
              exigido={"unitPriceCents": 25990}, etapa_valor=REGRA_NEGOCIO,
              complementar={"sku": "KB-100", "name": "Teclado Mecânico", "available": True}),
    TesteRest("R2", "GET_PRODUCT", "GET", "/products/XX-999", 404,
              exigido={"code": "PRODUCT_NOT_FOUND"}, etapa_valor=CONTRATO),
    TesteRest("R3", "POST_QUOTE", "POST", "/quotes", 200,
              exigido={"subtotalCents": 64970, "discountPercent": 5, "totalCents": 61722},
              etapa_valor=REGRA_NEGOCIO,
              itens=[{"sku": "KB-100", "quantity": 2}, {"sku": "MS-200", "quantity": 1}],
              complementar={"discountCents": 3248}),
    TesteRest("R4", "POST_QUOTE", "POST", "/quotes", 200,
              exigido={"subtotalCents": 119990, "discountPercent": 10,
                       "discountCents": 11999, "totalCents": 107991},
              etapa_valor=REGRA_NEGOCIO,
              itens=[{"sku": "MN-400", "quantity": 1}]),
    TesteRest("R5", "POST_QUOTE", "POST", "/quotes", 422,
              exigido={"code": "INVALID_PRODUCT"}, etapa_valor=CONTRATO,
              itens=[{"sku": "XX-999", "quantity": 1}]),
]


def consolidar_itens(itens: list[dict[str, object]]) -> list[dict[str, object]]:
    """Soma as quantidades de SKUs repetidos: o contrato proíbe SKU duplicado no request."""
    quantidades: dict[str, int] = {}
    for item in itens:
        quantidades[item["sku"]] = quantidades.get(item["sku"], 0) + item["quantity"]
    return [{"sku": sku, "quantity": quantidade} for sku, quantidade in quantidades.items()]


def _conferir(corpo: dict, campo: str, esperado: object) -> tuple[str, str]:
    """Compara um campo da resposta. Devolve (problema, mensagem); problema vazio = confere."""
    if campo not in corpo:
        return "ausente", f"campo {campo} ausente"
    obtido = corpo[campo]
    if isinstance(esperado, bool):
        tipo_ok = isinstance(obtido, bool)
    elif isinstance(esperado, int):
        # JSON não distingue 25990 de 25990.0; texto ou booleano não são aceitos.
        tipo_ok = not isinstance(obtido, bool) and (
            isinstance(obtido, int) or (isinstance(obtido, float) and obtido.is_integer()))
    else:
        tipo_ok = isinstance(obtido, str)
    if not tipo_ok:
        return "tipo", f"campo {campo} com tipo inesperado ({obtido!r})"
    if obtido != esperado:
        return "valor", f"{campo}={obtido!r}, esperado {esperado!r}"
    return "", ""


def _validar(teste: TesteRest, resposta: httpx.Response, request_id: str, r: Resultado) -> None:
    r.passou = True
    try:
        corpo = resposta.json()
    except ValueError:
        corpo = None

    if resposta.status_code != teste.status_esperado:
        code = f" (code={corpo.get('code')})" if isinstance(corpo, dict) and "code" in corpo else ""
        r.falhar(CONTRATO, f"HTTP {resposta.status_code}{code}, esperado HTTP {teste.status_esperado}")
    elif corpo is None:
        r.falhar(SERIALIZACAO, "corpo da resposta não é um JSON válido")
    elif not isinstance(corpo, dict):
        r.falhar(CONTRATO, "corpo da resposta não é um objeto JSON")
    else:
        for campo, esperado in teste.exigido.items():
            problema, mensagem = _conferir(corpo, campo, esperado)
            if problema:
                r.falhar(teste.etapa_valor if problema == "valor" else CONTRATO, mensagem)
        complementar = dict(teste.complementar)
        if teste.operacao == "POST_QUOTE" or teste.status_esperado != 200:
            complementar["requestId"] = request_id
        for campo, esperado in complementar.items():
            problema, mensagem = _conferir(corpo, campo, esperado)
            if problema:
                r.observacoes.append(mensagem)

    if resposta.headers.get("X-Request-ID") != request_id:
        r.observacoes.append("header X-Request-ID não foi devolvido na resposta")
    if not resposta.headers.get("Content-Type", "").lower().startswith("application/json"):
        r.observacoes.append(f"Content-Type da resposta: {resposta.headers.get('Content-Type', 'ausente')}")


def executar_teste(http: httpx.Client, cfg: Config, alvo: Alvo, teste: TesteRest) -> Resultado:
    request_id = novo_request_id(cfg.client_team, teste.id)
    url = url_api(alvo.endereco) + teste.caminho
    headers = {"X-Client-Team": cfg.client_team, "X-Request-ID": request_id}
    conteudo = None
    requisicao = f"{teste.metodo} {url}"
    if teste.itens is not None:
        conteudo = json.dumps({"items": consolidar_itens(teste.itens)}, ensure_ascii=False)
        headers["Content-Type"] = "application/json"
        requisicao += f" body={conteudo}"

    esperado = f"HTTP {teste.status_esperado}; " + "; ".join(f"{k}={v}" for k, v in teste.exigido.items())
    r = Resultado(teste=teste.id, protocolo="REST", operacao=teste.operacao, destino=alvo.endereco,
                  request_id=request_id, requisicao=requisicao, esperado=esperado)

    inicio = time.perf_counter()
    try:
        resposta = http.request(teste.metodo, url, headers=headers, content=conteudo)
    except (httpx.InvalidURL, httpx.UnsupportedProtocol) as erro:
        r.falhar(REQUEST, f"endereço inválido: {erro}")
        return r
    except httpx.TimeoutException as erro:
        r.status = "TIMEOUT"
        r.falhar(CONEXAO, f"tempo esgotado após {cfg.timeout}s ({type(erro).__name__})")
        return r
    except httpx.TransportError as erro:
        r.status = "SEM_CONEXAO"
        r.falhar(CONEXAO, f"{type(erro).__name__}: {erro}")
        return r
    except httpx.DecodingError as erro:
        r.falhar(SERIALIZACAO, f"resposta não pôde ser decodificada: {erro}")
        return r
    except httpx.HTTPError as erro:
        r.falhar(REQUEST, f"{type(erro).__name__}: {erro}")
        return r
    finally:
        r.duracao_ms = round((time.perf_counter() - inicio) * 1000)

    r.status = str(resposta.status_code)
    r.resposta = resposta.text[:400] or "(corpo vazio)"
    try:
        _validar(teste, resposta, request_id, r)
    except Exception as erro:  # falha do próprio Cliente ao ler a resposta
        r.falhar(INTERPRETACAO, f"{type(erro).__name__}: {erro}")
    return r


def executar_bateria_rest(cfg: Config, alvo: Alvo, registro: Registro) -> Bateria:
    """Executa R1–R5 contra um Servidor REST."""
    resultados = []
    # trust_env=False: ignora proxies do sistema, que quebram chamadas na rede do laboratório.
    with httpx.Client(timeout=cfg.timeout, trust_env=False) as http:
        for teste in TESTES:
            resultado = executar_teste(http, cfg, alvo, teste)
            registro.registrar(resultado, alvo.server_team)
            resultados.append(resultado)
    return Bateria("REST", alvo.endereco, alvo.server_team, resultados)


def main() -> int:
    cfg = carregar_config("Cliente REST da Catalog & Quote API (testes R1-R5).")
    if not cfg.alvos_rest:
        print("Informe REST_BASE_URL no .env, no ambiente ou em --rest-base-url.", file=sys.stderr)
        return 2
    registro = Registro(cfg.client_team, cfg.log_file)
    baterias = [executar_bateria_rest(cfg, alvo, registro) for alvo in cfg.alvos_rest]
    exibir_matriz(cfg.client_team, baterias, cfg.log_file)
    return 0 if all(b.aprovada for b in baterias) else 1


if __name__ == "__main__":
    sys.exit(main())

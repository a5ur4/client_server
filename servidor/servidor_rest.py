"""Servidor REST da Catalog & Quote API (FastAPI).

Uso:
    python servidor_rest.py            (somente REST)
    python iniciar.py                  (REST + gRPC)

Documentação interativa: http://localhost:8080/docs
"""
import time

import uvicorn
from config import CFG
from fastapi import Depends, FastAPI, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, StrictFloat, StrictInt, StrictStr, ValidationError
from registro import registrar
from starlette.exceptions import HTTPException as StarletteHTTPException

BASE_PATH = "/api/v1"

# Catálogo fixo do contrato, mantido em memória (valores em centavos inteiros).
CATALOGO = {
    "KB-100": {"sku": "KB-100", "name": "Teclado Mecânico", "unitPriceCents": 25990, "available": True},
    "MS-200": {"sku": "MS-200", "name": "Mouse Sem Fio", "unitPriceCents": 12990, "available": True},
    "HD-300": {"sku": "HD-300", "name": "Headset USB", "unitPriceCents": 19990, "available": True},
    "MN-400": {"sku": "MN-400", "name": "Monitor 27", "unitPriceCents": 119990, "available": True},
}


class RespostaJSON(JSONResponse):
    media_type = "application/json; charset=utf-8"


class ItemCotacao(BaseModel):
    sku: StrictStr
    quantity: StrictInt | StrictFloat


class PedidoCotacao(BaseModel):
    items: list[ItemCotacao]


class Produto(BaseModel):
    sku: str
    name: str
    unitPriceCents: int
    available: bool


class Cotacao(BaseModel):
    requestId: str
    subtotalCents: int
    discountPercent: int
    discountCents: int
    totalCents: int


class Erro(BaseModel):
    code: str
    message: str
    requestId: str


class ErroContrato(Exception):
    """Erro previsto no contrato: vira a resposta padrão {code, message, requestId}."""

    def __init__(self, status: int, code: str, message: str):
        self.status = status
        self.code = code
        self.message = message


app = FastAPI(title="Catalog & Quote API", version="v1",
              description="ConectaShop — contrato REST do laboratório de interoperabilidade.")


def resposta_erro(request: Request, status: int, code: str, message: str) -> RespostaJSON:
    request.state.code = code
    return RespostaJSON(status_code=status, content={
        "code": code, "message": message, "requestId": request.headers.get("X-Request-ID", "")})


def _operacao(request: Request) -> str:
    caminho = request.url.path[len(BASE_PATH):]
    if request.method == "GET" and caminho.startswith("/products/"):
        return "GET_PRODUCT"
    if request.method == "POST" and caminho == "/quotes":
        return "POST_QUOTE"
    return f"{request.method}_{caminho}"


@app.middleware("http")
async def aplicar_contrato(request: Request, call_next):
    """Valida os headers obrigatórios, devolve o X-Request-ID e registra cada chamada."""
    if not request.url.path.startswith(BASE_PATH + "/"):
        return await call_next(request)

    inicio = time.perf_counter()
    request.state.code = ""
    request.state.input = "-"
    client_team = request.headers.get("X-Client-Team", "").strip()
    request_id = request.headers.get("X-Request-ID", "").strip()
    if not client_team or not request_id:
        resposta = resposta_erro(request, 400, "MISSING_REQUIRED_HEADER",
                                 "Headers X-Client-Team and X-Request-ID are required")
    else:
        try:
            resposta = await call_next(request)
        except Exception as erro:
            resposta = resposta_erro(request, 500, "INTERNAL_ERROR", "Unexpected server error")
            print(f"[servidor_rest] erro inesperado: {type(erro).__name__}: {erro}")
    if request_id:
        resposta.headers["X-Request-ID"] = request_id

    resultado: dict[str, object] = {"result": "OK" if resposta.status_code < 400 else "ERROR"}
    if request.state.code:
        resultado["code"] = request.state.code
    resultado["durationMs"] = round((time.perf_counter() - inicio) * 1000)
    registrar("REST", client_team, request_id, _operacao(request), {"input": request.state.input},
              str(resposta.status_code), **resultado)
    return resposta


@app.exception_handler(ErroContrato)
async def tratar_erro_contrato(request: Request, erro: ErroContrato) -> RespostaJSON:
    return resposta_erro(request, erro.status, erro.code, erro.message)


@app.exception_handler(StarletteHTTPException)
async def tratar_rota_fora_do_contrato(request: Request, erro: StarletteHTTPException) -> RespostaJSON:
    """Path ou método que o contrato não define: mantém o status HTTP e usa o corpo de erro padrão."""
    return resposta_erro(request, erro.status_code, "INVALID_REQUEST", "Path or method not defined by the contract")


def headers_do_contrato(
    x_client_team: str | None = Header(None, alias="X-Client-Team", description="Código da equipe Cliente"),
    x_request_id: str | None = Header(None, alias="X-Request-ID", description="Identificador único da chamada"),
) -> None:
    """Apenas documenta os headers no /docs; a validação acontece no middleware."""


_ERROS = {400: {"model": Erro}, 422: {"model": Erro}, 500: {"model": Erro}}

_CORPO_COTACAO = {"requestBody": {"required": True, "content": {"application/json": {
    "schema": {
        "type": "object",
        "required": ["items"],
        "properties": {"items": {
            "type": "array", "minItems": 1, "maxItems": 5,
            "items": {
                "type": "object",
                "required": ["sku", "quantity"],
                "properties": {"sku": {"type": "string"},
                               "quantity": {"type": "integer", "minimum": 1, "maximum": 10}},
            },
        }},
    },
    "example": {"items": [{"sku": "KB-100", "quantity": 2}, {"sku": "MS-200", "quantity": 1}]},
}}}}


@app.get(BASE_PATH + "/products/{sku}", response_model=Produto, summary="Consultar produto",
         responses={400: {"model": Erro}, 404: {"model": Erro}, 500: {"model": Erro}},
         dependencies=[Depends(headers_do_contrato)])
def consultar_produto(sku: str, request: Request) -> RespostaJSON:
    request.state.input = sku
    produto = CATALOGO.get(sku)
    if produto is None:
        raise ErroContrato(404, "PRODUCT_NOT_FOUND", "Product not found")
    return RespostaJSON(produto)


def percentual_desconto(subtotal_cents: int) -> int:
    if subtotal_cents >= 100000:
        return 10
    if subtotal_cents >= 50000:
        return 5
    return 0


def calcular(pedido: PedidoCotacao) -> dict[str, int]:
    itens = pedido.items
    if not 1 <= len(itens) <= 5:
        raise ErroContrato(422, "INVALID_QUANTITY_OR_ITEMS", "items must contain 1 to 5 distinct products")
    if len({item.sku for item in itens}) != len(itens):
        raise ErroContrato(422, "INVALID_QUANTITY_OR_ITEMS", "Duplicated SKU in items")
    for item in itens:
        # 2.0 é o mesmo número JSON que 2; 1.5 não é uma quantidade inteira.
        if not 1 <= item.quantity <= 10 or item.quantity != int(item.quantity):
            raise ErroContrato(422, "INVALID_QUANTITY_OR_ITEMS", "quantity must be an integer between 1 and 10")

    subtotal = 0
    for item in itens:
        produto = CATALOGO.get(item.sku)
        if produto is None:
            raise ErroContrato(422, "INVALID_PRODUCT", f"Unknown SKU: {item.sku}")
        subtotal += produto["unitPriceCents"] * int(item.quantity)

    percentual = percentual_desconto(subtotal)
    desconto = subtotal * percentual // 100
    return {"subtotalCents": subtotal, "discountPercent": percentual,
            "discountCents": desconto, "totalCents": subtotal - desconto}


@app.post(BASE_PATH + "/quotes", response_model=Cotacao, summary="Calcular cotação",
          responses=_ERROS, openapi_extra=_CORPO_COTACAO, dependencies=[Depends(headers_do_contrato)])
async def calcular_cotacao(request: Request) -> RespostaJSON:
    # O corpo é lido direto da requisição para que JSON inválido ou campo ausente
    # resultem em 400 INVALID_REQUEST, como manda o contrato (e não no 422 padrão do FastAPI).
    try:
        pedido = PedidoCotacao.model_validate_json(await request.body())
    except ValidationError:
        request.state.input = "corpo-invalido"
        raise ErroContrato(400, "INVALID_REQUEST", "Invalid JSON body or missing required field")
    request.state.input = ",".join(f"{item.quantity}x{item.sku}" for item in pedido.items) or "sem-itens"
    return RespostaJSON({"requestId": request.headers["X-Request-ID"], **calcular(pedido)})


if __name__ == "__main__":
    print(f"Servidor REST {CFG.server_team} em http://{CFG.host}:{CFG.rest_port}{BASE_PATH}")
    uvicorn.run(app, host=CFG.host, port=CFG.rest_port, access_log=False)

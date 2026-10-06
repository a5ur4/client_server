"""Autoverificação do Servidor: exercita todos os casos do contrato, inclusive os de erro.

Rode com os Servidores no ar (python iniciar.py), antes do sorteio:
    python verificar_contrato.py
    python verificar_contrato.py --rest-base-url http://127.0.0.1:8080 --grpc-target 127.0.0.1:50051
"""
import argparse
import sys
import uuid

import grpc
import httpx
import shipping_pb2 as pb
import shipping_pb2_grpc as pb_grpc

falhas = 0


def conferir(nome: str, obtido: object, esperado: object) -> None:
    global falhas
    if obtido == esperado:
        print(f"  PASS  {nome}")
    else:
        falhas += 1
        print(f"  FAIL  {nome}\n        obtido  : {obtido!r}\n        esperado: {esperado!r}")


def verificar_rest(base_url: str) -> None:
    print(f"REST {base_url}")
    api = base_url.rstrip("/") + "/api/v1"
    http = httpx.Client(timeout=5, trust_env=False)

    def headers() -> dict[str, str]:
        return {"X-Client-Team": "C99", "X-Request-ID": f"verif-{uuid.uuid4().hex[:8]}"}

    def resumo(resposta: httpx.Response) -> tuple:
        return resposta.status_code, resposta.json().get("code")

    def cotar(corpo, cabecalhos=None) -> httpx.Response:
        cabecalhos = cabecalhos or {**headers(), "Content-Type": "application/json"}
        conteudo = corpo if isinstance(corpo, str) else httpx.Request("POST", api, json=corpo).content
        return http.post(f"{api}/quotes", headers=cabecalhos, content=conteudo)

    enviados = headers()
    r = http.get(f"{api}/products/KB-100", headers=enviados)
    conferir("GET KB-100 -> 200 com o produto do contrato", (r.status_code, r.json()), (200, {
        "sku": "KB-100", "name": "Teclado Mecânico", "unitPriceCents": 25990, "available": True}))
    conferir("X-Request-ID devolvido no header", r.headers.get("X-Request-ID"), enviados["X-Request-ID"])
    conferir("Content-Type application/json; charset=utf-8",
             r.headers.get("Content-Type", "").lower(), "application/json; charset=utf-8")
    for sku, preco in [("MS-200", 12990), ("HD-300", 19990), ("MN-400", 119990)]:
        r = http.get(f"{api}/products/{sku}", headers=headers())
        conferir(f"GET {sku} -> unitPriceCents={preco}", r.json().get("unitPriceCents"), preco)

    enviados = headers()
    r = http.get(f"{api}/products/XX-999", headers=enviados)
    conferir("GET XX-999 -> 404 PRODUCT_NOT_FOUND com requestId", (r.status_code, r.json()), (404, {
        "code": "PRODUCT_NOT_FOUND", "message": r.json().get("message"), "requestId": enviados["X-Request-ID"]}))
    r = http.get(f"{api}/products/KB-100", headers={"X-Request-ID": "verif-sem-equipe"})
    conferir("sem X-Client-Team -> 400 MISSING_REQUIRED_HEADER", resumo(r), (400, "MISSING_REQUIRED_HEADER"))
    r = http.get(f"{api}/products/KB-100", headers={"X-Client-Team": "C99"})
    conferir("sem X-Request-ID -> 400 MISSING_REQUIRED_HEADER", resumo(r), (400, "MISSING_REQUIRED_HEADER"))

    def valores(resposta: httpx.Response) -> tuple:
        c = resposta.json()
        return (resposta.status_code, c.get("subtotalCents"), c.get("discountPercent"),
                c.get("discountCents"), c.get("totalCents"))

    r = cotar({"items": [{"sku": "KB-100", "quantity": 2}, {"sku": "MS-200", "quantity": 1}]})
    conferir("cotação 2xKB-100 + 1xMS-200 (5%)", valores(r), (200, 64970, 5, 3248, 61722))
    r = cotar({"items": [{"sku": "MN-400", "quantity": 1}]})
    conferir("cotação 1xMN-400 (10%)", valores(r), (200, 119990, 10, 11999, 107991))
    r = cotar({"items": [{"sku": "HD-300", "quantity": 1}]})
    conferir("cotação 1xHD-300 (0%)", valores(r), (200, 19990, 0, 0, 19990))
    r = cotar('{"items": [{"sku": "HD-300", "quantity": 1}]}', headers())
    conferir("cotação sem header Content-Type é aceita", valores(r), (200, 19990, 0, 0, 19990))

    conferir("JSON inválido -> 400 INVALID_REQUEST", resumo(cotar('{"items": [')), (400, "INVALID_REQUEST"))
    conferir("sem items -> 400 INVALID_REQUEST", resumo(cotar({})), (400, "INVALID_REQUEST"))
    conferir("item sem quantity -> 400 INVALID_REQUEST",
             resumo(cotar({"items": [{"sku": "KB-100"}]})), (400, "INVALID_REQUEST"))
    conferir("SKU inexistente -> 422 INVALID_PRODUCT",
             resumo(cotar({"items": [{"sku": "XX-999", "quantity": 1}]})), (422, "INVALID_PRODUCT"))
    for quantidade in (0, 11):
        conferir(f"quantity={quantidade} -> 422 INVALID_QUANTITY_OR_ITEMS",
                 resumo(cotar({"items": [{"sku": "KB-100", "quantity": quantidade}]})),
                 (422, "INVALID_QUANTITY_OR_ITEMS"))
    conferir("SKU duplicado -> 422 INVALID_QUANTITY_OR_ITEMS",
             resumo(cotar({"items": [{"sku": "KB-100", "quantity": 1}, {"sku": "KB-100", "quantity": 2}]})),
             (422, "INVALID_QUANTITY_OR_ITEMS"))
    conferir("items vazio -> 422 INVALID_QUANTITY_OR_ITEMS",
             resumo(cotar({"items": []})), (422, "INVALID_QUANTITY_OR_ITEMS"))
    seis = [{"sku": f"KB-10{i}", "quantity": 1} for i in range(6)]
    conferir("6 itens -> 422 INVALID_QUANTITY_OR_ITEMS",
             resumo(cotar({"items": seis})), (422, "INVALID_QUANTITY_OR_ITEMS"))
    http.close()


def verificar_grpc(target: str) -> None:
    print(f"\ngRPC {target}")
    canal = grpc.insecure_channel(target, options=[("grpc.enable_http_proxy", 0)])
    stub = pb_grpc.ShippingServiceStub(canal)
    equipe = (("x-client-team", "C99"),)

    def frete(peso, zona, modo, request_id="verif-grpc", metadata=equipe) -> tuple:
        try:
            r = stub.CalculateShipping(pb.ShippingRequest(
                request_id=request_id, weight_grams=peso, zone=zona, mode=modo), metadata=metadata, timeout=5)
            return r.price_cents, r.estimated_days, r.request_id
        except grpc.RpcError as erro:
            return erro.code().name, erro.details()

    saude = stub.Health(pb.HealthRequest(), metadata=equipe, timeout=5)
    conferir("Health -> SERVING", saude.status, "SERVING")
    conferir("Health -> server_team preenchido", bool(saude.server_team), True)
    try:
        stub.Health(pb.HealthRequest(), timeout=5)
        obtido = ("OK", "")
    except grpc.RpcError as erro:
        obtido = (erro.code().name, erro.details())
    conferir("Health sem x-client-team -> MISSING_CLIENT_TEAM", obtido, ("INVALID_ARGUMENT", "MISSING_CLIENT_TEAM"))

    casos = [
        (1500, pb.LOCAL, pb.STANDARD, 1800, 2), (2500, pb.REGIONAL, pb.EXPRESS, 4600, 2),
        (1000, pb.NATIONAL, pb.STANDARD, 3400, 7), (1, pb.LOCAL, pb.EXPRESS, 2200, 1),
        (1001, pb.REGIONAL, pb.STANDARD, 2600, 4), (30000, pb.NATIONAL, pb.EXPRESS, 22500, 3),
    ]
    for peso, zona, modo, preco, dias in casos:
        nome = f"{peso}g {pb.ShippingZone.Name(zona)} {pb.ShippingMode.Name(modo)} -> {preco} centavos, {dias} dia(s)"
        conferir(nome, frete(peso, zona, modo), (preco, dias, "verif-grpc"))

    invalido = "INVALID_ARGUMENT"
    conferir("sem x-client-team -> MISSING_CLIENT_TEAM",
             frete(1000, pb.LOCAL, pb.STANDARD, metadata=None), (invalido, "MISSING_CLIENT_TEAM"))
    conferir("request_id vazio -> MISSING_REQUEST_ID",
             frete(1000, pb.LOCAL, pb.STANDARD, request_id=""), (invalido, "MISSING_REQUEST_ID"))
    conferir("weight_grams=0 -> INVALID_WEIGHT", frete(0, pb.LOCAL, pb.STANDARD), (invalido, "INVALID_WEIGHT"))
    conferir("weight_grams=30001 -> INVALID_WEIGHT", frete(30001, pb.LOCAL, pb.STANDARD), (invalido, "INVALID_WEIGHT"))
    conferir("zone UNSPECIFIED -> INVALID_ZONE",
             frete(1000, pb.SHIPPING_ZONE_UNSPECIFIED, pb.STANDARD), (invalido, "INVALID_ZONE"))
    conferir("mode UNSPECIFIED -> INVALID_MODE",
             frete(1000, pb.LOCAL, pb.SHIPPING_MODE_UNSPECIFIED), (invalido, "INVALID_MODE"))
    canal.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Autoverificação do Servidor contra o contrato.")
    parser.add_argument("--rest-base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--grpc-target", default="127.0.0.1:50051")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding=None if sys.stdout.isatty() else "utf-8", errors="replace")
    verificar_rest(args.rest_base_url)
    verificar_grpc(args.grpc_target)
    print(f"\n{'TUDO CERTO' if falhas == 0 else f'{falhas} FALHA(S)'}")
    return 0 if falhas == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

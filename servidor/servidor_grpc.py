"""Servidor gRPC do ShippingService.

Uso:
    python servidor_grpc.py            (somente gRPC)
    python iniciar.py                  (REST + gRPC)

Os stubs (shipping_pb2*.py) são gerados a partir de proto/shipping.proto com
`python gerar_stubs.py`.
"""
import time
from concurrent import futures

import grpc
import shipping_pb2 as pb
import shipping_pb2_grpc as pb_grpc
from config import CFG
from registro import registrar

# Tabelas do contrato, em centavos e dias.
TARIFA_BASE = {
    (pb.LOCAL, pb.STANDARD): 1000, (pb.LOCAL, pb.EXPRESS): 1600,
    (pb.REGIONAL, pb.STANDARD): 1800, (pb.REGIONAL, pb.EXPRESS): 2800,
    (pb.NATIONAL, pb.STANDARD): 3000, (pb.NATIONAL, pb.EXPRESS): 4500,
}
ADICIONAL_POR_KG = {pb.STANDARD: 400, pb.EXPRESS: 600}
PRAZO_DIAS = {
    (pb.LOCAL, pb.STANDARD): 2, (pb.LOCAL, pb.EXPRESS): 1,
    (pb.REGIONAL, pb.STANDARD): 4, (pb.REGIONAL, pb.EXPRESS): 2,
    (pb.NATIONAL, pb.STANDARD): 7, (pb.NATIONAL, pb.EXPRESS): 3,
}
ZONAS = {pb.LOCAL, pb.REGIONAL, pb.NATIONAL}


class ArgumentoInvalido(Exception):
    """Violação de uma regra do contrato: vira INVALID_ARGUMENT com a descrição informada."""


def calcular_frete(peso_gramas: int, zona: int, modo: int) -> tuple[int, int]:
    """Devolve (price_cents, estimated_days). Cobra por quilograma iniciado."""
    quilos_cobrados = -(-peso_gramas // 1000)  # teto da divisão inteira
    preco = TARIFA_BASE[(zona, modo)] + quilos_cobrados * ADICIONAL_POR_KG[modo]
    return preco, PRAZO_DIAS[(zona, modo)]


def _nome(enum, valor: int) -> str:
    """Nome do valor do enum para o log; valores fora do enum aparecem como número."""
    try:
        return enum.Name(valor)
    except ValueError:
        return str(valor)


class ShippingService(pb_grpc.ShippingServiceServicer):

    def _atender(self, operacao: str, request_id: str, parametros: dict[str, object],
                 context: grpc.ServicerContext, acao):
        """Exige x-client-team, executa a regra, registra a chamada e traduz os erros."""
        inicio = time.perf_counter()
        client_team = dict(context.invocation_metadata()).get("x-client-team", "").strip()
        status, descricao, resposta = grpc.StatusCode.OK, "", None
        try:
            if not client_team:
                raise ArgumentoInvalido("MISSING_CLIENT_TEAM")
            resposta = acao()
        except ArgumentoInvalido as erro:
            status, descricao = grpc.StatusCode.INVALID_ARGUMENT, str(erro)
        except Exception as erro:
            status, descricao = grpc.StatusCode.INTERNAL, "INTERNAL_ERROR"
            print(f"[servidor_grpc] erro inesperado: {type(erro).__name__}: {erro}")

        resultado: dict[str, object] = {}
        if isinstance(resposta, pb.ShippingResponse):
            resultado["priceCents"] = resposta.price_cents
            resultado["estimatedDays"] = resposta.estimated_days
        resultado["result"] = "OK" if resposta is not None else "ERROR"
        if descricao:
            resultado["detail"] = descricao
        resultado["durationMs"] = round((time.perf_counter() - inicio) * 1000)
        registrar("GRPC", client_team, request_id, operacao, parametros, status.name, **resultado)

        if resposta is None:
            context.abort(status, descricao)
        return resposta

    def Health(self, request, context):
        return self._atender("Health", "", {}, context,
                             lambda: pb.HealthResponse(status="SERVING", server_team=CFG.server_team))

    def CalculateShipping(self, request, context):
        def acao():
            if not request.request_id:
                raise ArgumentoInvalido("MISSING_REQUEST_ID")
            if not 1 <= request.weight_grams <= 30000:
                raise ArgumentoInvalido("INVALID_WEIGHT")
            # Valores fora do enum também chegam aqui como inteiros desconhecidos.
            if request.zone not in ZONAS:
                raise ArgumentoInvalido("INVALID_ZONE")
            if request.mode not in ADICIONAL_POR_KG:
                raise ArgumentoInvalido("INVALID_MODE")
            preco, dias = calcular_frete(request.weight_grams, request.zone, request.mode)
            return pb.ShippingResponse(request_id=request.request_id, price_cents=preco,
                                       estimated_days=dias, server_team=CFG.server_team)

        parametros = {"weight": request.weight_grams, "zone": _nome(pb.ShippingZone, request.zone),
                      "mode": _nome(pb.ShippingMode, request.mode)}
        return self._atender("CalculateShipping", request.request_id, parametros, context, acao)


def criar_servidor() -> grpc.Server:
    """Cria e inicia o servidor gRPC (não bloqueia)."""
    servidor = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    pb_grpc.add_ShippingServiceServicer_to_server(ShippingService(), servidor)
    endereco = f"{CFG.host}:{CFG.grpc_port}"
    if servidor.add_insecure_port(endereco) == 0:
        raise RuntimeError(f"não foi possível abrir a porta gRPC {endereco}")
    servidor.start()
    return servidor


if __name__ == "__main__":
    servidor_grpc = criar_servidor()
    print(f"Servidor gRPC {CFG.server_team} em {CFG.host}:{CFG.grpc_port}")
    try:
        servidor_grpc.wait_for_termination()
    except KeyboardInterrupt:
        servidor_grpc.stop(grace=1)

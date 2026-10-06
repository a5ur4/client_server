"""Cliente gRPC do ShippingService — executa os testes G1–G5.

Uso:
    python cliente_grpc.py                      (lê GRPC_TARGET do arquivo .env)
    python cliente_grpc.py --grpc-target 10.0.0.24:50051 --grpc-server-team S04

Os stubs (shipping_pb2*.py) são gerados pela própria equipe a partir de
proto/shipping.proto com `python gerar_stubs.py`.
"""
import sys
import time

import grpc

import shipping_pb2 as pb
import shipping_pb2_grpc as pb_grpc
from config import Alvo, Config, carregar_config
from registro import (CONEXAO, CONTRATO, INTERPRETACAO, REGRA_NEGOCIO, SERIALIZACAO,
                      Bateria, Registro, Resultado, exibir_matriz, novo_request_id)

# (teste, weight_grams, zone, mode, price_cents esperado, estimated_days esperado)
CASOS_FRETE = [
    ("G2", 1500, pb.LOCAL, pb.STANDARD, 1800, 2),
    ("G3", 2500, pb.REGIONAL, pb.EXPRESS, 4600, 2),
    ("G4", 1000, pb.NATIONAL, pb.STANDARD, 3400, 7),
]


def _etapa_do_erro(erro: grpc.RpcError) -> str:
    codigo = erro.code()
    if codigo in (grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED):
        return CONEXAO
    if codigo == grpc.StatusCode.INTERNAL and "serializ" in (erro.details() or "").lower():
        return SERIALIZACAO
    # UNIMPLEMENTED (package/service/método diferente), INVALID_ARGUMENT indevido etc.
    return CONTRATO


def _descrever_frete(requisicao: pb.ShippingRequest) -> str:
    return (f"CalculateShipping(weight_grams={requisicao.weight_grams}, "
            f"zone={pb.ShippingZone.Name(requisicao.zone)}, mode={pb.ShippingMode.Name(requisicao.mode)})")


class ClienteGrpc:
    def __init__(self, cfg: Config, alvo: Alvo, registro: Registro):
        self.cfg = cfg
        self.alvo = alvo
        self.registro = registro
        # Começa com o código informado na configuração; o Health confirma quem respondeu.
        self.server_team = alvo.server_team
        self.metadata = (("x-client-team", cfg.client_team),)
        # Sem proxy HTTP do sistema: a conexão com o Servidor do laboratório é direta.
        self.canal = grpc.insecure_channel(alvo.endereco, options=[("grpc.enable_http_proxy", 0)])
        self.stub = pb_grpc.ShippingServiceStub(self.canal)

    def _chamar(self, r: Resultado, metodo, requisicao):
        """Executa a RPC medindo a duração. Devolve (resposta, erro); um dos dois é None."""
        inicio = time.perf_counter()
        try:
            resposta = metodo(requisicao, metadata=self.metadata, timeout=self.cfg.timeout)
            r.status = "OK"
            return resposta, None
        except grpc.RpcError as erro:
            r.status = erro.code().name
            r.resposta = f'details="{erro.details()}"'
            return None, erro
        finally:
            r.duracao_ms = round((time.perf_counter() - inicio) * 1000)

    def _novo_resultado(self, teste: str, operacao: str, requisicao: str, esperado: str) -> Resultado:
        return Resultado(teste=teste, protocolo="GRPC", operacao=operacao, destino=self.alvo.endereco,
                         request_id=novo_request_id(self.cfg.client_team, teste),
                         requisicao=requisicao, esperado=esperado)

    def testar_health(self) -> Resultado:
        r = self._novo_resultado("G1", "Health", "Health()",
                                 "status=SERVING; server_team identifica o servidor")
        r.observacoes.append("HealthRequest não possui request_id: o identificador é só do log do Cliente")
        resposta, erro = self._chamar(r, self.stub.Health, pb.HealthRequest())
        if erro is not None:
            r.falhar(_etapa_do_erro(erro), f"{erro.code().name}: {erro.details()}")
            return r
        r.resposta = f'status="{resposta.status}" server_team="{resposta.server_team}"'
        r.passou = True
        if resposta.status != "SERVING":
            r.falhar(CONTRATO, f'status="{resposta.status}", esperado "SERVING"')
        if not resposta.server_team:
            r.falhar(CONTRATO, "server_team vazio: não identifica o servidor")
        elif self.alvo.server_team and resposta.server_team != self.alvo.server_team:
            r.observacoes.append(f"servidor se identificou como {resposta.server_team}, "
                                 f"mas o esperado era {self.alvo.server_team}: confira o GRPC_TARGET")
        if resposta.server_team:
            self.server_team = resposta.server_team
        return r

    def testar_frete(self, teste: str, peso: int, zona: int, modo: int, preco: int, dias: int) -> Resultado:
        r = self._novo_resultado(teste, "CalculateShipping", "",
                                 f"price_cents={preco}; estimated_days={dias}")
        requisicao = pb.ShippingRequest(request_id=r.request_id, weight_grams=peso, zone=zona, mode=modo)
        r.requisicao = _descrever_frete(requisicao)
        resposta, erro = self._chamar(r, self.stub.CalculateShipping, requisicao)
        if erro is not None:
            r.falhar(_etapa_do_erro(erro), f"{erro.code().name}: {erro.details()}")
            return r
        r.resposta = (f'request_id="{resposta.request_id}" price_cents={resposta.price_cents} '
                      f'estimated_days={resposta.estimated_days} server_team="{resposta.server_team}"')
        r.extras["priceCents"] = resposta.price_cents
        r.extras["estimatedDays"] = resposta.estimated_days
        r.passou = True
        if resposta.price_cents != preco:
            r.falhar(REGRA_NEGOCIO, f"price_cents={resposta.price_cents}, esperado {preco}")
        if resposta.estimated_days != dias:
            r.falhar(REGRA_NEGOCIO, f"estimated_days={resposta.estimated_days}, esperado {dias}")
        if resposta.request_id != r.request_id:
            r.observacoes.append(f'request_id devolvido "{resposta.request_id}" difere do enviado')
        if not resposta.server_team:
            r.observacoes.append("server_team vazio na resposta")
        return r

    def testar_peso_invalido(self) -> Resultado:
        r = self._novo_resultado("G5", "CalculateShipping", "", "status INVALID_ARGUMENT; INVALID_WEIGHT")
        requisicao = pb.ShippingRequest(request_id=r.request_id, weight_grams=0, zone=pb.LOCAL, mode=pb.STANDARD)
        r.requisicao = _descrever_frete(requisicao)
        resposta, erro = self._chamar(r, self.stub.CalculateShipping, requisicao)
        if erro is None:
            r.resposta = f"price_cents={resposta.price_cents} estimated_days={resposta.estimated_days}"
            r.falhar(REGRA_NEGOCIO, "servidor aceitou weight_grams=0; esperado INVALID_ARGUMENT")
        elif erro.code() != grpc.StatusCode.INVALID_ARGUMENT:
            r.falhar(_etapa_do_erro(erro), f"status {erro.code().name}, esperado INVALID_ARGUMENT")
        elif "INVALID_WEIGHT" not in (erro.details() or "").upper():
            r.falhar(CONTRATO, f'descrição "{erro.details()}", esperado INVALID_WEIGHT')
        else:
            r.extras["details"] = erro.details()
            r.passou = True
        return r

    def executar_bateria(self) -> Bateria:
        # Health primeiro: confirma que o Servidor alcançado é o correto.
        testes = [("G1", "Health", self.testar_health)]
        testes += [(caso[0], "CalculateShipping", lambda caso=caso: self.testar_frete(*caso))
                   for caso in CASOS_FRETE]
        testes.append(("G5", "CalculateShipping", self.testar_peso_invalido))
        resultados = []
        for identificador, operacao, teste in testes:
            try:
                resultado = teste()
            except Exception as erro:  # falha do próprio Cliente ao montar ou ler a mensagem
                resultado = self._novo_resultado(identificador, operacao, "-", "-")
                resultado.falhar(INTERPRETACAO, f"{type(erro).__name__}: {erro}")
            self.registro.registrar(resultado, self.server_team)
            resultados.append(resultado)
        self.canal.close()
        return Bateria("gRPC", self.alvo.endereco, self.server_team, resultados)


def executar_bateria_grpc(cfg: Config, alvo: Alvo, registro: Registro) -> Bateria:
    """Executa G1–G5 contra um Servidor gRPC."""
    return ClienteGrpc(cfg, alvo, registro).executar_bateria()


def main() -> int:
    cfg = carregar_config("Cliente gRPC do ShippingService (testes G1-G5).")
    if not cfg.alvos_grpc:
        print("Informe GRPC_TARGET no .env, no ambiente ou em --grpc-target.", file=sys.stderr)
        return 2
    registro = Registro(cfg.client_team, cfg.log_file)
    baterias = [executar_bateria_grpc(cfg, alvo, registro) for alvo in cfg.alvos_grpc]
    exibir_matriz(cfg.client_team, baterias, cfg.log_file)
    return 0 if all(b.aprovada for b in baterias) else 1


if __name__ == "__main__":
    sys.exit(main())

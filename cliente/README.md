# ConectaShop — Grupo CLIENTE

Cliente REST (Catalog & Quote API) e Cliente gRPC (ShippingService) da dinâmica
IntegraLab. Executam automaticamente os testes R1–R5 e G1–G5 contra qualquer
Servidor que siga o contrato.

## Tecnologia

| Item | Escolha |
|---|---|
| Linguagem | Python 3.10 ou superior |
| Cliente REST | `httpx` |
| Cliente gRPC | `grpcio`, com stubs gerados por `grpcio-tools` a partir de `proto/shipping.proto` |

## Arquivos

| Arquivo | Função |
|---|---|
| `cliente_rest.py` | Cliente REST: testes R1–R5 |
| `cliente_grpc.py` | Cliente gRPC: testes G1–G5 (Health é o primeiro) |
| `executar.py` | Roda todas as baterias configuradas e mostra a matriz final |
| `config.py` | Leitura da configuração (argumentos, ambiente e `.env`) |
| `registro.py` | Saída no terminal, gravação do log e matriz de execução |
| `.env` / `.env.example` | Arquivo de configuração e modelo comentado |
| `proto/shipping.proto` | Contrato gRPC, idêntico ao do guia |
| `gerar_stubs.py` | Gera `shipping_pb2.py` e `shipping_pb2_grpc.py` |
| `logs/integracao_cliente.log` | Log de todas as tentativas |

## Instalação

No PowerShell, dentro da pasta `cliente`:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python gerar_stubs.py
```

No Linux/macOS, a ativação é `source .venv/bin/activate`.

## Configuração pelo arquivo `.env`

Nenhum endereço fica no código. Edite o arquivo `.env` desta pasta (o
`.env.example` traz o modelo comentado):

```ini
CLIENT_TEAM=C01

REST_BASE_URL=http://10.0.0.23:8080,http://10.0.0.25:8080
REST_SERVER_TEAM=S03,S05

GRPC_TARGET=10.0.0.24:50051,10.0.0.26:50051
GRPC_SERVER_TEAM=S04,S06
```

`REST_BASE_URL` e `GRPC_TARGET` aceitam um ou mais Servidores separados por
vírgula, e os códigos de equipe seguem a mesma ordem. Assim os dois Servidores
REST e os dois Servidores gRPC do sorteio ficam em um único arquivo.

| Variável | Argumento equivalente | Descrição |
|---|---|---|
| `CLIENT_TEAM` | `--client-team` | Código da nossa equipe |
| `REST_BASE_URL` | `--rest-base-url` | Servidor(es) REST, com ou sem `/api/v1` |
| `REST_SERVER_TEAM` | `--rest-server-team` | Equipe de cada Servidor REST (vai para o log) |
| `GRPC_TARGET` | `--grpc-target` | Servidor(es) gRPC, `host:porta` |
| `GRPC_SERVER_TEAM` | `--grpc-server-team` | Equipe de cada Servidor gRPC (o Health confirma) |
| `CLIENT_TIMEOUT` | `--timeout` | Segundos por chamada (padrão 5) |
| `CLIENT_LOG_FILE` | `--log-file` | Arquivo de log (padrão `logs/integracao_cliente.log`) |
| `ENV_FILE` | `--env-file` | Outro arquivo de configuração no lugar do `.env` |

Ordem de prioridade: argumento de linha de comando, variável de ambiente,
arquivo `.env`, valor padrão. Comentários no `.env` só em linha própria.

## Execução

Tudo o que está no `.env` (REST e gRPC, todos os Servidores):

```powershell
python executar.py
```

Só REST ou só gRPC:

```powershell
python cliente_rest.py
```

```powershell
python cliente_grpc.py
```

Trocar de Servidor sem editar o arquivo:

```powershell
python cliente_rest.py --rest-base-url http://10.0.0.23:8080 --rest-server-team S03
```

```powershell
python cliente_grpc.py --grpc-target 10.0.0.24:50051 --grpc-server-team S04
```

O código de saída é `0` quando todos os testes passam, `1` quando algum falha
e `2` quando nenhum endereço foi configurado.

## O que cada chamada envia

- REST: headers `X-Client-Team` e `X-Request-ID` em todas as chamadas, e
  `Content-Type: application/json` quando há body.
- gRPC: metadata `x-client-team` em todas as chamadas e um `request_id` único
  em cada `CalculateShipping`.
- O Request ID tem o formato `<equipe>-<teste>-<12 hex>`, por exemplo
  `C01-R3-af013b2201ce`, e aparece no terminal e no log.
- SKUs repetidos são somados antes do envio de uma cotação.

## Saída e log

Cada teste mostra no terminal protocolo, operação, destino, request, Request ID,
resultado esperado, status, resposta, duração e `PASS`/`FAIL`. Ao final sai a
matriz de execução, no formato pedido para o relatório:

```
== MATRIZ DE EXECUCAO - Cliente C01 ==
  Protocolo  Servidor  Destino                Testes  Resultado  Falhas (etapa)
  REST       S03       http://10.0.0.23:8080  R1-R5   5/5 PASS   -
  REST       S05       http://10.0.0.25:8080  R1-R5   4/5 FAIL   R3(regra_negocio)
  gRPC       S04       10.0.0.24:50051        G1-G5   5/5 PASS   -
  gRPC       S06       10.0.0.26:50051        G1-G5   0/5 FAIL   G1(conexao), G2(conexao), ...
```

Cada tentativa também é gravada em uma linha do log:

```
[2026-10-06T14:06:51] protocol=REST client=C01 server=S01 requestId=C01-R3-5b2b7dc4bba6 test=R3 operation=POST_QUOTE target=http://127.0.0.1:8081 status=200 durationMs=12 result=PASS
[2026-10-06T14:07:03] protocol=GRPC client=C01 server=S01 requestId=C01-G2-d754dac3b0cb test=G2 operation=CalculateShipping target=127.0.0.1:50061 status=OK durationMs=21 priceCents=1800 estimatedDays=2 result=PASS
```

Em caso de falha, a linha traz `failStage` e `detail`:

| `failStage` | Quando ocorre |
|---|---|
| `conexao` | Servidor inalcançável, recusa de conexão ou tempo esgotado |
| `request` | Endereço inválido ou erro ao montar/enviar a requisição |
| `serializacao` | Resposta que não é JSON válido ou mensagem gRPC que não desserializa |
| `contrato` | Status, campo, tipo ou código de erro diferente do contrato |
| `regra_negocio` | Formato correto, mas valor ou validação diferente do esperado |
| `interpretacao` | Erro do próprio Cliente ao ler a resposta |

O `PASS`/`FAIL` segue a tabela de testes do contrato. Outros desvios (por
exemplo, `X-Request-ID` não devolvido no header da resposta) não reprovam o
teste, mas ficam registrados no campo `obs`.

## Roteiro no dia da integração

1. Anotar código da equipe, host e porta de cada Servidor sorteado e preencher o `.env`.
2. Rodar `python cliente_grpc.py`: o G1 (Health) confirma qual Servidor respondeu.
   Se o `server_team` devolvido for diferente do informado, o Cliente avisa.
3. Rodar `python executar.py` para as quatro integrações e copiar a matriz final.
4. Para cada falha, anotar `failStage` e pedir ao grupo Servidor as linhas de
   log com o mesmo Request ID.
5. Se algo for corrigido no Cliente (sem alterar o contrato), rodar de novo: o
   log mantém a tentativa inicial e a final.

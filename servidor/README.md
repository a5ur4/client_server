# ConectaShop — Grupo SERVIDOR

Servidor REST (Catalog & Quote API) e Servidor gRPC (ShippingService) da
dinâmica IntegraLab, implementados exatamente conforme o contrato.

## Tecnologia

| Item | Escolha |
|---|---|
| Linguagem | Python 3.10 ou superior |
| Servidor REST | FastAPI + Uvicorn |
| Servidor gRPC | `grpcio`, com stubs gerados por `grpcio-tools` a partir de `proto/shipping.proto` |
| Persistência | SQLite (arquivo local, biblioteca padrão), usado só para o registro das chamadas |

O catálogo e as regras de cálculo ficam em memória. Nenhuma resposta do
contrato depende do SQLite nem de banco de dados externo.

## Arquivos

| Arquivo | Função |
|---|---|
| `servidor_rest.py` | API REST: `GET /api/v1/products/{sku}` e `POST /api/v1/quotes` |
| `servidor_grpc.py` | ShippingService: `Health` e `CalculateShipping` |
| `iniciar.py` | Sobe REST e gRPC no mesmo processo |
| `config.py` | Leitura da configuração (ambiente e `.env`) |
| `.env` / `.env.example` | Arquivo de configuração e modelo comentado |
| `registro.py` | Log no terminal, em arquivo e no SQLite |
| `banco.py` | Tabela `request_log` no SQLite |
| `consultar_logs.py` | Busca linhas de log por Request ID ou equipe Cliente |
| `verificar_contrato.py` | Autoteste de todos os casos do contrato, inclusive erros |
| `proto/shipping.proto` | Contrato gRPC, idêntico ao do guia |
| `gerar_stubs.py` | Gera `shipping_pb2.py` e `shipping_pb2_grpc.py` |
| `logs/integracao_servidor.log` | Log de todas as chamadas recebidas |

## Instalação

No PowerShell, dentro da pasta `servidor`:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python gerar_stubs.py
```

No Linux/macOS, a ativação é `source .venv/bin/activate`.

## Configuração pelo arquivo `.env`

Edite o arquivo `.env` desta pasta (o `.env.example` traz o modelo comentado):

```ini
SERVER_TEAM=S01
SERVER_HOST=0.0.0.0
REST_PORT=8080
GRPC_PORT=50051
```

| Variável | Argumento de `iniciar.py` | Padrão | Descrição |
|---|---|---|---|
| `SERVER_TEAM` | `--server-team` | `S01` | Código da nossa equipe (`server_team` e logs) |
| `SERVER_HOST` | `--host` | `0.0.0.0` | Interface de escuta; `0.0.0.0` aceita outras máquinas |
| `REST_PORT` | `--rest-port` | `8080` | Porta da API REST |
| `GRPC_PORT` | `--grpc-port` | `50051` | Porta do ShippingService |
| `SERVER_LOG_FILE` | — | `logs/integracao_servidor.log` | Arquivo de log |
| `SERVER_DB_FILE` | — | `dados/conectashop.db` | Arquivo SQLite |
| `ENV_FILE` | — | `.env` | Outro arquivo de configuração no lugar do `.env` |

Ordem de prioridade: argumento de `iniciar.py`, variável de ambiente, arquivo
`.env`, valor padrão. Comentários no `.env` só em linha própria.

## Inicialização

Os dois serviços juntos, com a configuração do `.env` (recomendado):

```powershell
python iniciar.py
```

Sobrescrevendo um valor pela linha de comando:

```powershell
python iniciar.py --server-team S02 --rest-port 8090
```

Ao iniciar, o programa mostra o IP da máquina na rede, já no formato de
`REST_BASE_URL` e `GRPC_TARGET` para informar ao professor.

Separadamente, se necessário:

```powershell
python servidor_rest.py
```

```powershell
python servidor_grpc.py
```

A documentação interativa da API REST fica em `http://localhost:8080/docs`.

## Verificação antes do sorteio

Com os Servidores no ar, em outro terminal:

```powershell
python verificar_contrato.py
```

O autoteste cobre catálogo, cotações, headers ausentes, todos os códigos de
erro REST, as seis combinações de zona e modo, peso por quilograma iniciado e
todos os erros gRPC.

Para testar de outra máquina, como pede o guia:

```powershell
python verificar_contrato.py --rest-base-url http://IP_DO_SERVIDOR:8080 --grpc-target IP_DO_SERVIDOR:50051
```

Se funcionar em `localhost` e falhar de outra máquina, o bloqueio costuma ser o
firewall: na primeira execução o Windows pergunta se o Python pode aceitar
conexões de rede, e é preciso permitir para o tipo de rede do laboratório.

## Decisões de interpretação do contrato

| Situação | Resposta |
|---|---|
| Header `X-Client-Team` ou `X-Request-ID` ausente | `400 MISSING_REQUIRED_HEADER`, verificado antes de qualquer outra regra |
| JSON inválido, campo ausente ou campo com tipo errado | `400 INVALID_REQUEST` |
| `items` vazio ou com mais de 5 itens, `quantity` fora de 1–10 ou não inteira, SKU duplicado | `422 INVALID_QUANTITY_OR_ITEMS` |
| SKU fora do catálogo na cotação | `422 INVALID_PRODUCT` (avaliado depois das regras de quantidade) |
| Body JSON enviado sem header `Content-Type` | Aceito: o contrato não define erro para esse caso |
| Path ou método que o contrato não define | Status HTTP normal (`404`/`405`) com o corpo de erro padrão e `code` `INVALID_REQUEST` |
| Erro inesperado | `500 INTERNAL_ERROR` no REST e `INTERNAL` / `INTERNAL_ERROR` no gRPC; o serviço continua no ar |
| Metadata `x-client-team` ausente, inclusive em `Health` | `INVALID_ARGUMENT` / `MISSING_CLIENT_TEAM` |
| `zone` ou `mode` com valor fora do enum | `INVALID_ZONE` / `INVALID_MODE` |
| Ordem de validação gRPC | `x-client-team`, `request_id`, `weight_grams`, `zone`, `mode` |

O `X-Request-ID` recebido é devolvido no header de todas as respostas REST,
inclusive nas de erro. Nenhuma autenticação, header ou metadata extra é exigida.

## Logs

Uma linha por chamada recebida, no terminal e em `logs/integracao_servidor.log`:

```
[2026-10-06T13:40:59] protocol=REST server=S01 client=C01 requestId=C01-R1-3262ad8cc468 operation=GET_PRODUCT input=KB-100 status=200 result=OK durationMs=1
[2026-10-06T13:40:59] protocol=REST server=S01 client=C01 requestId=C01-R5-0ddbedde6fa9 operation=POST_QUOTE input=1xXX-999 status=422 result=ERROR code=INVALID_PRODUCT durationMs=1
[2026-10-06T13:40:59] protocol=GRPC server=S01 client=C01 requestId=C01-G2-aae483e5f41d operation=CalculateShipping weight=1500 zone=LOCAL mode=STANDARD status=OK priceCents=1800 estimatedDays=2 result=OK durationMs=0
```

`result=ERROR` indica que a chamada terminou com um erro previsto no contrato
(ou com `500`/`INTERNAL`); o campo `code` ou `detail` diz qual. `Health` não
possui Request ID e aparece com `requestId=-`.

Para entregar a um grupo Cliente as linhas de um Request ID:

```powershell
python consultar_logs.py --request-id C01-R3-af013b2201ce
```

```powershell
python consultar_logs.py --client C01 --ultimos 20
```

## Roteiro no dia da integração

1. Ajustar `SERVER_TEAM` no `.env`, subir com `python iniciar.py` e rodar `verificar_contrato.py` de outra máquina.
2. Informar ao professor código da equipe, `REST_BASE_URL`, `GRPC_TARGET` e estado (`REST=UP; gRPC=UP`).
3. Manter o processo ativo durante toda a janela de testes.
4. Compartilhar com os Clientes apenas endereço, porta, código da equipe e estado do serviço.
5. Ao final, usar `consultar_logs.py --client <código>` para montar a matriz e as evidências do relatório.

# Relatório técnico — IntegraLab (ConectaShop)

> Modelo. Preencha os campos entre colchetes depois da integração e exporte em
> PDF ou DOCX. Use as seções do papel sorteado (Cliente ou Servidor).

## 1. Identificação

- Disciplina: Sistemas Distribuídos e Computação Paralela
- Equipe: [código, ex.: C01 ou S01] — [integrantes]
- Papel na dinâmica: [CLIENTE | SERVIDOR]
- Data da integração: [data]

## 2. Tecnologias escolhidas

| Item | Cliente | Servidor |
|---|---|---|
| Linguagem | Python | Python |
| REST | `httpx` | FastAPI + Uvicorn |
| gRPC | `grpcio` + stubs de `grpcio-tools` | `grpcio` + stubs de `grpcio-tools` |
| Persistência | Arquivo de log | Catálogo em memória; SQLite local para o registro das chamadas |

## 3. Arquitetura

### Se CLIENTE

- `config.py` lê `REST_BASE_URL`, `GRPC_TARGET` e os códigos de equipe de
  argumentos ou variáveis de ambiente; nenhum endereço fica no código.
- `cliente_rest.py` descreve R1–R5 como dados (método, caminho, body, status e
  campos esperados), envia cada requisição com `X-Client-Team` e `X-Request-ID`
  e valida a resposta somente com base no contrato.
- `cliente_grpc.py` abre um canal para `GRPC_TARGET`, envia a metadata
  `x-client-team`, chama `Health` primeiro e depois `CalculateShipping` (G2–G5),
  com um `request_id` único por chamada.
- `registro.py` mostra cada tentativa no terminal e grava uma linha no log, com
  `PASS`/`FAIL` e, nas falhas, a etapa em que ocorreram.

### Se SERVIDOR

- `servidor_rest.py` (FastAPI): um middleware valida os headers obrigatórios,
  devolve o `X-Request-ID` e registra a chamada; os endpoints aplicam catálogo,
  validações e cálculo de desconto; os erros saem no formato padrão
  `{code, message, requestId}`.
- `servidor_grpc.py`: implementa `Health` e `CalculateShipping` a partir do
  `shipping.proto`, com as tabelas de tarifa, adicional por quilograma iniciado
  e prazo; violações viram `INVALID_ARGUMENT` com a descrição do contrato.
- `registro.py` e `banco.py`: cada chamada gera uma linha no terminal, no
  arquivo de log e na tabela `request_log` do SQLite, consultável por Request ID.
- `iniciar.py` sobe os dois serviços em `0.0.0.0`, com portas configuráveis.

## 4. Parceiros sorteados

### Se CLIENTE — Servidores testados

| Protocolo | Equipe | Endereço |
|---|---|---|
| REST | [S__] | [http://host:porta] |
| REST | [S__] | [http://host:porta] |
| gRPC | [S__] | [host:porta] |
| gRPC | [S__] | [host:porta] |

### Se SERVIDOR — Endereços publicados e Clientes recebidos

- REST_BASE_URL: [http://host:8080]
- GRPC_TARGET: [host:50051]

| Protocolo | Equipe Cliente |
|---|---|
| REST | [C__] |
| REST | [C__] |
| gRPC | [C__] |
| gRPC | [C__] |

## 5. Matriz de execução

| Protocolo | Parceiro | Testes | Resultado inicial | Resultado final | Request IDs | Observação |
|---|---|---|---|---|---|---|
| REST | [__] | R1–R5 | [_/5] | [_/5] | [__] | [__] |
| REST | [__] | R1–R5 | [_/5] | [_/5] | [__] | [__] |
| gRPC | [__] | G1–G5 | [_/5] | [_/5] | [__] | [__] |
| gRPC | [__] | G1–G5 | [_/5] | [_/5] | [__] | [__] |

### Resultado por teste

| Teste | Esperado | Parceiro 1 | Parceiro 2 |
|---|---|---|---|
| R1 | HTTP 200; unitPriceCents=25990 | [PASS/FAIL] | [PASS/FAIL] |
| R2 | HTTP 404; PRODUCT_NOT_FOUND | [PASS/FAIL] | [PASS/FAIL] |
| R3 | HTTP 200; 64970 / 5% / 61722 | [PASS/FAIL] | [PASS/FAIL] |
| R4 | HTTP 200; 119990 / 10% / 11999 / 107991 | [PASS/FAIL] | [PASS/FAIL] |
| R5 | HTTP 422; INVALID_PRODUCT | [PASS/FAIL] | [PASS/FAIL] |
| G1 | SERVING; server_team | [PASS/FAIL] | [PASS/FAIL] |
| G2 | 1800 centavos; 2 dias | [PASS/FAIL] | [PASS/FAIL] |
| G3 | 4600 centavos; 2 dias | [PASS/FAIL] | [PASS/FAIL] |
| G4 | 3400 centavos; 7 dias | [PASS/FAIL] | [PASS/FAIL] |
| G5 | INVALID_ARGUMENT; INVALID_WEIGHT | [PASS/FAIL] | [PASS/FAIL] |

## 6. Evidências: logs correlacionados pelo Request ID

Para cada integração, cole a linha do Cliente e a linha do Servidor com o mesmo
`requestId`.

```
[linha do log do Cliente]
[linha do log do Servidor]
```

## 7. Falhas observadas

| Parceiro | Teste | Request ID | Etapa | Causa provável ou confirmada | Correção |
|---|---|---|---|---|---|
| [__] | [__] | [__] | [conexão / request / serialização / contrato / regra de negócio / interpretação] | [__] | [__ ou "nenhuma: falha do parceiro"] |

Do lado do Servidor, classifique como problema de rede/ambiente, divergência de
contrato, erro de regra de negócio ou erro do Cliente. Registre também que
nenhuma correção alterou o contrato.

## 8. Comparação prática REST × gRPC

Pontos para desenvolver com a experiência real da equipe:

- Contrato: texto e exemplos (REST) × arquivo `.proto` compilável (gRPC).
- Ambiguidade: quais casos do contrato REST exigiram interpretação e quais o
  `.proto` resolveu sozinho (nomes, tipos, enums).
- Erros: status HTTP + corpo JSON × status gRPC + descrição.
- Depuração: REST legível com `curl`/navegador × gRPC binário, dependente de stubs.
- Esforço de implementação e de troca de servidor em cada protocolo.
- Medidas: [duração média observada em REST] × [duração média observada em gRPC].

## 9. Conclusão

[O que tornou as integrações interoperáveis ou incompatíveis: fidelidade ao
contrato, tratamento de headers/metadata, tipos numéricos, arredondamento do
desconto, peso por quilograma iniciado, configuração de rede.]

# IntegraLab — ConectaShop

Trabalho de Sistemas Distribuídos: interoperabilidade REST e gRPC orientada por
contratos. Este diretório tem os dois papéis da dinâmica, em projetos
independentes, para usar o que for sorteado.

| Pasta | Papel | Conteúdo | Instruções |
|---|---|---|---|
| `cliente/` | Grupo CLIENTE | Cliente REST (R1–R5) e Cliente gRPC (G1–G5) | [cliente/README.md](cliente/README.md) |
| `servidor/` | Grupo SERVIDOR | Servidor REST (FastAPI) e Servidor gRPC | [servidor/README.md](servidor/README.md) |
| `simulacao/` | Apoio | Simulação local da dinâmica (não faz parte da entrega) | abaixo |

As pastas `cliente/` e `servidor/` não compartilham código: cada uma tem a
própria cópia do `shipping.proto`, os próprios stubs, o próprio
`requirements.txt` e o próprio `.env`. Na entrega, envie apenas a pasta do
papel sorteado.

`RELATORIO_MODELO.md` traz a estrutura do relatório final para os dois papéis.

## Configuração

Cada projeto lê um arquivo `.env` na própria pasta:

- `cliente/.env`: código da equipe e os Servidores sorteados (`REST_BASE_URL`, `GRPC_TARGET`).
- `servidor/.env`: código da equipe, interface de escuta e portas.

Os códigos `C01` e `S01` são apenas padrões: troque pelo código que o professor
atribuir à equipe.

## Teste local (antes do sorteio)

Já existe um ambiente virtual em `.venv` com as dependências das duas pastas.

Terminal 1, servidores (lê `servidor/.env`):

```powershell
cd servidor
..\.venv\Scripts\python.exe iniciar.py
```

Terminal 2, autoteste do servidor:

```powershell
cd servidor
..\.venv\Scripts\python.exe verificar_contrato.py
```

Terminal 2, clientes contra o servidor local (lê `cliente/.env`):

```powershell
cd cliente
..\.venv\Scripts\python.exe executar.py
```

## Simulação da dinâmica

Um único comando sobe dois Servidores (equipes S01 e S02, em portas diferentes),
roda a autoverificação de contrato em cada um, executa o Cliente C01 contra os
quatro serviços e mostra a matriz de execução e a correlação de logs pelo
Request ID:

```powershell
.venv\Scripts\python.exe simulacao\simular.py
```

Com um Servidor fora do ar no sorteio, para ver uma falha registrada e classificada:

```powershell
.venv\Scripts\python.exe simulacao\simular.py --com-falha
```

Os logs da simulação ficam em `simulacao/logs` e não se misturam com os logs de
entrega de `cliente/logs` e `servidor/logs`.

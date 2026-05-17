# Dashboard B3

Dashboard Flask para monitorar ativos da B3 usando a API da brapi.

## Recursos

- Ativos B3: PETR4, VALE3, ITUB4, BBDC4, ABEV3, WEGE3, BBAS3 e B3SA3.
- Versao desktop e mobile/iPhone.
- Atualizacao em tempo real via Server-Sent Events (`/api/mercado/stream`).
- Banco SQLite local com snapshots em `market_snapshots` e cotacoes em `asset_quotes`.
- Autenticacao HTTP Basic.
- Headers de seguranca.
- Deploy preparado para Google Cloud Run.

## Configuracao local

Crie um arquivo `.env` com base em `.env.example`:

```env
BRAPI_TOKEN=sua_chave_brapi
GOOGLE_FINANCE_CSV_URL=
GOOGLE_FINANCE_TIMEOUT=12
DASHBOARD_USER=admin
DASHBOARD_PASSWORD=sua_senha_forte
DATABASE_PATH=dashboard_b3.sqlite3
MARKET_REFRESH_SECONDS=60
STREAM_HEARTBEAT_SECONDS=15
HOST=0.0.0.0
PORT=5000
DEBUG=0
```

## Dados em tempo real

O dashboard abre `/api/mercado/stream` no navegador e recebe novas leituras continuamente. Cada leitura fica persistida no SQLite definido por `DATABASE_PATH`.

Observacao: as cotacoes publicas da B3 normalmente possuem atraso e dados em tempo real oficiais dependem de contratacao B2B. A integracao atual usa `brapi.dev` quando `BRAPI_TOKEN` esta configurado e preserva a estrutura para trocar a fonte por um feed oficial da B3.

## Modelo Google

Para alimentar o dashboard com Google Sheets, publique uma planilha como CSV e configure `GOOGLE_FINANCE_CSV_URL`.

Colunas aceitas: `ticker`, `nome`, `date`, `open`, `high`, `low`, `close`, `volume`, `variacao`. A planilha pode usar `GOOGLEFINANCE` para montar esses campos. Segundo a documentacao oficial do Google Sheets, `GOOGLEFINANCE` busca informacoes atuais ou historicas do Google Finance, mas nem todos os ativos/bolsas sao suportados e dados historicos possuem restricoes de acesso por API.

Exemplo de linhas esperadas no CSV:

```csv
ticker,nome,date,open,high,low,close,volume,variacao
PETR4,Petrobras,2026-05-15,38.00,40.00,37.00,39.00,123456,1.20
VALE3,Vale,2026-05-15,60.00,63.00,59.00,62.00,555000,2.50
```

Instale dependencias:

```bash
pip install -r requirements.txt
```

Execute:

```bash
python app.py
```

## iPhone na rede local

No Windows:

```bat
iniciar_iphone.bat
```

Abra no Safari:

```text
http://SEU_IP_LOCAL:5001/iphone
```

## Deploy

Veja:

- `GOOGLE_CLOUD_RUN.md`
- `HOSPEDAGEM_DOMINIO.md`

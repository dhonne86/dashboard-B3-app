# Dashboard B3

Dashboard Flask para monitorar ativos da B3 usando a API da brapi.

## Recursos

- Ativos B3: PETR4, VALE3, ITUB4, BBDC4, ABEV3, WEGE3, BBAS3 e B3SA3.
- Versao desktop e mobile/iPhone.
- Autenticacao HTTP Basic.
- Headers de seguranca.
- Deploy preparado para Google Cloud Run.

## Configuracao local

Crie um arquivo `.env` com base em `.env.example`:

```env
BRAPI_TOKEN=sua_chave_brapi
DASHBOARD_USER=admin
DASHBOARD_PASSWORD=sua_senha_forte
HOST=0.0.0.0
PORT=5000
DEBUG=0
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

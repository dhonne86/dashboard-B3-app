# Deploy no Google Cloud Run

Google Domains foi migrado para Squarespace. Para ficar no ecossistema Google, use:

- Hospedagem: Google Cloud Run
- Dominio: Squarespace Domains ou outro registrador
- DNS/HTTPS: Cloud Run custom domain, Firebase Hosting ou Load Balancer

## Arquivos prontos

- `Dockerfile`: empacota o Flask com Gunicorn.
- `.dockerignore`: evita enviar `.env`, logs e dependencias locais.
- `cloudbuild.yaml`: build/deploy via Cloud Build.
- `deploy_google_cloud.bat`: deploy manual via `gcloud`.

## Variaveis obrigatorias

Configure no Cloud Run:

```env
BRAPI_TOKEN=sua_chave_brapi
DASHBOARD_USER=admin
DASHBOARD_PASSWORD=senha_forte
DEBUG=0
```

O Cloud Run define a variavel `PORT` automaticamente. O app ja usa essa porta.

## Deploy pelo Windows

Instale e autentique o Google Cloud CLI, depois rode:

```bat
set PROJECT_ID=seu-projeto-google
set BRAPI_TOKEN=sua_chave_brapi
set DASHBOARD_PASSWORD=senha_forte
deploy_google_cloud.bat
```

O comando final retorna uma URL parecida com:

```text
https://dashboard-b3-xxxxx-southamerica-east1.run.app
```

## Dominio

Depois do deploy:

1. Abra Cloud Run no Google Cloud Console.
2. Selecione o servico `dashboard-b3`.
3. Va em Custom domains.
4. Adicione seu dominio ou subdominio.
5. Copie os registros DNS que o Google mostrar.
6. Cole esses registros no DNS do registrador do dominio.

Se o dominio veio do antigo Google Domains, ele agora deve ser gerenciado no Squarespace.

# Hospedagem e dominio do Dashboard B3

## Seguranca configurada

- O token da brapi fica em variavel de ambiente: `BRAPI_TOKEN`.
- O dashboard exige usuario e senha via HTTP Basic Auth.
- Headers de seguranca foram ativados no Flask.
- O arquivo `.env` fica local e foi colocado no `.gitignore`.

Credenciais locais atuais:

- Usuario: `admin`
- Senha: `DashB3#2026!nR7`

Troque a senha antes de publicar em producao.

## Variaveis de ambiente para hospedagem

Configure estas variaveis no painel da hospedagem:

```env
BRAPI_TOKEN=sua_chave_brapi
DASHBOARD_USER=admin
DASHBOARD_PASSWORD=uma_senha_forte
DEBUG=0
```

## Comando de producao

Em hospedagem Linux, use:

```bash
gunicorn app:app --bind 0.0.0.0:$PORT
```

## Opcao Google

Para hospedar no Google, use o guia:

```text
GOOGLE_CLOUD_RUN.md
```

O Google Domains foi migrado para Squarespace; portanto, um dominio antigo do Google hoje e gerenciado por la. A hospedagem continua podendo ser feita no Google Cloud Run.

## Dominio

1. Registre um dominio, por exemplo `seudashboard.com.br`.
2. Publique o app em uma hospedagem que aceite Python/Flask.
3. No painel da hospedagem, adicione o dominio customizado.
4. No provedor do dominio, crie os registros DNS indicados pela hospedagem.
5. Ative HTTPS/SSL no painel da hospedagem.

## Teste local

Desktop:

```bash
venv\Scripts\python.exe app.py
```

iPhone na mesma rede Wi-Fi:

```bash
iniciar_iphone.bat
```

Depois abra:

```text
http://192.168.1.170:5001/iphone
```

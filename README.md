# Gauge Metrics API

Backend Python/FastAPI da plataforma Gauge Metrics.

Este repositório substitui gradualmente a camada Streamlit responsável por:

- Conexões Jira
- Validação de token Jira
- Permissões de usuário/admin
- Criptografia de tokens
- Persistência em MongoDB
- APIs de projetos, campos, issues e JQL
- APIs para preview e salvamento de gráficos

## Arquitetura

```text
app/
├── api/
│   ├── jira.py
│   └── charts.py
├── core/
│   ├── config.py
│   └── security.py
├── db/
│   └── mongo.py
├── models/
│   └── schemas.py
├── services/
│   ├── jira_service.py
│   └── chart_service.py
└── main.py
```

## Rodar localmente

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Variáveis de ambiente

Configure localmente um arquivo `.env` com:

```text
MONGO_URI=<sua-uri-mongodb>
MONGO_DB_NAME=dashboard_metrics
SECRET_KEY=<fernet-key>
MASTER_USERS=admin@empresa.com,marcelo@empresa.com
CORS_ORIGINS=http://localhost:3000
```

Para gerar uma chave Fernet:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Observação de migração

A autenticação inicial usa o header `X-User-Email`, apenas para substituir temporariamente o `st.session_state` do Streamlit. O próximo passo é trocar por JWT, SSO ou login próprio.

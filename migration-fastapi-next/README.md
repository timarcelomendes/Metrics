# Migração Streamlit → Python FastAPI + Next.js

Este diretório é uma base inicial para copiar o projeto Streamlit atual para uma arquitetura separada em backend Python e frontend Next.js, preservando o foco em Jira, permissões e construtores de gráficos.

## Objetivo

Separar a aplicação em duas camadas:

- **Backend FastAPI**: autenticação, permissões, criptografia de tokens, MongoDB, conexão Jira, carga de issues, JQL e geração de preview de gráficos.
- **Frontend Next.js**: telas de conexão Jira, seleção de projeto, construtor visual de gráficos e renderização Plotly.

## Escopo preservado do Streamlit

1. **Conexões Jira**
   - Salvar múltiplas conexões por usuário.
   - Criptografar token de API.
   - Ativar/desativar conexão ativa.
   - Validar conexão via Jira antes de salvar/ativar.
   - Listar projetos visíveis ao token ativo.

2. **Permissões**
   - Usuário comum acessa seus próprios dashboards/conexões.
   - Admin/master pode administrar configurações globais.
   - Base preparada para JWT ou SSO futuramente.

3. **Construtor de gráficos**
   - Filtros categóricos, numéricos e de data.
   - Gráfico X-Y.
   - Gráfico agregado.
   - KPI por dados carregados ou JQL.
   - Tabela dinâmica simples.
   - Preview Plotly em JSON.

## Como rodar backend

```bash
cd migration-fastapi-next/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

## Como rodar frontend

```bash
cd migration-fastapi-next/frontend
npm install
npm run dev
```

## Variáveis esperadas

Backend:

```env
MONGO_URI=mongodb+srv://...
MONGO_DB_NAME=dashboard_metrics
SECRET_KEY=<fernet-key>
MASTER_USERS=admin@empresa.com,marcelo@empresa.com
CORS_ORIGINS=http://localhost:3000
```

Frontend:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Observação importante

Esta é uma base de migração incremental. O Streamlit original continua existindo. A recomendação é migrar por módulos: primeiro Jira + permissões, depois dashboard e construtores de gráficos, depois IA/exportações/administração.

# Gauge Metrics Web

Frontend Next.js da plataforma Gauge Metrics.

Este repositório substitui gradualmente a camada visual do Streamlit responsável por:

- Conexões Jira
- Seleção de projeto
- Construtor de gráficos
- Preview Plotly
- Dashboard customizado
- Administração e permissões

## Arquitetura

```text
src/
├── app/
│   ├── page.tsx
│   ├── jira-connections/
│   └── chart-builder/
├── components/
│   └── ChartRenderer.tsx
├── lib/
│   └── api.ts
└── types.ts
```

## Rodar localmente

```bash
npm install
npm run dev
```

## Variáveis de ambiente

```text
NEXT_PUBLIC_API_URL=http://localhost:8000
```

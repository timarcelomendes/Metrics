# Metrics Viewer Lite

Projeto paralelo e simplificado do Metrics, focado **apenas em visualização de dados**.

O projeto original foi mantido intacto na raiz do repositório. Esta versão lite evita dependências de autenticação, integrações Jira, IA, administração, valoração e módulos de forecast, deixando um fluxo direto para carregar dados e explorar gráficos.

## Objetivo

- Carregar um arquivo CSV próprio ou usar dados de exemplo.
- Visualizar indicadores básicos em cards.
- Filtrar dados por período, projeto e responsável.
- Explorar gráficos simples e uma tabela detalhada.

## Como executar

```bash
cd metrics_viewer_lite
pip install -r requirements.txt
streamlit run app.py
```

## Formato esperado do CSV

A aplicação funciona melhor com estas colunas:

| Coluna | Tipo | Obrigatória | Descrição |
| --- | --- | --- | --- |
| `date` | data | Sim | Data do registro. |
| `project` | texto | Não | Projeto, produto ou squad. |
| `owner` | texto | Não | Responsável ou time. |
| `metric` | texto | Não | Nome da métrica. |
| `value` | número | Sim | Valor da métrica. |

Se `project`, `owner` ou `metric` não existirem, a aplicação cria valores padrão para permitir a visualização.

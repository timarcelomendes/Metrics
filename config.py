# config.py

# --- Nomes dos Ficheiros de Configuração ---
CUSTOM_FIELDS_FILE = 'custom_fields.json'
STANDARD_FIELDS_FILE = 'standard_fields_config.json'
STATUS_MAPPING_FILE = 'status_mapping.json'
DASHBOARD_LAYOUT_FILE = 'dashboard_layout.json'

# --- Constantes do Jira ---
# O ID do seu campo de Story Points. Verifique no seu Jira.
STORY_POINTS_FIELD_ID = 'customfield_10016'

# Lista de campos padrão do Jira que podem ser selecionados
AVAILABLE_STANDARD_FIELDS = {
    "Resolução": "resolution",
    "Data de Vencimento": "duedate",
    "Versões Afetadas": "versions",
    "Componentes": "components",
    "Ambiente": "environment",
    "Prioridade": "priority"
}

# --- Constantes de Mapeamento de Status Padrão ---
DEFAULT_INITIAL_STATES = ['to do', 'a fazer', 'backlog', 'aberto', 'novo']
DEFAULT_DONE_STATES = ['done', 'concluído', 'pronto', 'finalizado', 'resolvido']
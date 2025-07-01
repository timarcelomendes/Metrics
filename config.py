# config.py

# Dicionário central de campos padrão do Jira
AVAILABLE_STANDARD_FIELDS = {
    "Resolução": "resolution",
    "Data de Vencimento": "duedate",
    "Versões Afetadas": "versions",
    "Componentes": "components",
    "Ambiente": "environment",
    "Prioridade": "priority"
}

# Nomes dos ficheiros de configuração
CUSTOM_FIELDS_FILE = 'custom_fields.json'
STANDARD_FIELDS_FILE = 'standard_fields_config.json'
STATUS_MAPPING_FILE = 'status_mapping.json'
DASHBOARD_LAYOUT_FILE = 'dashboard_layout.json'

# Mapeamentos de status padrão
DEFAULT_INITIAL_STATES = ['to do', 'a fazer', 'backlog', 'aberto', 'novo']
DEFAULT_DONE_STATES = ['done', 'concluído', 'pronto', 'finalizado', 'resolvido']

# ID do campo personalizado para Story Points
STORY_POINTS_FIELD_ID = 'customfield_10016'
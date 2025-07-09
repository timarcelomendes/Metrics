# config.py

AVAILABLE_STANDARD_FIELDS = {
    "Resolução":        {'id': 'resolution', 'type': 'Texto'},
    "Data de Vencimento": {'id': 'duedate',    'type': 'Data'},
    "Versões Afetadas": {'id': 'versions',   'type': 'Texto'},
    "Componentes":      {'id': 'components', 'type': 'Texto'},
    "Ambiente":         {'id': 'environment','type': 'Texto'},
    "Prioridade":       {'id': 'priority',   'type': 'Texto'}
}
CUSTOM_FIELDS_FILE = 'custom_fields.json'
STANDARD_FIELDS_FILE = 'standard_fields_config.json'
STATUS_MAPPING_FILE = 'status_mapping.json'
DASHBOARD_LAYOUT_FILE = 'dashboard_layout.json'
DEFAULT_INITIAL_STATES = ['to do', 'a fazer', 'backlog', 'aberto', 'novo']
DEFAULT_DONE_STATES = ['done', 'concluído', 'pronto', 'finalizado', 'resolvido']

# A linha abaixo foi removida:
# STORY_POINTS_FIELD_ID = 'customfield_10016'
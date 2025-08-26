# config.py

import streamlit as st
import toml
from pathlib import Path

# --- Constantes Padrão ---
DASHBOARD_CHART_LIMIT = 20
DEFAULT_INITIAL_STATES = ['a fazer', 'to do', 'backlog']
DEFAULT_DONE_STATES = ['concluído', 'done', 'resolvido', 'closed']
DEFAULT_COLORS = {
    'status_colors': {
        'a fazer': '#808080', 'em andamento': '#007bff', 'concluído': '#28a745'
    },
    'type_colors': {
        'bug': '#d73a49', 'melhoria': '#28a745', 'tarefa': '#007bff'
    }
}

# --- Função de Carregamento Central ---
@st.cache_data
def load_app_config():
    """
    Lê o ficheiro de configuração .streamlit/config.toml e retorna um dicionário,
    usando os valores padrão como fallback.
    """
    try:
        config_path = Path(".streamlit/config.toml")
        if config_path.is_file():
            config_data = toml.load(config_path)
            # Junta as configurações padrão com as do ficheiro para garantir que todas as chaves existem
            final_config = DEFAULT_COLORS.copy()
            final_config.update(config_data)
            return final_config
    except Exception as e:
        print(f"Erro ao ler config.toml: {e}")
    # Retorna os padrões se o ficheiro não for encontrado ou se houver um erro
    return DEFAULT_COLORS

# --- Funções Auxiliares para Aceder às Cores ---
def get_status_color_mapping():
    """Retorna o mapeamento de cores para os status, lendo da configuração."""
    configs = st.session_state.get('global_configs', {})
    return configs.get('status_colors', DEFAULT_COLORS['status_colors'])

def get_type_color_mapping():
    """Retorna o mapeamento de cores para os tipos, lendo da configuração."""
    configs = st.session_state.get('global_configs', {})
    return configs.get('type_colors', DEFAULT_COLORS['type_colors'])
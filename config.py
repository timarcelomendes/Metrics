# config.py

import streamlit as st
import toml
from pathlib import Path
import plotly.express as px

# --- Configurações da Aplicação ---
APP_VERSION = "1.5.0"
SESSION_TIMEOUT_MINUTES = 60
DASHBOARD_CHART_LIMIT = 20

# --- Constantes de Estado Padrão ---
DEFAULT_INITIAL_STATES = ['Aberto', 'A Fazer', 'Backlog', 'To Do', 'Open']
DEFAULT_DONE_STATES = ['Concluído', 'Fechado', 'Resolvido', 'Done', 'Closed', 'Resolved']
DEFAULT_COLORS = {
    "status_colors": {
        "Aberto": "#FF5733",       # Vermelho
        "A Fazer": "#FFC300",      # Amarelo
        "Em Progresso": "#33C1FF", # Azul
        "Concluído": "#28A745",    # Verde
        "Fechado": "#6C757D",      # Cinza
        "Resolvido": "#17A2B8",    # Ciano
        "Reaberto": "#FF33A8"      # Rosa
    },
    "type_colors": {
        "Bug": "#E74C3C",          # Vermelho Escuro
        "Tarefa": "#3498DB",       # Azul
        "Melhoria": "#2ECC71",     # Verde
        "História": "#9B59B6",     # Roxo
        "Épico": "#F39C12"         # Laranja
    }
}
# --- Esquemas de Cores para Gráficos ---
COLOR_THEMES = {
    "Padrão Gauge": {
        "primary_color": "#0068C9",    # Azul Gauge
        "secondary_color": "#83C9FF",  # Azul Claro
        "title_color": "#3D3D3D",      # Cinza Escuro
        "color_sequence": ["#0068C9", "#83C9FF", "#0A2943", "#FF4B4B", "#3D3D3D"]
    },
    "Oceano Profundo": {
        "primary_color": "#0A2943",    # Azul Escuro
        "secondary_color": "#0068C9",  # Azul Médio
        "title_color": "#E0E0E0",      # Cinza Claro
        "color_sequence": ["#0A2943", "#0068C9", "#83C9FF", "#FF4B4B", "#3D3D3D"]
    },
    "Vulcão": {
        "primary_color": "#E24E42",    # Vermelho Principal
        "secondary_color": "#FF9B54",  # Laranja
        "title_color": "#4F4A45",      # Cinza Escuro
        "color_sequence": ["#E24E42", "#FF9B54", "#4F4A45", "#C84B31", "#2D2424"]
    },
    "Floresta": {
        "primary_color": "#2E7D32",    # Verde Escuro
        "secondary_color": "#66BB6A",  # Verde Claro
        "title_color": "#3E2723",      # Marrom Escuro
        "color_sequence": ["#2E7D32", "#66BB6A", "#AED581", "#4CAF50", "#81C784"]
    },
    "Pôr do Sol": {
        "primary_color": "#FF8F00",    # Laranja Escuro
        "secondary_color": "#FFCA28",  # Amarelo
        "title_color": "#D84315",      # Laranja Queimado
        "color_sequence": ["#FF8F00", "#FFCA28", "#FFA726", "#FF7043", "#F57C00"]
    }
}

# --- Constantes Padrão ---
DEFAULT_INITIAL_STATES = ['a fazer', 'to do', 'backlog']
DEFAULT_DONE_STATES = ['concluído', 'done', 'resolvido', 'closed']


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
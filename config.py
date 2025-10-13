# config.py

import streamlit as st
import toml
from pathlib import Path
import plotly.express as px

# --- Parâmetro de Timeout da Sessão ---
SESSION_TIMEOUT_MINUTES = 30

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

# --- Esquemas de Cores para Gráficos ---
COLOR_THEMES = {
    "Padrão Gauge": ["#FF4B4B", "#3D3D3D", "#FFD700", "#6A5ACD", "#20B2AA", "#FF69B4", "#ADD8E6", "#F0E68C"],
    "Azuis e Cinzas": px.colors.sequential.Blues_r + px.colors.sequential.Greys_r,
    "Verdes e Amarelos": px.colors.sequential.YlGn_r,
    "Espectro de Cores Vivas": px.colors.qualitative.Plotly,
    "Pastel": px.colors.qualitative.Pastel,
    "Alto Contraste": px.colors.qualitative.Bold,
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
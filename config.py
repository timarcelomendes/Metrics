# config.py

import streamlit as st
import toml
from pathlib import Path
import plotly.express as px

# --- CONFIGURAÇÃO DA BASE DE DADOS E MASTER USER (lido a partir de secrets.toml) ---
MONGO_URI = st.secrets["connections"]["mongodb_uri"]
DB_NAME = "gauge_metrics"
MASTER_USERS = st.secrets["app_settings"]["MASTER_USERS"]

# --- Configurações da Aplicação ---
APP_VERSION = "1.5.0"
SESSION_TIMEOUT_MINUTES = 60
DASHBOARD_CHART_LIMIT = 20

# --- Constantes de Estado Padrão ---
DEFAULT_INITIAL_STATES = ['Aberto', 'A Fazer', 'Backlog', 'To Do', 'Open']
DEFAULT_DONE_STATES = ['Concluído', 'Fechado', 'Resolvido', 'Done', 'Closed', 'Resolved']
DEFAULT_COLORS = {
    "status_colors": {
        "Aberto": "#FF5733",
        "A Fazer": "#FFC300",
        "Em Progresso": "#33C1FF",
        "Concluído": "#28A745",
        "Fechado": "#6C757D",
        "Resolvido": "#17A2B8",
        "Reaberto": "#FF33A8"
    },
    "type_colors": {
        "Bug": "#E74C3C",
        "Tarefa": "#3498DB",
        "Melhoria": "#2ECC71",
        "História": "#9B59B6",
        "Épico": "#F39C12"
    }
}
# --- Esquemas de Cores para Gráficos ---
COLOR_THEMES = {
    "Padrão Gauge": {
        "primary_color": "#0068C9", "secondary_color": "#83C9FF", "title_color": "#3D3D3D",
        "color_sequence": ["#0068C9", "#83C9FF", "#0A2943", "#FF4B4B", "#3D3D3D"]
    },
    # Adicione outros temas aqui se necessário
}

# --- Funções Auxiliares ---
@st.cache_data
def load_app_config():
    try:
        config_path = Path(".streamlit/config.toml")
        if config_path.is_file():
            config_data = toml.load(config_path)
            final_config = DEFAULT_COLORS.copy()
            final_config.update(config_data)
            return final_config
    except Exception as e:
        print(f"Erro ao ler config.toml: {e}")
    return DEFAULT_COLORS

def get_status_color_mapping():
    configs = st.session_state.get('global_configs', {})
    return configs.get('status_colors', DEFAULT_COLORS['status_colors'])

def get_type_color_mapping():
    configs = st.session_state.get('global_configs', {})
    return configs.get('type_colors', DEFAULT_COLORS['type_colors'])
# config.py

import streamlit as st
import toml
from pathlib import Path
import plotly.express as px

# --- CONFIGURAÇÃO DA BASE DE DADOS E MASTER USER (lido a partir de secrets.toml) ---
MONGO_URI = st.secrets.get("connections", {}).get("mongodb_uri")
DB_NAME = "gauge_metrics"
MASTER_USERS = st.secrets.get("app_settings", {}).get("MASTER_USERS", [])

if not MONGO_URI:
    st.error("MONGO_URI não encontrado em secrets.toml [connections].")
if not MASTER_USERS:
    st.warning("MASTER_USERS não encontrado ou vazio em secrets.toml [app_settings].")


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
        "primary_color": "#0068C9",
        "secondary_color": "#83C9FF",
        "title_color": "#3D3D3D",
        "color_sequence": ["#0068C9", "#83C9FF", "#0A2943", "#FF4B4B", "#3D3D3D", "#FFB400", "#FF7F0E", "#1F77B4"]
    },
    "Tons de Verde": {
        "primary_color": "#28a745",
        "secondary_color": "#8fbc8f",
        "title_color": "#2F4F4F",
        "color_sequence": ["#2E8B57", "#3CB371", "#8FBC8F", "#98FB98", "#20B2AA", "#66CDAA", "#00FA9A", "#008080"]
    },
    "Oceano Profundo": {
        "primary_color": "#1f77b4",
        "secondary_color": "#aec7e8",
        "title_color": "#0A2943",
        "color_sequence": ["#17becf", "#1f77b4", "#7f7f7f", "#aec7e8", "#ff7f0e", "#ffbb78", "#2ca02c", "#98df8a"]
    },
    "Vibrante (Plotly)": {
        "primary_color": "#636EFA",
        "secondary_color": "#AB63FA",
        "title_color": "#1A1A1A",
        "color_sequence": px.colors.qualitative.Plotly
    },
    "Entardecer": {
        "primary_color": "#EF553B",
        "secondary_color": "#FFA15A",
        "title_color": "#444444",
        "color_sequence": ["#EF553B", "#FFA15A", "#00CC96", "#AB63FA", "#FECB52", "#FF6692", "#B6E880", "#FF97FF"]
    },
    "Monocromático Azul": {
        "primary_color": "#0d6efd",
        "secondary_color": "#6c757d",
        "title_color": "#212529",
        "color_sequence": px.colors.sequential.Blues_r
    },
}

# --- Funções Auxiliares ---
@st.cache_data
def load_app_config():
    """Lê configurações de cores de um arquivo TOML, se existir."""
    try:
        config_path = Path(".streamlit/config.toml")
        if config_path.is_file():
            config_data = toml.load(config_path)
            # Funde com defaults, dando prioridade ao que está no toml
            final_config = DEFAULT_COLORS.copy()
            final_config.update(config_data.get("colors", {})) # Assume que cores estão sob [colors] no toml
            return final_config
    except Exception as e:
        print(f"Erro ao ler config.toml: {e}")
    return DEFAULT_COLORS

# MANTIDO: Função para facilitar o acesso ao tema selecionado
def get_selected_color_theme(theme_name="Padrão Gauge"):
    """Retorna o dicionário de cores para o tema especificado ou o padrão."""
    return COLOR_THEMES.get(theme_name, COLOR_THEMES["Padrão Gauge"])
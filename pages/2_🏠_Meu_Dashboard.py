# pages/2_🏠_Meu_Dashboard.py

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import uuid
import json
from jira_connector import *
from metrics_calculator import *
from config import *
from utils import *
from security import *
from pathlib import Path
import importlib
import jira_connector
from datetime import datetime, timedelta

st.set_page_config(page_title="Meu Dashboard", page_icon="🏠", layout="wide")

# --- CABEÇALHO E CONTROLES ---
st.header(f"🏠 Meu Dashboard: {st.session_state.get('project_name', 'Bem-vindo')}", divider='rainbow')

# --- Bloco de Autenticação e Conexão ---
if 'email' not in st.session_state:
    st.warning("⚠️ Por favor, faça login para acessar."); 
    st.page_link("1_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑"); 
    st.stop()

if check_session_timeout():
    st.warning(f"Sua sessão expirou por inatividade de {SESSION_TIMEOUT_MINUTES} minutos. Por favor, faça login novamente.")
    st.page_link("1_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑")
    st.stop()
    
if 'jira_client' not in st.session_state:
    user_connections = get_user_connections(st.session_state['email'])
    
    if not user_connections:
        st.warning("Nenhuma conexão Jira foi configurada ainda.", icon="🔌")
        st.info("Para começar, você precisa de adicionar as suas credenciais do Jira.")
        st.page_link("pages/8_🔗_Conexões_Jira.py", label="Configurar sua Primeira Conexão", icon="🔗")
        st.stop()
    else:
        st.warning("Nenhuma conexão Jira está ativa para esta sessão.", icon="⚡")
        st.info("Por favor, ative uma das suas conexões guardadas para carregar os dados.")
        st.page_link("pages/8_🔗_Conexões_Jira.py", label="Ativar uma Conexão", icon="🔗")
        st.stop()

st.markdown("""
<style>
/* Alinha os itens nos controlos do cabeçalho verticalmente ao centro */
[data-testid="stHorizontalBlock"] {
    align-items: center;
}
/* Aumenta o espaço entre os gráficos */
div[data-testid="stVerticalBlock"] div[data-testid="stVerticalBlock"] {
    gap: 1.5rem; 
}
/* Estilo para o 'empty state' */
#empty-state-container {
    text-align: center;
    padding: 3rem;
    background-color: #f8f9fa;
    border-radius: 0.5rem;
}
#empty-state-container .icon {
    font-size: 4rem;
}

/* --- REGRAS PARA BOTÕES QUADRADOS E COMPACTOS --- */
div[data-testid="stAppViewContainer"] div[data-testid="stContainer"] > div[data-testid="stVerticalBlock"] div[data-testid="stButton"] > button {
    background-color: transparent;
    border: none;
    color: #4a4a4a;
    width: 35px;  /* Largura fixa */
    height: 35px; /* Altura fixa para criar um quadrado */
    padding: 0;
    margin: 0;
    display: flex;
    align-items: center;
    justify-content: center;
}
div[data-testid="stAppViewContainer"] div[data-testid="stContainer"] > div[data-testid="stVerticalBlock"] div[data-testid="stButton"] > button:hover {
    background-color: #f0f2f6;
    color: #1c1c1c;
    border-radius: 0.25rem;
}
div[data-testid="stAppViewContainer"] div[data-testid="stContainer"] > div[data-testid="stVerticalBlock"] div[data-testid="stButton"] > button:focus {
    box-shadow: none !important;
    outline: none !important;
}
</style>
""", unsafe_allow_html=True)

def on_project_change():
    if 'dynamic_df' in st.session_state: st.session_state.pop('dynamic_df', None)
    if 'loaded_project_key' in st.session_state: st.session_state.pop('loaded_project_key', None)

def on_layout_change():
    num_cols = st.session_state.dashboard_layout_radio
    save_dashboard_column_preference(st.session_state.project_key, num_cols)

def move_item(items_list, from_index, to_index):
    if 0 <= from_index < len(items_list) and 0 <= to_index < len(items_list):
        item = items_list.pop(from_index)
        items_list.insert(to_index, item)
    return items_list

# --- BARRA LATERAL ---
with st.sidebar:
    project_root = Path(__file__).parent.parent
    logo_path = project_root / "images" / "gauge-logo.svg"
    try:
        st.logo(str(logo_path), size="large")
    except (FileNotFoundError, AttributeError):
        st.write("Gauge Metrics") 

    st.markdown(f"Logado como: **{st.session_state.get('email', '')}**")
    st.divider()
    st.header("Fonte de Dados")
    projects = st.session_state.get('projects', {})
    project_names = list(projects.keys())
    
    last_project_key = find_user(st.session_state['email']).get('last_project_key')
    default_index = project_names.index(next((name for name, key in projects.items() if key == last_project_key), None)) if last_project_key and projects else 0
    
    selected_project_name = st.selectbox("Selecione um Projeto", options=project_names, key="project_selector_dashboard", index=default_index, on_change=on_project_change, placeholder="Escolha um projeto...")
    
    if selected_project_name:
        if st.button("Visualizar Dashboard", width='stretch', type="primary"):
            importlib.reload(jira_connector)
            project_key = projects[selected_project_name]
            save_last_project(st.session_state['email'], project_key)
            st.session_state.project_key = project_key
            st.session_state.project_name = selected_project_name
            
            df = jira_connector.load_and_process_project_data(st.session_state.jira_client, project_key)
            st.session_state.dynamic_df = df
            st.session_state.loaded_project_key = project_key
            st.rerun()
    
    st.divider()
    if st.button("Logout", width='stretch', type='secondary'):
        # Guarda o valor de 'remember_email' antes de limpar a sessão
        email_to_remember = st.session_state.get('remember_email', '')
        
        # Limpa todas as chaves da sessão
        for key in list(st.session_state.keys()):
            del st.session_state[key]
            
        # Restaura a chave 'remember_email' se ela existia
        if email_to_remember:
            st.session_state['remember_email'] = email_to_remember
            
        st.switch_page("1_🔑_Autenticação.py")

# --- LÓGICA PRINCIPAL DA PÁGINA ---
df = st.session_state.get('dynamic_df')
current_project_key = st.session_state.get('project_key')

if df is None or not st.session_state.get('project_name'):
    st.info("⬅️ Na barra lateral, selecione um projeto e clique em 'Visualizar Dashboard' para carregar os dados.")
    st.stop()

# --- Carregamento e Preparação das Configurações ---
user_data = find_user(st.session_state['email']); all_layouts = user_data.get('dashboard_layout', {})
project_layouts = all_layouts.get(current_project_key, {})
available_dashboards = project_layouts.get('dashboards', {})
if not available_dashboards:
    available_dashboards["main"] = {"id": "main", "name": "Dashboard Principal", "tabs": {"Geral": []}}
    project_layouts['dashboards'] = available_dashboards
    project_layouts['active_dashboard_id'] = "main"

active_dashboard_id = project_layouts.get('active_dashboard_id')
active_dashboard_config = available_dashboards.get(active_dashboard_id, {"tabs": {"Geral": []}})
tabs_layout = active_dashboard_config.get('tabs', {"Geral": []})
project_config = get_project_config(current_project_key) or {}
default_cols = project_config.get('dashboard_columns', 2)
active_dashboard_name = active_dashboard_config.get('name', 'Dashboard')
all_charts = [chart for tab_charts in tabs_layout.values() for chart in tab_charts]

cols = st.columns([2.5, 1.5, 1.5, 1.5, 1.5])

with cols[0]:
    dashboard_names = {db['name']: db['id'] for db_id, db in available_dashboards.items()}
    selected_dashboard_name = st.selectbox(
        "Visualizar Dashboard:",
        options=dashboard_names.keys(),
        index=list(dashboard_names.keys()).index(active_dashboard_name) if active_dashboard_name in dashboard_names else 0,
        label_visibility="collapsed"
    )
    selected_dashboard_id = dashboard_names.get(selected_dashboard_name)
    if selected_dashboard_id != active_dashboard_id:
        project_layouts['active_dashboard_id'] = selected_dashboard_id
        all_layouts[current_project_key] = project_layouts
        save_user_dashboard(st.session_state['email'], all_layouts); st.rerun()

with cols[1]:
    st.radio(
        "Layout em Colunas", [1, 2], 
        index=(1 if default_cols == 2 else 0), 
        horizontal=True, 
        key="dashboard_layout_radio",
        on_change=on_layout_change
    )

with cols[2]:
    organize_mode = st.toggle("Organizar", help="Ative para gerir dashboards e abas.")

with cols[3]:
    if st.button("🤖 Análise AI", help="Gerar análise do dashboard com IA", width='stretch'):
        with st.spinner("A Gauge AI está a analisar os dados de todos os gráficos..."):
            summaries = [summarize_chart_data(c, df) for c in all_charts]
            provider = user_data.get('ai_provider_preference', 'Google Gemini')
            insights = get_ai_insights(st.session_state.project_name, summaries, provider)
            st.session_state.ai_dashboard_insights = insights

with cols[4]:
    if st.button("➕ Gráfico", width='stretch', type="primary"):
        st.switch_page("pages/5_🏗️_Construir Gráficos.py")

st.divider()

if 'ai_dashboard_insights' in st.session_state and st.session_state.ai_dashboard_insights:
    with st.expander("🤖 Análise da Gauge AI para o Dashboard", expanded=True):
        st.markdown(st.session_state.ai_dashboard_insights)
        if st.button("Fechar Análise", key="close_ai_insights"):
            del st.session_state.ai_dashboard_insights
            st.rerun()

# ===== FILTROS GLOBAIS =====
with st.expander("Filtros do Dashboard (afetam todas as visualizações)", expanded=False):
    global_configs = st.session_state.get('global_configs', {})
    all_std_fields = global_configs.get('available_standard_fields', {})
    name_for_issuetype = next((name for name, conf in all_std_fields.items() if conf.get('id') == 'issuetype'), 'Tipo de Issue')
    name_for_assignee = next((name for name, conf in all_std_fields.items() if conf.get('id') == 'assignee'), 'Responsável')
    name_for_status = next((name for name, conf in all_std_fields.items() if conf.get('id') == 'status'), 'Status')
    name_for_priority = next((name for name, conf in all_std_fields.items() if conf.get('id') == 'priority'), 'Prioridade')
    
    filter_fields_to_display = [name_for_issuetype, name_for_assignee, name_for_status, name_for_priority]
    filter_cols = st.columns(len(filter_fields_to_display))
    selections = {}

    for i, field_name in enumerate(filter_fields_to_display):
        has_field = field_name in df.columns
        options = sorted(df[field_name].dropna().unique()) if has_field else []
        selections[field_name] = filter_cols[i].multiselect(f"Filtrar por {field_name}", options=options, placeholder="Todos", disabled=not has_field)
    
    filtered_df = df.copy()
    for field_name, selected_values in selections.items():
        if selected_values:
            filtered_df = filtered_df[filtered_df[field_name].isin(selected_values)]

# --- INTERFACE DE ORGANIZAÇÃO OU VISUALIZAÇÃO ---
if organize_mode:
    st.subheader("🛠️ Modo de Organização")
    
    # --- 1. GESTÃO DE DASHBOARDS ---
    st.markdown("**1. Gerir Dashboards**")
    with st.container(border=True):
        d_col1, d_col2 = st.columns(2)
        with d_col1:
            with st.form("new_dashboard_form"):
                new_dashboard_name = st.text_input("Nome do Novo Dashboard")
                if st.form_submit_button("➕ Criar Novo Dashboard", width='stretch'):
                    if new_dashboard_name:
                        new_id = str(uuid.uuid4())
                        layouts = find_user(st.session_state['email']).get('dashboard_layout', {})
                        proj_layouts = layouts.get(current_project_key, {})
                        if 'dashboards' not in proj_layouts: proj_layouts['dashboards'] = {}
                        proj_layouts['dashboards'][new_id] = {"id": new_id, "name": new_dashboard_name, "tabs": {"Geral": []}}
                        proj_layouts['active_dashboard_id'] = new_id
                        layouts[current_project_key] = proj_layouts
                        save_user_dashboard(st.session_state['email'], layouts)
                        st.success(f"Dashboard '{new_dashboard_name}' criado!")
                        st.rerun()

        with d_col2:
            with st.form("rename_dashboard_form"):
                renamed_dashboard_name = st.text_input("Renomear Dashboard Atual", value=active_dashboard_name)
                if st.form_submit_button("✏️ Renomear", width='stretch'):
                    if renamed_dashboard_name:
                        layouts = find_user(st.session_state['email']).get('dashboard_layout', {})
                        layouts[current_project_key]['dashboards'][active_dashboard_id]['name'] = renamed_dashboard_name
                        save_user_dashboard(st.session_state['email'], layouts)
                        st.success("Dashboard renomeado!")
                        st.rerun()
        
        st.divider()
        if len(available_dashboards) > 1:
            if st.button("❌ Apagar Dashboard Atual", width='stretch', type="secondary"):
                layouts = find_user(st.session_state['email']).get('dashboard_layout', {})
                del layouts[current_project_key]['dashboards'][active_dashboard_id]
                layouts[current_project_key]['active_dashboard_id'] = next(iter(layouts[current_project_key]['dashboards']))
                save_user_dashboard(st.session_state['email'], layouts)
                st.success("Dashboard apagado!")
                st.rerun()
        else:
            st.button("❌ Apagar Dashboard Atual", width='stretch', disabled=True, help="Não pode apagar o seu último dashboard.")

    with st.container(border=True):
        st.markdown("**2. Gerir Abas e Gráficos do Dashboard Atual**")
        
        st.markdown("###### Gerir Abas")
        tab_names = list(tabs_layout.keys())

        for i, tab_name in enumerate(tab_names):
            cols = st.columns([0.7, 0.1, 0.1, 0.1])
            new_name = cols[0].text_input("Nome da Aba", value=tab_name, key=f"tab_name_{i}")
            
            if cols[1].button("🔼", key=f"up_tab_{i}", help="Mover para cima", width='stretch', disabled=(i == 0)):
                current_items = list(tabs_layout.items())
                moved_items = move_item(current_items, i, i - 1)
                project_layouts['dashboards'][active_dashboard_id]['tabs'] = dict(moved_items)
                all_layouts[current_project_key] = project_layouts
                save_user_dashboard(st.session_state['email'], all_layouts)
                st.rerun()

            if cols[2].button("🔽", key=f"down_tab_{i}", help="Mover para baixo", width='stretch', disabled=(i == len(tab_names) - 1)):
                current_items = list(tabs_layout.items())
                moved_items = move_item(current_items, i, i + 1)
                project_layouts['dashboards'][active_dashboard_id]['tabs'] = dict(moved_items)
                all_layouts[current_project_key] = project_layouts
                save_user_dashboard(st.session_state['email'], all_layouts)
                st.rerun()

            if cols[3].button("❌", key=f"del_tab_{i}", help="Apagar aba", width='stretch', disabled=(len(tab_names) <= 1)):
                if tab_name in tabs_layout:
                    charts_to_move = tabs_layout.pop(tab_name)
                    first_tab_name = next(iter(tabs_layout))
                    tabs_layout[first_tab_name].extend(charts_to_move)
                    
                    project_layouts['dashboards'][active_dashboard_id]['tabs'] = tabs_layout
                    all_layouts[current_project_key] = project_layouts
                    save_user_dashboard(st.session_state['email'], all_layouts)
                    st.rerun()
            
            if new_name != tab_name:
                items = list(tabs_layout.items())
                items[i] = (new_name, items[i][1])
                tabs_layout = dict(items)
                st.session_state.updated_tabs_layout = tabs_layout

        if st.button("➕ Adicionar Nova Aba", width='stretch'):
            new_tab_name = f"Nova Aba {len(tab_names) + 1}"
            tabs_layout[new_tab_name] = []
            project_layouts['dashboards'][active_dashboard_id]['tabs'] = tabs_layout
            all_layouts[current_project_key] = project_layouts
            save_user_dashboard(st.session_state['email'], all_layouts)
            st.rerun()
        
        st.divider()
        st.markdown("###### Atribuir Gráficos às Abas")
        if not all_charts:
            st.info("Nenhum gráfico neste dashboard. Adicione um para começar a organizar.")
        else:
            updated_chart_assignments = {}
            for chart in all_charts:
                chart_id = chart['id']
                current_tab = next((tab for tab, charts in tabs_layout.items() if chart_id in [c['id'] for c in charts]), None)
                
                tab_options = tab_names
                
                if current_tab and current_tab not in tab_options:
                    tab_options.insert(0, current_tab)

                default_index = tab_options.index(current_tab) if current_tab in tab_options else 0
                
                cols = st.columns([3, 2])
                cols[0].write(f"📊 {chart.get('title', 'Gráfico sem título')}")
                new_tab = cols[1].selectbox(
                    "Mover para a aba:",
                    options=tab_options,
                    index=default_index,
                    key=f"select_tab_{chart_id}"
                )
                updated_chart_assignments[chart_id] = new_tab

        st.divider()
        if st.button("Salvar Alterações de Organização", type="primary", width='stretch'):
            if 'updated_tabs_layout' in st.session_state:
                tabs_layout = st.session_state.pop('updated_tabs_layout')

            new_tabs_layout = {name: [] for name in tabs_layout.keys()}
            
            for chart in all_charts:
                assigned_tab = updated_chart_assignments.get(chart['id'])
                if assigned_tab in new_tabs_layout:
                    new_tabs_layout[assigned_tab].append(chart)
            
            project_layouts['dashboards'][active_dashboard_id]['tabs'] = new_tabs_layout
            all_layouts[current_project_key] = project_layouts
            save_user_dashboard(st.session_state['email'], all_layouts)
            st.success("Organização do dashboard salva com sucesso!")
            st.rerun()

else:
    tabs_with_charts = {name: charts for name, charts in tabs_layout.items() if charts}
    
    if not any(tabs_with_charts.values()):
        st.markdown("""<div id="empty-state-container">...</div>""", unsafe_allow_html=True)
        if st.button("➕ Adicionar seu primeiro gráfico", type="primary"):
            st.switch_page("pages/5_🏗️_Construir Gráficos.py")
    else:
        tab_names = list(tabs_with_charts.keys())
        st_tabs = st.tabs(tab_names)
        for i, tab_name in enumerate(tab_names):
            with st_tabs[i]:
                dashboard_items_in_tab = tabs_with_charts[tab_name]
                cols = st.columns(default_cols, gap="large")
                for j, chart_to_render in enumerate(dashboard_items_in_tab):
                    with cols[j % default_cols]:
                        with st.container(border=True):
                            
                            header_cols = st.columns([0.6, 0.1, 0.1, 0.1, 0.1])
                            
                            if chart_to_render.get('type') != 'indicator':
                                with header_cols[0]:
                                    st.markdown(f"**{chart_to_render.get('icon', '📊')} {chart_to_render.get('title', 'Visualização')}**")
                            
                            # A lógica dos botões agora usa header_cols, que sempre existe
                            with header_cols[1]:
                                if st.button("🔼", key=f"up_{chart_to_render['id']}", help="Mover para cima", width='stretch', disabled=(j == 0)):
                                    new_order = move_item(dashboard_items_in_tab, j, j - 1)
                                    tabs_layout[tab_name] = new_order
                                    all_layouts[current_project_key]['dashboards'][active_dashboard_id]['tabs'] = tabs_layout
                                    save_user_dashboard(st.session_state['email'], all_layouts)
                                    st.rerun()

                            with header_cols[2]:
                                if st.button("🔽", key=f"down_{chart_to_render['id']}", help="Mover para baixo", width='stretch', disabled=(j == len(dashboard_items_in_tab) - 1)):
                                    new_order = move_item(dashboard_items_in_tab, j, j + 1)
                                    tabs_layout[tab_name] = new_order
                                    all_layouts[current_project_key]['dashboards'][active_dashboard_id]['tabs'] = tabs_layout
                                    save_user_dashboard(st.session_state['email'], all_layouts)
                                    st.rerun()
                            
                            with header_cols[3]:
                                if st.button("✏️", key=f"edit_{chart_to_render['id']}", help="Editar Gráfico", width='stretch'):
                                    st.session_state['chart_to_edit'] = chart_to_render; st.switch_page("pages/5_🏗️_Construir Gráficos.py")
                            
                            with header_cols[4]:
                                if st.button("❌", key=f"del_{chart_to_render['id']}", help="Remover Gráfico", width='stretch'):
                                    tabs_layout[tab_name] = [item for item in dashboard_items_in_tab if item['id'] != chart_to_render['id']]
                                    all_layouts[current_project_key]['dashboards'][active_dashboard_id]['tabs'] = tabs_layout
                                    save_user_dashboard(st.session_state['email'], all_layouts)
                                    st.rerun()
                            
                            render_chart(chart_to_render, filtered_df)
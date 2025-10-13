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

# Determina se estamos em modo de edição e obtém os dados do gráfico
editing_mode = 'chart_to_edit' in st.session_state and st.session_state.chart_to_edit is not None
chart_data = st.session_state.get('chart_to_edit', {})

if editing_mode:
    # Se o estado principal ('new_chart_config') ainda não foi populado com os dados de edição, faz a cópia.
    if 'new_chart_config' not in st.session_state or st.session_state.new_chart_config.get('id') != chart_data.get('id'):
        st.session_state.new_chart_config = chart_data.copy()
    
    # Se o estado dos filtros ('creator_filters') não foi populado, carrega-o a partir do gráfico.
    if 'creator_filters' not in st.session_state or not st.session_state.creator_filters:
        st.session_state.creator_filters = parse_dates_in_filters(chart_data.get('filters', []))
else:
    # Se estiver a criar um novo gráfico, garante que ambos os estados começam vazios.
    st.session_state.new_chart_config = {}
    st.session_state.creator_filters = []

# Define o cabeçalho da página com base no modo (usando o estado agora correto)
if editing_mode:
    st.header(f"✏️ Editando: {st.session_state.new_chart_config.get('title', 'Visualização')}", divider='orange')
else:
    st.header("🏗️ Laboratório de Criação de Gráficos", divider='rainbow')

# Verificações de segurança e sessão (sem alterações)
if 'email' not in st.session_state:
    st.warning("⚠️ Por favor, faça login para acessar."); st.page_link("1_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑"); st.stop()
if check_session_timeout():
    st.warning(f"Sua sessão expirou por inatividade de {SESSION_TIMEOUT_MINUTES} minutos. Por favor, faça login novamente.")
    st.page_link("1_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑"); st.stop()
if 'jira_client' not in st.session_state:
    st.warning("Nenhuma conexão Jira está ativa para esta sessão.", icon="⚡")
    st.info("Por favor, ative uma das suas conexões guardadas para carregar os dados.")
    st.page_link("pages/8_🔗_Conexões_Jira.py", label="Ativar uma Conexão", icon="🔗")
    st.stop()

# --- BLOCO 2: DEFINIÇÃO DE TODAS AS FUNÇÕES AUXILIARES E CALLBACKS ---

def is_valid_chart(item):
    """Verifica se um item é um dicionário e se contém as chaves essenciais 'id' e 'title'."""
    return isinstance(item, dict) and 'id' in item and 'title' in item

def ensure_project_data_is_loaded():
    """Garante que o DataFrame do projeto está carregado na sessão."""
    if 'dynamic_df' not in st.session_state or st.session_state.get('dynamic_df') is None:
        project_key = st.session_state.get('project_key')
        if project_key and 'jira_client' in st.session_state:
            df = jira_connector.load_and_process_project_data(st.session_state.jira_client, project_key)
            st.session_state.dynamic_df = df
            st.session_state.loaded_project_key = project_key

def add_chart_callback():
    """Prepara o estado para criar um novo gráfico e navega para a página de construção."""
    
    # ----> ADICIONE ESTA LINHA <----
    print("\n--- DEBUG: INÍCIO DO FLUXO 'ADICIONAR GRÁFICO' ---")
    print("[DASHBOARD - PASSO 1/2] A função 'add_chart_callback' foi chamada com sucesso.")
    
    # Limpa qualquer estado antigo para garantir uma página de criação limpa
    keys_to_clear = ['chart_to_edit', 'creator_filters', 'chart_config_ia', 'new_chart_config']
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
            print(f"   > Chave de sessão limpa: {key}") # Print opcional para mais detalhes
    
    ensure_project_data_is_loaded()
    
    # ----> ADICIONE ESTA LINHA <----
    print("[DASHBOARD - PASSO 2/2] Estado limpo. Prestes a chamar st.switch_page para 'Construir Gráficos'.")
    
    st.switch_page("pages/5_🏗️_Construir Gráficos.py")

def edit_chart_callback(chart_config):
    print("\n--- DEBUG: INÍCIO DO FLUXO 'EDITAR GRÁFICO' ---")
    print(f"[DASHBOARD] A função 'edit_chart_callback' foi chamada para o gráfico: '{chart_config.get('title')}'")
    st.session_state['chart_to_edit'] = chart_config
    print(f"[DASHBOARD] A variável 'chart_to_edit' foi definida na sessão.")
    print("--------------------------------------------------")
    ensure_project_data_is_loaded()
    st.switch_page("pages/5_🏗️_Construir Gráficos.py")

def remove_chart_callback(chart_id, tab_name, project_key, all_layouts):
    """Executa a remoção e SINALIZA que a página precisa ser reexecutada."""
    user_email = st.session_state['email']
    active_dashboard_id = all_layouts.get(project_key, {}).get('active_dashboard_id')
    if active_dashboard_id:
        tabs = all_layouts[project_key]['dashboards'][active_dashboard_id]['tabs']
        if tab_name in tabs:
            tabs[tab_name] = [chart for chart in tabs[tab_name] if chart.get('id') != chart_id]
            save_user_dashboard(user_email, all_layouts)
            st.success("Gráfico removido!")
            st.session_state.needs_rerun = True

def move_chart_callback(charts_list, tab_name, from_index, to_index, project_key, all_layouts):
    """Executa o movimento e SINALIZA que a página precisa ser reexecutada."""
    item = charts_list.pop(from_index)
    charts_list.insert(to_index, item)
    active_dashboard_id = all_layouts.get(project_key, {}).get('active_dashboard_id')
    if active_dashboard_id:
        tabs = all_layouts[project_key]['dashboards'][active_dashboard_id]['tabs']
        tabs[tab_name] = charts_list
        save_user_dashboard(st.session_state['email'], all_layouts)
        st.session_state.needs_rerun = True

def on_layout_change():
    """Salva a preferência de colunas do layout quando o rádio é alterado."""
    num_cols = st.session_state.dashboard_layout_radio
    save_dashboard_column_preference(st.session_state.project_key, num_cols)

def move_item(items_list, from_index, to_index):
    """Move um item dentro de uma lista de uma posição para outra."""
    if 0 <= from_index < len(items_list) and 0 <= to_index < len(items_list):
        item = items_list.pop(from_index)
        items_list.insert(to_index, item)
    return items_list


# --- BLOCO 3: CSS E BARRA LATERAL ---
st.markdown("""
<style>
/* ... todo o CSS da resposta anterior ... */
/* Alinha os itens nos controlos do cabeçalho verticalmente ao centro */
[data-testid="stHorizontalBlock"] { align-items: center; }
/* Aumenta o espaço entre os gráficos */
div[data-testid="stVerticalBlock"] div[data-testid="stVerticalBlock"] { gap: 1.5rem; }
/* Estilo para o 'empty state' */
#empty-state-container { text-align: center; padding: 3rem; background-color: #f8f9fa; border-radius: 0.5rem; }
#empty-state-container .icon { font-size: 4rem; }

/* --- REGRAS PARA BOTÕES DE AÇÃO DOS GRÁFICOS (NOVO) --- */

/* Contêiner que alinha os botões de ação */
.card-actions {
    display: flex;
    justify-content: flex-end; /* Alinha os ícones à direita */
    align-items: center;
    gap: 0.5rem; /* Espaço entre os ícones */
}

/* Estilo base para os botões de ícone dentro do contêiner */
.card-actions [data-testid="stButton"] > button {
    background-color: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0.25rem !important; /* Padding para área de clique */
    margin: 0 !important;
    color: #4a4a4a;
    height: auto !important;
    min-width: auto !important;
    line-height: 1 !important;
    border-radius: 0.35rem; /* Bordas arredondadas no hover */
    display: flex;
    align-items: center;
    justify-content: center;
}

/* Efeito de hover */
.card-actions [data-testid="stButton"] > button:hover {
    background-color: #f0f2f6 !important;
    color: #1c1c1c;
}

/* Remove efeitos indesejados de clique/foco */
.card-actions [data-testid="stButton"] > button:active,
.card-actions [data-testid="stButton"] > button:focus {
    border: none !important;
    box-shadow: none !important;
    outline: none !important;
    transform: none !important;
}

/* Tamanho da fonte do ícone */
.card-actions [data-testid="stButton"] > button > span {
    font-size: 0.9rem !important;
}

/* --- REGRAS DE ANULAÇÃO E RESTAURAÇÃO PARA BOTÕES NA BARRA LATERAL (SEM ALTERAÇÕES) --- */
div[data-testid="stSidebarContent"] [data-testid="stButton"] > button {
    padding: 0.375rem 0.75rem !important;
    height: auto !important;
    min-width: 100% !important;
    box-shadow: none !important;
    border-radius: 0.5rem !important;
}
div[data-testid="stSidebarContent"] [kind="primary"] > button {
    background-color: var(--primary-color) !important;
    color: white !important;
    border: 1px solid var(--primary-color) !important;
}
div[data-testid="stSidebarContent"] [kind="secondary"] > button {
    background-color: transparent !important;
    border: 1px solid rgb(210, 210, 210) !important;
    color: rgb(73, 80, 87) !important;
}
div[data-testid="stSidebarContent"] [data-testid="stButton"] > button > span {
    font-size: 1rem !important;
    color: inherit !important;
}
</style>
""", unsafe_allow_html=True)

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

    selected_project_name = st.selectbox("Selecione um Projeto", options=project_names, key="project_selector_creator", index=default_index, placeholder="Escolha um projeto...")

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
        email_to_remember = st.session_state.get('remember_email', '')
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        if email_to_remember:
            st.session_state['remember_email'] = email_to_remember
        st.switch_page("1_🔑_Autenticação.py")


# --- BLOCO 4: LÓGICA PRINCIPAL DA PÁGINA E RENDERIZAÇÃO ---
df = st.session_state.get('dynamic_df')
current_project_key = st.session_state.get('project_key')

if df is None or not st.session_state.get('project_name'):
    st.info("⬅️ Na barra lateral, selecione um projeto e clique em 'Visualizar Dashboard' para carregar os dados.")
    st.stop()

# Carregamento e Preparação das Configurações de Layout
user_data = find_user(st.session_state['email'])
all_layouts = user_data.get('dashboard_layout', {})
project_layouts = all_layouts.get(current_project_key, {})
available_dashboards = project_layouts.get('dashboards', {})

if not available_dashboards:
    available_dashboards["main"] = {"id": "main", "name": "Dashboard Principal", "tabs": {"Geral": []}}
    project_layouts['dashboards'] = available_dashboards
    project_layouts['active_dashboard_id'] = "main"
    save_user_dashboard(st.session_state['email'], all_layouts)

active_dashboard_id = project_layouts.get('active_dashboard_id')
active_dashboard_config = available_dashboards.get(active_dashboard_id, {"tabs": {"Geral": []}})
tabs_layout = active_dashboard_config.get('tabs', {"Geral": []})

# Validação e Limpeza dos Gráficos
needs_saving = False
for tab_name, charts in list(tabs_layout.items()):
    if not isinstance(charts, list):
        charts = []
        needs_saving = True
    valid_charts = [chart for chart in charts if is_valid_chart(chart)]
    if len(valid_charts) != len(charts):
        tabs_layout[tab_name] = valid_charts
        needs_saving = True
if needs_saving:
    save_user_dashboard(st.session_state['email'], all_layouts)

all_charts = [chart for tab_charts in tabs_layout.values() for chart in tab_charts]
project_config = get_project_config(current_project_key) or {}
default_cols = project_config.get('dashboard_columns', 2)
active_dashboard_name = active_dashboard_config.get('name', 'Dashboard')


# Controles do Cabeçalho
cols = st.columns([2.5, 1.5, 1.5, 1.5, 1.5])
with cols[0]:
    dashboard_names = {db['name']: db['id'] for db_id, db in available_dashboards.items()}
    selected_dashboard_name = st.selectbox("Visualizar Dashboard:", options=dashboard_names.keys(), index=list(dashboard_names.keys()).index(active_dashboard_name) if active_dashboard_name in dashboard_names else 0, label_visibility="collapsed")
    selected_dashboard_id = dashboard_names.get(selected_dashboard_name)
    if selected_dashboard_id != active_dashboard_id:
        project_layouts['active_dashboard_id'] = selected_dashboard_id
        all_layouts[current_project_key] = project_layouts
        save_user_dashboard(st.session_state['email'], all_layouts)
        st.rerun()

with cols[1]:
    st.radio("Layout em Colunas", [1, 2], index=(1 if default_cols == 2 else 0), horizontal=True, key="dashboard_layout_radio", on_change=on_layout_change)

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
        add_chart_callback()

st.divider()

if 'ai_dashboard_insights' in st.session_state and st.session_state.ai_dashboard_insights:
    with st.expander("🤖 Análise da Gauge AI para o Dashboard", expanded=True):
        st.markdown(st.session_state.ai_dashboard_insights)
        if st.button("Fechar Análise", key="close_ai_insights"):
            del st.session_state.ai_dashboard_insights
            st.rerun()

# Filtros Globais
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

# Interface Principal: Modo de Organização ou Visualização
if organize_mode:
    st.subheader("🛠️ Modo de Organização")
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
                new_tab = cols[1].selectbox("Mover para a aba:", options=tab_options, index=default_index, key=f"select_tab_{chart_id}")
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
        st.markdown("""<div style="text-align: center; padding: 2rem;"><h3>Seu Dashboard está vazio!</h3><p>Adicione visualizações do laboratório de criação para ver seus dados aqui.</p></div>""", unsafe_allow_html=True)
        if st.button("➕ Adicionar seu primeiro gráfico", type="primary"):
            add_chart_callback()
    else:
        tab_names = list(tabs_with_charts.keys())
        st_tabs = st.tabs(tab_names)
        for i, tab_name in enumerate(tab_names):
            with st_tabs[i]:
                charts_in_tab_original = tabs_with_charts.get(tab_name, [])
                unique_charts_in_tab, seen_ids = [], set()
                for chart in charts_in_tab_original:
                    chart_id = chart.get('id')
                    if chart_id and chart_id not in seen_ids:
                        unique_charts_in_tab.append(chart)
                        seen_ids.add(chart_id)
                charts_in_tab = unique_charts_in_tab
                indicator_charts = [c for c in charts_in_tab if c.get('type') == 'indicator']
                other_charts = [c for c in charts_in_tab if c.get('type') != 'indicator']
                if indicator_charts:
                    cols = st.columns(len(indicator_charts))
                    for idx, chart_config in enumerate(indicator_charts):
                        with cols[idx]:
                            original_index = charts_in_tab.index(chart_config)
                            with st.container(border=True):
                                # Container para os botões de ação
                                st.markdown('<div class="card-actions">', unsafe_allow_html=True)
                                # Colunas para organizar os botões dentro do container flex
                                b_cols = st.columns(4)
                                b_cols[0].button("🔼", key=f"indicator_up_{tab_name}_{chart_config['id']}", help="Mover para cima", on_click=move_chart_callback, args=(charts_in_tab, tab_name, original_index, original_index - 1, current_project_key, all_layouts), disabled=(original_index == 0), use_container_width=True)
                                b_cols[1].button("🔽", key=f"indicator_down_{tab_name}_{chart_config['id']}", help="Mover para baixo", on_click=move_chart_callback, args=(charts_in_tab, tab_name, original_index, original_index + 1, current_project_key, all_layouts), disabled=(original_index >= len(charts_in_tab) - 1), use_container_width=True)
                                if b_cols[2].button("✏️", key=f"indicator_edit_{tab_name}_{chart_config['id']}", help="Editar", use_container_width=True):
                                    edit_chart_callback(chart_config)
                                b_cols[3].button("❌", key=f"indicator_del_{tab_name}_{chart_config['id']}", help="Remover", on_click=remove_chart_callback, args=(chart_config['id'], tab_name, current_project_key, all_layouts), use_container_width=True)
                                st.markdown('</div>', unsafe_allow_html=True)

                                # Renderiza o gráfico logo abaixo dos botões
                                render_chart(chart_config, filtered_df, f"chart_indicator_{tab_name}_{chart_config['id']}")
                    if other_charts:
                        st.divider()
                if other_charts:
                    layout_columns = project_config.get('dashboard_columns', 2)
                    cols = st.columns(layout_columns)
                    for idx, chart_config in enumerate(other_charts):
                        with cols[idx % layout_columns]:
                            original_index = charts_in_tab.index(chart_config)
                            with st.container(border=True):
                                header_cols = st.columns([0.6, 0.1, 0.1, 0.1, 0.1])
                                header_cols[0].markdown(f"**📊 {chart_config.get('title', 'Visualização')}**")
                                header_cols[1].button("🔼", key=f"other_up_{tab_name}_{chart_config['id']}", help="Mover para cima", on_click=move_chart_callback, args=(charts_in_tab, tab_name, original_index, original_index - 1, current_project_key, all_layouts), disabled=(original_index == 0), use_container_width=True)
                                header_cols[2].button("🔽", key=f"other_down_{tab_name}_{chart_config['id']}", help="Mover para baixo", on_click=move_chart_callback, args=(charts_in_tab, tab_name, original_index, original_index + 1, current_project_key, all_layouts), disabled=(original_index >= len(charts_in_tab) - 1), use_container_width=True)
                                if header_cols[3].button("✏️", key=f"other_edit_{tab_name}_{chart_config['id']}", help="Editar", use_container_width=True):
                                    edit_chart_callback(chart_config)                               
                                header_cols[4].button("❌", key=f"other_del_{tab_name}_{chart_config['id']}", help="Remover", on_click=remove_chart_callback, args=(chart_config['id'], tab_name, current_project_key, all_layouts), use_container_width=True)
                                render_chart(chart_config, filtered_df, f"chart_other_{tab_name}_{chart_config['id']}")

# --- BLOCO 5: EXECUTOR DE SINAL (SEMPRE NO FINAL DO SCRIPT) ---
if st.session_state.get('needs_rerun', False):
    del st.session_state['needs_rerun']
    st.rerun()
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

st.set_page_config(page_title="Meu Dashboard", page_icon="🏠", layout="wide")

# --- CSS FINAL PARA ESTILO E ALINHAMENTO ---
st.markdown("""
<style>
/* 1. Regra geral: Alinha os cartões do dashboard no TOPO */
[data-testid="stVerticalBlock"] div.st-emotion-cache-1jicfl2 {
    align-items: flex-start;
}
/* 2. Regra específica: Alinha os itens DENTRO do painel de controlo ao CENTRO */
#control-panel [data-testid="stHorizontalBlock"] {
    align-items: center;
}
</style>
""", unsafe_allow_html=True)

def on_project_change():
    """Limpa o estado relevante ao trocar de projeto."""
    if 'dynamic_df' in st.session_state: st.session_state.pop('dynamic_df', None)
    if 'loaded_project_key' in st.session_state: st.session_state.pop('loaded_project_key', None)

def on_layout_change():
    """Callback que lê o estado do toggle e chama a função para guardar a preferência."""
    use_two_cols = st.session_state.dashboard_layout_toggle
    num_cols = 2 if use_two_cols else 1
    save_dashboard_column_preference(st.session_state.project_key, num_cols)

def move_item(items_list, from_index, to_index):
    """Move um item dentro de uma lista de uma posição para outra."""
    if 0 <= from_index < len(items_list) and 0 <= to_index < len(items_list):
        item = items_list.pop(from_index)
        items_list.insert(to_index, item)
    return items_list

st.header(f"🏠 Meu Dashboard: {st.session_state.get('project_name', 'Nenhum Projeto Carregado')}", divider='rainbow')

# --- Bloco de Autenticação e Conexão ---
if 'email' not in st.session_state:
    st.warning("⚠️ Por favor, faça login para acessar."); st.page_link("1_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑"); st.stop()

# --- LÓGICA DE VERIFICAÇÃO DE CONEXÃO CORRIGIDA ---
if 'jira_client' not in st.session_state:
    # Verifica se o utilizador tem alguma conexão guardada na base de dados
    user_connections = get_user_connections(st.session_state['email'])
    
    if not user_connections:
        # Cenário 1: O utilizador nunca configurou uma conexão
        st.warning("Nenhuma conexão Jira foi configurada ainda.", icon="🔌")
        st.info("Para começar, você precisa de adicionar as suas credenciais do Jira.")
        st.page_link("pages/8_🔗_Conexões_Jira.py", label="Configurar sua Primeira Conexão", icon="🔗")
        st.stop()
    else:
        # Cenário 2: O utilizador tem conexões, mas nenhuma está ativa
        st.warning("Nenhuma conexão Jira está ativa para esta sessão.", icon="⚡")
        st.info("Por favor, ative uma das suas conexões guardadas para carregar os dados.")
        st.page_link("pages/8_🔗_Conexões_Jira.py", label="Ativar uma Conexão", icon="🔗")
        st.stop()

# --- BARRA LATERAL SIMPLIFICADA ---
with st.sidebar:
    project_root = Path(__file__).parent.parent
    logo_path = project_root / "images" / "gauge-logo.svg"
    try:
        st.logo(
            logo_path, 
            size="large")
    except FileNotFoundError:
        st.write("Gauge Metrics") 

    st.markdown(f"Logado como: **{st.session_state.get('email', '')}**")
    st.header("Fonte de Dados")
    projects = st.session_state.get('projects', {})
    project_names = list(projects.keys())
    
    last_project_key = find_user(st.session_state['email']).get('last_project_key')
    default_index = project_names.index(next((name for name, key in projects.items() if key == last_project_key), None)) if last_project_key and projects else None
    
    selected_project_name = st.selectbox("Selecione um Projeto", options=project_names, key="project_selector_dashboard", index=default_index, on_change=on_project_change, placeholder="Escolha um projeto...")
    
    if selected_project_name:
        if st.button("Visualizar Dashboard", use_container_width=True, type="primary"):
            project_key = projects[selected_project_name]
            save_last_project(st.session_state['email'], project_key)
            st.session_state.project_key = project_key
            st.session_state.project_name = selected_project_name
            
            # --- CHAMADA À NOVA FUNÇÃO ---
            df = load_and_process_project_data(st.session_state.jira_client, project_key)
            st.session_state.dynamic_df = df
            st.session_state.loaded_project_key = project_key
            st.rerun()

        if st.button("Logout", use_container_width=True, type='secondary'):
            for key in list(st.session_state.keys()): del st.session_state[key]
            st.switch_page("1_🔑_Autenticação.py")

# --- LÓGICA PRINCIPAL DA PÁGINA ---
df = st.session_state.get('dynamic_df')
current_project_key = st.session_state.get('project_key')

if df is None or not current_project_key:
    st.info("⬅️ Na barra lateral, selecione um projeto e clique em 'Visualizar / Atualizar Dashboard' para carregar os dados.")
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
active_dashboard_config = available_dashboards.get(active_dashboard_id, {})
tabs_layout = active_dashboard_config.get('tabs', {"Geral": []})
all_charts = [chart for tab_charts in tabs_layout.values() for chart in tab_charts]
project_config = get_project_config(current_project_key) or {}
default_cols = project_config.get('dashboard_columns', 2)
active_dashboard_name = active_dashboard_config.get('name', 'Dashboard')

# --- NOVO SELETOR DE DASHBOARDS ---
dashboard_names = {db['name']: db['id'] for db_id, db in available_dashboards.items()}
selected_dashboard_name = st.selectbox(
    "Selecione o Dashboard para Visualizar:",
    options=dashboard_names.keys(),
    index=list(dashboard_names.keys()).index(active_dashboard_name) if active_dashboard_name in dashboard_names else 0
)
selected_dashboard_id = dashboard_names.get(selected_dashboard_name)
if selected_dashboard_id != active_dashboard_id:
    project_layouts['active_dashboard_id'] = selected_dashboard_id
    all_layouts[current_project_key] = project_layouts
    save_user_dashboard(st.session_state['email'], all_layouts); st.rerun()

# --- LÓGICA DE AUTOCORREÇÃO ---
all_charts_in_db = [chart for tab_charts in tabs_layout.values() for chart in tab_charts if isinstance(chart, dict)]
clean_tabs_layout = {name: [] for name in tabs_layout.keys()}
all_chart_ids_in_clean_layout = set()

for chart in all_charts_in_db:
    current_tab = next((tab for tab, charts in tabs_layout.items() if chart.get('id') in [c.get('id') for c in charts if isinstance(c, dict)]), "Geral")
    if chart.get('id') not in all_chart_ids_in_clean_layout:
         clean_tabs_layout[current_tab].append(chart)
         all_chart_ids_in_clean_layout.add(chart['id'])

if json.dumps(tabs_layout, sort_keys=True) != json.dumps(clean_tabs_layout, sort_keys=True):
    project_layouts['dashboards'][active_dashboard_id]['tabs'] = clean_tabs_layout
    all_layouts[current_project_key] = project_layouts
    save_user_dashboard(st.session_state['email'], all_layouts)
    st.toast("Layout do dashboard foi limpo e sincronizado!", icon="🧹")
    st.rerun()

all_charts = [chart for tab_charts in tabs_layout.values() for chart in tab_charts]
project_config = get_project_config(current_project_key) or {}
default_cols = project_config.get('dashboard_columns', 2)


# ===== FILTROS GLOBAIS DINÂMICOS E INTELIGENTES =====
with st.expander("Filtros do Dashboard (afetam todas as visualizações)", expanded=False):
    
    # --- LÓGICA PARA DESCOBRIR OS NOMES DOS CAMPOS ---
    global_configs = st.session_state.get('global_configs', {})
    all_std_fields = global_configs.get('available_standard_fields', {})

    # Procura pelo nome que o utilizador deu a cada campo padrão
    name_for_issuetype = next((name for name, conf in all_std_fields.items() if conf.get('id') == 'issuetype'), 'Tipo de Issue')
    name_for_assignee = next((name for name, conf in all_std_fields.items() if conf.get('id') == 'assignee'), 'Responsável')
    name_for_status = next((name for name, conf in all_std_fields.items() if conf.get('id') == 'status'), 'Status')
    name_for_priority = next((name for name, conf in all_std_fields.items() if conf.get('id') == 'priority'), 'Prioridade')
    
    # Lista dos campos a serem exibidos como filtros
    filter_fields_to_display = [
        name_for_issuetype, name_for_assignee, name_for_status, name_for_priority
    ]

    filter_cols = st.columns(len(filter_fields_to_display))
    selections = {}

    for i, field_name in enumerate(filter_fields_to_display):
        has_field = field_name in df.columns
        options = sorted(df[field_name].dropna().unique()) if has_field else []
        
        selections[field_name] = filter_cols[i].multiselect(
            f"Filtrar por {field_name}", 
            options=options, 
            placeholder="Todos", 
            disabled=not has_field,
            help=f"O campo '{field_name}' não foi carregado. Ative-o em 'Minha Conta' e recarregue os dados." if not has_field else ""
        )
    
    # Cria o dataframe filtrado
    filtered_df = df.copy()
    for field_name, selected_values in selections.items():
        if selected_values:
            filtered_df = filtered_df[filtered_df[field_name].isin(selected_values)]

st.caption(f"A exibir visualizações para o projeto: **{st.session_state.project_name}**.")

# --- PAINEL DE CONTROLE ---
st.markdown('<div id="control-panel">', unsafe_allow_html=True)
with st.container(border=True):
    col1, col2, col3 = st.columns([1, 1.5, 1])
    
    with col1:
        st.metric("Visualizações", f"{len(all_charts)} / {DASHBOARD_CHART_LIMIT}")

    with col2:
        st.caption("Controlos de Layout")
        toggle_cols = st.columns(2)
        with toggle_cols[0]:
            use_two_columns = st.toggle("2 Colunas", value=(default_cols == 2), key="dashboard_layout_toggle", on_change=on_layout_change)
            num_columns = 2 if use_two_columns else 1
        with toggle_cols[1]:
            organize_mode = st.toggle("Organizar", help="Ative para gerir dashboards, abas e mover gráficos.")
            
    with col3:
        st.caption("Ações")
        if len(all_charts) >= DASHBOARD_CHART_LIMIT:
            st.button("Limite Atingido", disabled=True, use_container_width=True)
        else:
            if st.button("➕ Adicionar Gráfico", use_container_width=True, type="primary"):
                st.switch_page("pages/5_🏗️_Construir Gráficos.py")

st.markdown('</div>', unsafe_allow_html=True)
st.divider()

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
                if st.form_submit_button("➕ Criar Novo Dashboard", use_container_width=True):
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
                if st.form_submit_button("✏️ Renomear", use_container_width=True):
                    if renamed_dashboard_name:
                        layouts = find_user(st.session_state['email']).get('dashboard_layout', {})
                        layouts[current_project_key]['dashboards'][active_dashboard_id]['name'] = renamed_dashboard_name
                        save_user_dashboard(st.session_state['email'], layouts)
                        st.success("Dashboard renomeado!")
                        st.rerun()
        
        st.divider()
        if len(available_dashboards) > 1:
            if st.button("❌ Apagar Dashboard Atual", use_container_width=True, type="secondary"):
                layouts = find_user(st.session_state['email']).get('dashboard_layout', {})
                del layouts[current_project_key]['dashboards'][active_dashboard_id]
                layouts[current_project_key]['active_dashboard_id'] = next(iter(layouts[current_project_key]['dashboards']))
                save_user_dashboard(st.session_state['email'], layouts)
                st.success("Dashboard apagado!")
                st.rerun()
        else:
            st.button("❌ Apagar Dashboard Atual", use_container_width=True, disabled=True, help="Não pode apagar o seu último dashboard.")

    # --- 2. GESTÃO DE ABAS E GRÁFICOS (NOVA INTERFACE) ---
    st.markdown("**2. Gerir Abas e Atribuir Gráficos**")
    
    # Lógica para mover entre abas (com botões de "setas")
    tab_names = list(tabs_layout.keys())
    if not tab_names:
        st.info("Adicione uma aba para começar a organizar os gráficos.")
    else:
        # Cria as colunas para o layout de "quadro"
        cols = st.columns(len(tab_names))
        
        for i, tab_name in enumerate(tab_names):
            with cols[i]:
                st.markdown(f"**{tab_name}**")
                st.caption(f"{len(tabs_layout[tab_name])} gráficos")
                st.divider()
                
                # Para cada gráfico na aba, cria um cartão
                charts_in_tab = tabs_layout[tab_name]
                for j, chart in enumerate(charts_in_tab):
                    with st.container(border=True):
                        # Título e botões de movimento
                        btn_cols = st.columns([1, 1, 1])
                        with btn_cols[0]:
                            if st.button("⬅️", key=f"move_left_{tab_name}_{j}", disabled=(i == 0), use_container_width=True):
                                layouts = find_user(st.session_state['email']).get('dashboard_layout', {})
                                # Move o gráfico da aba atual para a anterior
                                chart_to_move = layouts[current_project_key]['dashboards'][active_dashboard_id]['tabs'][tab_name].pop(j)
                                layouts[current_project_key]['dashboards'][active_dashboard_id]['tabs'][tab_names[i-1]].append(chart_to_move)
                                save_user_dashboard(st.session_state['email'], layouts); st.rerun()
                        with btn_cols[2]:
                            if st.button("➡️", key=f"move_right_{tab_name}_{j}", disabled=(i == len(tab_names) - 1), use_container_width=True):
                                layouts = find_user(st.session_state['email']).get('dashboard_layout', {})
                                chart_to_move = layouts[current_project_key]['dashboards'][active_dashboard_id]['tabs'][tab_name].pop(j)
                                layouts[current_project_key]['dashboards'][active_dashboard_id]['tabs'][tab_names[i+1]].append(chart_to_move)
                                save_user_dashboard(st.session_state['email'], layouts); st.rerun()

                        st.caption(f"**{chart.get('title', 'Gráfico')}**")
                        st.info("Clique para mover", icon="👆")
else:
    # --- MODO DE VISUALIZAÇÃO COM ABAS ---
    tabs_with_charts = {name: charts for name, charts in tabs_layout.items() if charts}
    if not tabs_with_charts:
        st.info(f"O dashboard '{active_dashboard_name}' está vazio.")
    else:
        tab_names = list(tabs_with_charts.keys())
        st_tabs = st.tabs(tab_names)
        for i, tab_name in enumerate(tab_names):
            with st_tabs[i]:
                dashboard_items_in_tab = tabs_with_charts[tab_name]
                num_columns = default_cols
                cols = st.columns(num_columns, gap="large")
                for j, chart_to_render in enumerate(dashboard_items_in_tab):
                    with cols[j % num_columns]:
                        with st.container(border=True):
                            header_cols = st.columns([0.6, 0.1, 0.1, 0.1, 0.1])
                            with header_cols[0]:
                                card_title = chart_to_render.get('title', 'Visualização'); card_icon = chart_to_render.get('icon', '📊')
                                st.markdown(f"**{card_icon} {card_title}**")
                            with header_cols[1]:
                                if st.button("⬆️", key=f"up_{chart_to_render['id']}", help="Mover", disabled=(j == 0), use_container_width=True):
                                    tabs_layout[tab_name] = move_item(list(dashboard_items_in_tab), j, j - 1); all_layouts[current_project_key]['dashboards'][active_dashboard_id]['tabs'] = tabs_layout; save_user_dashboard(st.session_state['email'], all_layouts); st.rerun()
                            with header_cols[2]:
                                if st.button("⬇️", key=f"down_{chart_to_render['id']}", help="Mover", disabled=(j == len(dashboard_items_in_tab) - 1), use_container_width=True):
                                    tabs_layout[tab_name] = move_item(list(dashboard_items_in_tab), j, j + 1); all_layouts[current_project_key]['dashboards'][active_dashboard_id]['tabs'] = tabs_layout; save_user_dashboard(st.session_state['email'], all_layouts); st.rerun()
                            with header_cols[3]:
                                if st.button("✏️", key=f"edit_{chart_to_render['id']}", help="Editar", use_container_width=True):
                                    st.session_state['chart_to_edit'] = chart_to_render; st.switch_page("pages/5_🏗️_Personalizar Gráficos.py")
                            with header_cols[4]:
                                if st.button("❌", key=f"del_{chart_to_render['id']}", help="Remover", use_container_width=True):
                                    tabs_layout[tab_name] = [item for item in dashboard_items_in_tab if item['id'] != chart_to_render['id']]; all_layouts[current_project_key]['dashboards'][active_dashboard_id]['tabs'] = tabs_layout; save_user_dashboard(st.session_state['email'], all_layouts); st.rerun()
                            st.divider()
                            # Assumindo que filtered_df está definido no escopo principal
                            if 'filtered_df' in locals():
                                render_chart(chart_to_render, filtered_df)
                            else:
                                render_chart(chart_to_render, df)
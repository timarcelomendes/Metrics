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

# --- CSS Simplificado ---
st.markdown("""
<style>
/* Remove o espaçamento extra no topo da página */
.block-container {
    padding-top: 2rem;
    padding-bottom: 2rem;
}
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
</style>
""", unsafe_allow_html=True)


def on_project_change():
    """Limpa o estado relevante ao trocar de projeto."""
    if 'dynamic_df' in st.session_state: st.session_state.pop('dynamic_df', None)
    if 'loaded_project_key' in st.session_state: st.session_state.pop('loaded_project_key', None)

def on_layout_change():
    """Callback que lê o estado do radio e chama a função para guardar a preferência."""
    num_cols = st.session_state.dashboard_layout_radio
    save_dashboard_column_preference(st.session_state.project_key, num_cols)

def move_item(items_list, from_index, to_index):
    """Move um item dentro de uma lista de uma posição para outra."""
    if 0 <= from_index < len(items_list) and 0 <= to_index < len(items_list):
        item = items_list.pop(from_index)
        items_list.insert(to_index, item)
    return items_list

# --- Bloco de Autenticação e Conexão ---
if 'email' not in st.session_state:
    st.warning("⚠️ Por favor, faça login para acessar."); st.page_link("1_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑"); st.stop()
if 'jira_client' not in st.session_state:
    user_connections = get_user_connections(st.session_state['email'])
    if not user_connections:
        st.warning("Nenhuma conexão Jira foi configurada ainda.", icon="🔌")
        st.page_link("pages/8_🔗_Conexões_Jira.py", label="Configurar sua Primeira Conexão", icon="🔗")
        st.stop()
    else:
        st.warning("Nenhuma conexão Jira está ativa para esta sessão.", icon="⚡")
        st.page_link("pages/8_🔗_Conexões_Jira.py", label="Ativar uma Conexão", icon="🔗")
        st.stop()

# --- BARRA LATERAL ---
with st.sidebar:
    project_root = Path(__file__).parent.parent
    logo_path = project_root / "images" / "gauge-logo.svg"
    try:
        st.logo(logo_path, size="large")
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
        if st.button("Visualizar Dashboard", use_container_width=True, type="primary"):
            project_key = projects[selected_project_name]
            save_last_project(st.session_state['email'], project_key)
            st.session_state.project_key = project_key
            st.session_state.project_name = selected_project_name
            
            df = load_and_process_project_data(st.session_state.jira_client, project_key)
            st.session_state.dynamic_df = df
            st.session_state.loaded_project_key = project_key
            st.rerun()
    
    st.divider()
    if st.button("Logout", use_container_width=True, type='secondary'):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.switch_page("1_🔑_Autenticação.py")

# --- LÓGICA PRINCIPAL DA PÁGINA ---
df = st.session_state.get('dynamic_df')
current_project_key = st.session_state.get('project_key')

if df is None or not current_project_key:
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

# --- INÍCIO DA CORREÇÃO ---
# A variável all_charts é definida ANTES de ser usada.
all_charts = [chart for tab_charts in tabs_layout.values() for chart in tab_charts]
# --- FIM DA CORREÇÃO ---


# --- CABEÇALHO E CONTROLES (VERSÃO MINIMALISTA FINAL) ---
st.header(f"🏠 Meu Dashboard: {st.session_state.get('project_name', '')}")

cols = st.columns([3, 1.5, 1.5, 1.5])

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
    st.button("➕ Gráfico", use_container_width=True, type="primary", on_click=lambda: st.switch_page("pages/5_🏗️_Construir Gráficos.py"))

st.divider()


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

    with st.container(border=True):
        st.markdown("**2. Gerir Abas e Gráficos do Dashboard Atual**")
        
        # --- Gerir Abas ---
        st.markdown("###### Gerir Abas")
        tab_names = list(tabs_layout.keys())
        tabs_df = pd.DataFrame({"Nome da Aba": tab_names})
        
        edited_tabs_df = st.data_editor(
            tabs_df,
            num_rows="dynamic",
            use_container_width=True,
            key="tabs_editor"
        )
        
        # --- Atribuir Gráficos ---
        st.markdown("###### Atribuir Gráficos às Abas")
        if not all_charts:
            st.info("Nenhum gráfico neste dashboard. Adicione um para começar a organizar.")
        else:
            updated_chart_assignments = {}
            for chart in all_charts:
                chart_id = chart['id']
                current_tab = next((tab for tab, charts in tabs_layout.items() if chart_id in [c['id'] for c in charts]), None)
                
                # Prepara a lista de abas para o selectbox
                tab_options = edited_tabs_df["Nome da Aba"].tolist()
                
                # Garante que a aba atual do gráfico esteja na lista, mesmo que tenha sido apagada
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
        if st.button("Salvar Alterações de Organização", type="primary", use_container_width=True):
            # Lógica para salvar as alterações
            new_tabs_layout = {name: [] for name in edited_tabs_df["Nome da Aba"].tolist()}
            
            # Reatribui os gráficos com base nas novas seleções
            for chart in all_charts:
                assigned_tab = updated_chart_assignments.get(chart['id'])
                if assigned_tab in new_tabs_layout:
                    new_tabs_layout[assigned_tab].append(chart)
            
            # Atualiza e salva a configuração
            project_layouts['dashboards'][active_dashboard_id]['tabs'] = new_tabs_layout
            all_layouts[current_project_key] = project_layouts
            save_user_dashboard(st.session_state['email'], all_layouts)
            st.success("Organização do dashboard salva com sucesso!")
            st.rerun()

else:
    tabs_with_charts = {name: charts for name, charts in tabs_layout.items() if charts}
    
    if not any(tabs_with_charts.values()):
        st.markdown("""
        <div id="empty-state-container">
            <div class="icon">📊</div>
            <h3>Seu dashboard está vazio!</h3>
            <p>Comece a adicionar visualizações para analisar seus dados.</p>
        </div>
        """, unsafe_allow_html=True)
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
                            header_cols = st.columns([0.8, 0.1, 0.1])
                            with header_cols[0]:
                                st.markdown(f"**{chart_to_render.get('icon', '📊')} {chart_to_render.get('title', 'Visualização')}**")
                            with header_cols[1]:
                                if st.button("✏️", key=f"edit_{chart_to_render['id']}", help="Editar Gráfico", use_container_width=True):
                                    st.session_state['chart_to_edit'] = chart_to_render; st.switch_page("pages/5_🏗️_Construir Gráficos.py")
                            with header_cols[2]:
                                if st.button("❌", key=f"del_{chart_to_render['id']}", help="Remover Gráfico", use_container_width=True):
                                    tabs_layout[tab_name] = [item for item in dashboard_items_in_tab if item['id'] != chart_to_render['id']]; all_layouts[current_project_key]['dashboards'][active_dashboard_id]['tabs'] = tabs_layout; save_user_dashboard(st.session_state['email'], all_layouts); st.rerun()
                            
                            render_chart(chart_to_render, filtered_df)
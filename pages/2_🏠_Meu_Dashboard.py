# pages/2_🏠_Meu_Dashboard.py

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import uuid
import json
import os
from jira_connector import *
from metrics_calculator import *
from config import *
from utils import *
from security import *
from pathlib import Path
from datetime import datetime, timedelta

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

if 'jira_client' not in st.session_state:
    user_data = find_user(st.session_state['email'])
    if user_data and user_data.get('encrypted_token'):
        with st.spinner("A conectar ao Jira..."):
            token = decrypt_token(user_data['encrypted_token'])
            client = connect_to_jira(user_data['jira_url'], user_data['jira_email'], token)
            if client:
                st.session_state.jira_client = client; st.session_state.projects = get_projects(client); st.rerun()
            else: st.error("Falha na conexão com o Jira."); st.page_link("pages/9_👤_Minha_Conta.py", label="Verificar Credenciais", icon="👤"); st.stop()

    if not user_data:
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
        if st.button("Visualizar / Atualizar Dashboard", use_container_width=True, type="primary"):
            project_key = projects[selected_project_name]
            save_last_project(st.session_state['email'], project_key)
            st.session_state.project_key = project_key
            st.session_state.project_name = selected_project_name
            
            with st.spinner(f"A carregar e processar dados de '{selected_project_name}'..."):
                all_issues_raw = get_all_project_issues(st.session_state.jira_client, project_key)
                valid_issues = filter_ignored_issues(all_issues_raw)
                
                data = []
                user_data = find_user(st.session_state['email'])
                global_configs = st.session_state.get('global_configs', {})
                project_config = get_project_config(project_key) or {}
                
                user_enabled_standard = user_data.get('standard_fields', [])
                user_enabled_custom = user_data.get('enabled_custom_fields', [])
                all_available_standard = global_configs.get('available_standard_fields', {})
                all_available_custom = global_configs.get('custom_fields', [])
                estimation_config = project_config.get('estimation_field', {})

                for i in valid_issues:
                    completion_date = find_completion_date(i)
                    issue_data = {
                        'Issue': i.key,
                        'Data de Criação': pd.to_datetime(i.fields.created).tz_localize(None),
                        'Data de Conclusão': completion_date,
                        'Lead Time (dias)': calculate_lead_time(i),
                        'Cycle Time (dias)': calculate_cycle_time(i),
                    }
                    
                    # --- LÓGICA DE PROCESSAMENTO UNIVERSAL CORRIGIDA ---
                    fields_to_process = []
                    for field_name in user_enabled_standard:
                        if field_name in all_available_standard:
                            fields_to_process.append({**all_available_standard[field_name], 'name': field_name})
                    for field_config in all_available_custom:
                        if field_config.get('name') in user_enabled_custom:
                            fields_to_process.append(field_config)
                    
                    for field in fields_to_process:
                        field_id, field_name = field['id'], field['name']
                        value = getattr(i.fields, field_id, None)
                        
                        # Lógica inteligente para extrair o valor correto de qualquer tipo de campo
                        if value is None:
                            issue_data[field_name] = None
                        elif hasattr(value, 'displayName'): # Para campos de Utilizador (Assignee, Reporter)
                            issue_data[field_name] = value.displayName
                        elif isinstance(value, list) and value: # Para campos de lista (Seleção Múltipla, Componentes, etc.)
                            processed_list = []
                            for item in value:
                                if hasattr(item, 'value'): processed_list.append(item.value)
                                elif hasattr(item, 'name'): processed_list.append(item.name)
                                else: processed_list.append(str(item))
                            issue_data[field_name] = ', '.join(processed_list)
                        elif hasattr(value, 'value'): # Para campos de Seleção Única
                            issue_data[field_name] = value.value
                        elif hasattr(value, 'name'): # Para campos de Objeto Simples (Status, Priority)
                            issue_data[field_name] = value.name
                        else: # Para campos de texto simples, número ou data
                            issue_data[field_name] = str(value).split('T')[0]

                    # Adiciona o campo de estimativa
                    if estimation_config.get('id'):
                        issue_data[estimation_config['name']] = get_issue_estimation(i, estimation_config)
                        
                    data.append(issue_data)
                
                st.session_state.dynamic_df = pd.DataFrame(data)
                st.rerun()

        if st.button("Logout", use_container_width=True, type='secondary'):
            for key in list(st.session_state.keys()): del st.session_state[key]
            st.switch_page("1_🔑_Autenticação.py")

# --- LÓGICA PRINCIPAL DA PÁGINA ---
st.header(f"🏠 Meu Dashboard: {st.session_state.get('project_name', 'Nenhum Projeto Carregado')}", divider='rainbow')

df = st.session_state.get('dynamic_df')
current_project_key = st.session_state.get('project_key')

if df is None or not current_project_key:
    st.info("⬅️ Na barra lateral, selecione um projeto e clique em 'Visualizar / Atualizar Dashboard' para carregar os dados.")
    st.stop()

if 'email' not in st.session_state:
    st.warning("⚠️ Por favor, faça autenticação para acessar esta página."); st.page_link("1_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑"); st.stop()

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
        st.markdown("**Criar Novo Dashboard**")
        with st.form("new_dashboard_form"):
            new_dashboard_name = st.text_input("Nome do Novo Dashboard", placeholder="Ex: Dashboard Técnico")
            if st.form_submit_button("➕ Criar", use_container_width=True):
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

        st.divider()
        st.subheader("**Dashboards Existentes**")
        st.divider()
        for db_id, db_config in available_dashboards.items():
            with st.container():
                # --- NOVO LAYOUT DE AÇÕES NA MESMA LINHA ---
                name_col, actions_col = st.columns([2, 1])
                with name_col:
                    st.markdown(f"**{db_config.get('name')}** {'(Ativo)' if db_id == active_dashboard_id else ''}")
                
                with actions_col:
                    btn_cols = st.columns(3)
                    with btn_cols[0]:
                        with st.popover("Partilhar", use_container_width=True):
                            with st.form(f"share_form_{db_id}"):
                                st.markdown(f"Partilhar '{db_config.get('name')}'")
                                all_other_users = get_all_users(exclude_email=st.session_state['email'])
                                selected_users = st.multiselect("Selecione os utilizadores:", options=all_other_users)
                                if st.form_submit_button("Confirmar Partilha", type="primary"):
                                    if selected_users:
                                        success, message = share_specific_dashboard(st.session_state['email'], selected_users, current_project_key, db_id)
                                        if success: st.success(message)
                                        else: st.error(message)

                    with btn_cols[1]:
                        with st.popover("Renomear", use_container_width=True):
                            with st.form(f"rename_form_{db_id}"):
                                new_name = st.text_input("Novo Nome", value=db_config.get('name'))
                                if st.form_submit_button("Confirmar"):
                                    if new_name:
                                        layouts = find_user(st.session_state['email']).get('dashboard_layout', {})
                                        layouts[current_project_key]['dashboards'][db_id]['name'] = new_name
                                        save_user_dashboard(st.session_state['email'], layouts)
                                        st.rerun()

                    with btn_cols[2]:
                        if st.button("Apagar", key=f"del_{db_id}", disabled=(len(available_dashboards) <= 1), use_container_width=True):
                            layouts = find_user(st.session_state['email']).get('dashboard_layout', {})
                            del layouts[current_project_key]['dashboards'][db_id]
                            if active_dashboard_id == db_id:
                                layouts[current_project_key]['active_dashboard_id'] = next(iter(layouts[current_project_key]['dashboards']))
                            save_user_dashboard(st.session_state['email'], layouts)
                            st.rerun()

    # --- 2. GESTÃO DE ABAS (opera no dashboard ativo) ---
    st.markdown("**2. Gerir Abas do Dashboard Atual**")
    with st.container(border=True):
        c1, c2 = st.columns(2)
        with c1:
            with st.form("add_tab_form"):
                new_tab_name = st.text_input("Nome da Nova Aba")
                if st.form_submit_button("Adicionar Aba", use_container_width=True):
                    if new_tab_name and new_tab_name not in tabs_layout:
                        layouts = find_user(st.session_state['email']).get('dashboard_layout', {})
                        layouts[current_project_key]['dashboards'][active_dashboard_id]['tabs'][new_tab_name] = []
                        save_user_dashboard(st.session_state['email'], layouts)
                        st.rerun()
        with c2:
            with st.form("remove_tab_form"):
                tabs_to_remove = [name for name, charts in tabs_layout.items() if not charts and name != "Geral"]
                selected_tab_to_remove = st.selectbox("Remover Aba Vazia", options=[""] + tabs_to_remove)
                if st.form_submit_button("Remover Aba", use_container_width=True, type="secondary"):
                    if selected_tab_to_remove:
                        layouts = find_user(st.session_state['email']).get('dashboard_layout', {})
                        del layouts[current_project_key]['dashboards'][active_dashboard_id]['tabs'][selected_tab_to_remove]
                        save_user_dashboard(st.session_state['email'], layouts)
                        st.rerun()

        # --- NOVA INTERFACE DE ATRIBUIÇÃO (ESTILO PLAYLIST) ---
        st.markdown("**Atribuir Gráficos às Abas:**")
        
        # Cria uma lista de todos os gráficos disponíveis para seleção
        all_available_charts = {chart['id']: chart.get('title', 'Gráfico Sem Título') for chart in all_charts}
        
        new_assignments = {}
        for tab_name in tabs_layout.keys():
            # Para cada aba, mostra um seletor múltiplo
            current_charts_in_tab = [chart['id'] for chart in tabs_layout[tab_name]]
            
            selected_chart_ids = st.multiselect(
                f"Gráficos na Aba '{tab_name}'",
                options=all_available_charts.keys(),
                default=current_charts_in_tab,
                format_func=lambda chart_id: all_available_charts[chart_id] # Mostra o título do gráfico em vez do ID
            )
            new_assignments[tab_name] = selected_chart_ids

    if st.button("Salvar Organização", use_container_width=True, type="primary"):
        # Reconstrói a estrutura de abas com base nas seleções
        layouts = find_user(st.session_state['email']).get('dashboard_layout', {})
        new_tabs_layout = {tab_name: [] for tab_name in tabs_layout.keys()}
        
        # Mapeia os IDs de volta para os objetos de gráfico completos
        all_charts_map = {chart['id']: chart for chart in all_charts}
        
        for tab_name, chart_ids in new_assignments.items():
            for chart_id in chart_ids:
                if chart_id in all_charts_map:
                    new_tabs_layout[tab_name].append(all_charts_map[chart_id])
        
        layouts[current_project_key]['dashboards'][active_dashboard_id]['tabs'] = new_tabs_layout
        save_user_dashboard(st.session_state['email'], layouts)
        st.success("Organização do dashboard guardada!")
        st.rerun()

else:
    # ===== MODO DE VISUALIZAÇÃO COM ABAS =====
    tabs_with_charts = {name: charts for name, charts in tabs_layout.items() if charts}
    if not tabs_with_charts:
        st.info(f"O dashboard '{active_dashboard_name}' está vazio.")
    else:
        tab_names = list(tabs_with_charts.keys())
        st_tabs = st.tabs(tab_names)
        for i, tab_name in enumerate(tab_names):
            with st_tabs[i]:
                dashboard_items_in_tab = tabs_with_charts[tab_name]
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
                                    tabs_layout[tab_name] = move_item(list(dashboard_items_in_tab), j, j - 1); all_layouts[current_project_key]["tabs"] = tabs_layout; save_user_dashboard(st.session_state['email'], all_layouts); st.rerun()
                            with header_cols[2]:
                                if st.button("⬇️", key=f"down_{chart_to_render['id']}", help="Mover", disabled=(j == len(dashboard_items_in_tab) - 1), use_container_width=True):
                                    tabs_layout[tab_name] = move_item(list(dashboard_items_in_tab), j, j + 1); all_layouts[current_project_key]["tabs"] = tabs_layout; save_user_dashboard(st.session_state['email'], all_layouts); st.rerun()
                            with header_cols[3]:
                                if st.button("✏️", key=f"edit_{chart_to_render['id']}", help="Editar", use_container_width=True):
                                    st.session_state['chart_to_edit'] = chart_to_render; st.switch_page("pages/5_🏗️_Construir Gráficos.py")
                            with header_cols[4]:
                                if st.button("❌", key=f"del_{chart_to_render['id']}", help="Remover", use_container_width=True):
                                    tabs_layout[tab_name] = [item for item in dashboard_items_in_tab if item['id'] != chart_to_render['id']]; all_layouts[current_project_key]["tabs"] = tabs_layout; save_user_dashboard(st.session_state['email'], all_layouts); st.rerun()
                            st.divider()
                            render_chart(chart_to_render, filtered_df)
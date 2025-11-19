# pages/2_🏠_Meu_Dashboard.py

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import uuid
import json
from metrics_calculator import * # find_completion_date está aqui
from config import *
from utils import *
from security import *
from pathlib import Path
import importlib
from datetime import datetime, timedelta
import copy

st.set_page_config(page_title="Meu Dashboard", page_icon="🏠", layout="wide")

# --- Lógica de Título Dinâmico ---
project_name = st.session_state.get('project_name')
if project_name:
    st.header(f"🏠 Meu Dashboard ({project_name})", divider='rainbow')
else:
    st.header("🏠 Meu Dashboard (Selecione um projeto)", divider='rainbow')

# --- Verificações de segurança e sessão ---
if 'email' not in st.session_state:
    st.warning("⚠️ Por favor, faça login para acessar."); st.page_link("0_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑"); st.stop()
if check_session_timeout():
    st.warning(f"Sua sessão expirou por inatividade de {SESSION_TIMEOUT_MINUTES} minutos. Por favor, faça login novamente."); st.page_link("0_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑"); st.stop()
if 'jira_client' not in st.session_state:
    st.warning("Nenhuma conexão Jira está ativa para esta sessão.", icon="⚡"); st.info("Por favor, ative uma das suas conexões guardadas para carregar os dados."); st.page_link("pages/8_🔗_Conexões_Jira.py", label="Ativar uma Conexão", icon="🔗"); st.stop()

# --- Funções Auxiliares ---
def is_valid_chart(item):
    return isinstance(item, dict) and 'id' in item and 'title' in item

def ensure_project_data_is_loaded():
    if 'dynamic_df' not in st.session_state or st.session_state.get('dynamic_df') is None:
        project_key = st.session_state.get('project_key')
        if project_key and 'jira_client' in st.session_state:
            user_data = find_user(st.session_state['email'])
            df_loaded, raw_issues, proj_config = load_and_process_project_data(
                st.session_state.jira_client, 
                project_key,
                user_data
            )
            st.session_state.dynamic_df = df_loaded
            st.session_state.loaded_project_key = project_key

def add_chart_callback():
    keys_to_clear = ['chart_to_edit', 'creator_filters', 'chart_config_ia', 'new_chart_config']
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
    ensure_project_data_is_loaded()
    st.switch_page("pages/5_🏗️_Construir Gráficos.py")

def edit_chart_callback(chart_config):
    st.session_state['chart_to_edit'] = chart_config
    ensure_project_data_is_loaded()
    st.switch_page("pages/5_🏗️_Construir Gráficos.py")

# --- Callbacks Atualizados para Sincronização (Live Sync) ---

def remove_chart_callback(chart_id, tab_name, project_key, dashboard_id, owner_email):
    """Remove gráfico do dashboard correto (próprio ou do owner)."""
    # Determina quem é o dono real dos dados
    target_email = owner_email if owner_email else st.session_state['email']
    
    # Carrega os layouts do alvo
    target_user_data = find_user(target_email)
    if not target_user_data:
        st.error("Erro ao acessar dados do proprietário do dashboard.")
        return

    all_layouts = target_user_data.get('dashboard_layout', {})
    active_dashboard_id = dashboard_id # O ID deve ser passado explicitamente para evitar confusão

    # Verifica se o dashboard existe no alvo
    if project_key in all_layouts and active_dashboard_id in all_layouts[project_key].get('dashboards', {}):
        tabs = all_layouts[project_key]['dashboards'][active_dashboard_id]['tabs']
        if tab_name in tabs:
            tabs[tab_name] = [chart for chart in tabs[tab_name] if chart.get('id') != chart_id]
            save_user_dashboard(target_email, all_layouts)
            st.success("Gráfico removido!")
            st.session_state.needs_rerun = True
    else:
        st.error("Dashboard não encontrado no perfil de origem.")

def move_chart_callback(charts_list, tab_name, from_index, to_index, project_key, dashboard_id, owner_email):
    """Move gráfico no dashboard correto (próprio ou do owner)."""
    # Nota: charts_list é uma cópia local da renderização, precisamos modificar a fonte
    target_email = owner_email if owner_email else st.session_state['email']
    
    target_user_data = find_user(target_email)
    if not target_user_data: return

    all_layouts = target_user_data.get('dashboard_layout', {})
    
    if project_key in all_layouts and dashboard_id in all_layouts[project_key].get('dashboards', {}):
        tabs = all_layouts[project_key]['dashboards'][dashboard_id]['tabs']
        if tab_name in tabs:
            # Obtém a lista real da fonte
            source_list = tabs[tab_name]
            # Realiza a movimentação
            if 0 <= from_index < len(source_list) and 0 <= to_index < len(source_list):
                item = source_list.pop(from_index)
                source_list.insert(to_index, item)
                
                # Salva no alvo
                save_user_dashboard(target_email, all_layouts)
                st.session_state.needs_rerun = True

def on_layout_change():
    num_cols = st.session_state.dashboard_layout_radio
    save_dashboard_column_preference(st.session_state.project_key, num_cols)

def move_item(items_list, from_index, to_index):
    if 0 <= from_index < len(items_list) and 0 <= to_index < len(items_list):
        item = items_list.pop(from_index)
        items_list.insert(to_index, item)
    return items_list

# --- CSS ---
st.markdown("""
<style>
    [data-testid="stHorizontalBlock"] { align-items: center; }
    div[data-testid="stVerticalBlock"] div[data-testid="stVerticalBlock"] { gap: 1.5rem; }
    .card-actions { display: flex; justify-content: flex-end; align-items: center; gap: 0.5rem; }
    .card-actions [data-testid="stButton"] > button {
        background-color: transparent !important; border: none !important; box-shadow: none !important;
        padding: 0.25rem !important; margin: 0 !important; color: #4a4a4a; height: auto !important;
        min-width: auto !important; line-height: 1 !important; border-radius: 0.35rem;
        display: flex; align-items: center; justify-content: center;
    }
    .card-actions [data-testid="stButton"] > button:hover { background-color: #f0f2f6 !important; color: #1c1c1c; }
    
    div[data-testid="stExpander"] div[data-testid="stHorizontalBlock"] {
        align-items: flex-end;
    }
</style>
""", unsafe_allow_html=True)

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
    default_index = project_names.index(next((name for name, key in projects.items() if key == last_project_key), None)) if last_project_key and project_names else 0
    selected_project_name = st.selectbox("Selecione um Projeto", options=project_names, key="project_selector_creator", index=default_index, placeholder="Escolha um projeto...")
    if selected_project_name:
        if st.button("Visualizar Dashboard", width='stretch', type="primary"):
            project_key = projects[selected_project_name]
            save_last_project(st.session_state['email'], project_key)
            st.session_state.project_key = project_key
            st.session_state.project_name = selected_project_name
            
            user_data = find_user(st.session_state['email'])
            
            df_loaded, raw_issues, proj_config = load_and_process_project_data(
                st.session_state.jira_client, 
                project_key,
                user_data 
            )
            
            st.session_state.dynamic_df = df_loaded
            st.session_state.raw_issues_for_fluxo = raw_issues
            st.session_state.loaded_project_key = project_key
            st.rerun()

    st.divider()
    if st.button("Logout", width='stretch', type='secondary'):
        email_to_remember = st.session_state.get('remember_email', '')
        for key in list(st.session_state.keys()): del st.session_state[key]
        if email_to_remember: st.session_state['remember_email'] = email_to_remember
        st.switch_page("0_🔑_Autenticação.py")

# --- LÓGICA PRINCIPAL DA PÁGINA ---
df = st.session_state.get('dynamic_df')
current_project_key = st.session_state.get('project_key')
if df is None or not st.session_state.get('project_name'):
    st.info("⬅️ Na barra lateral, selecione um projeto e clique em 'Visualizar Dashboard' para carregar os dados.")
    st.stop()

# Carregamento e Preparação do Layout (Local)
user_data = find_user(st.session_state['email'])
all_layouts = user_data.get('dashboard_layout', {})
project_layouts = all_layouts.get(current_project_key, {})
available_dashboards = project_layouts.get('dashboards', {})

if not available_dashboards:
    available_dashboards["main"] = {"id": "main", "name": "Dashboard Principal", "tabs": {"Geral": []}, "permission": "owner"}
    project_layouts['dashboards'] = available_dashboards
    project_layouts['active_dashboard_id'] = "main"
    save_user_dashboard(st.session_state['email'], all_layouts)

active_dashboard_id = project_layouts.get('active_dashboard_id')
# Pega a configuração inicial da cópia local
active_dashboard_config = available_dashboards.get(active_dashboard_id, {"tabs": {"Geral": []}})

# --- LÓGICA DE SINCRONIZAÇÃO (LIVE SYNC) ---
# Se o dashboard tiver um 'owner_email' diferente de mim, buscamos a versão mais recente dele.
current_user_email = st.session_state['email']
dashboard_owner_email = active_dashboard_config.get('owner_email')

# Variável para controlar onde salvar as edições
target_save_email = current_user_email 

if dashboard_owner_email and dashboard_owner_email != current_user_email:
    # Busca dados frescos do proprietário
    owner_data = find_user(dashboard_owner_email)
    if owner_data:
        owner_layouts = owner_data.get('dashboard_layout', {}).get(current_project_key, {})
        if active_dashboard_id in owner_layouts.get('dashboards', {}):
            # Sobrescreve a config local com a config do owner (mantendo a permissão local)
            fresh_config = owner_layouts['dashboards'][active_dashboard_id]
            
            my_permission = active_dashboard_config.get('permission', 'view')
            
            # Atualiza o objeto que será usado para renderizar
            active_dashboard_config = copy.deepcopy(fresh_config)
            active_dashboard_config['permission'] = my_permission
            active_dashboard_config['owner_email'] = dashboard_owner_email # Garante que a ref se mantém
            
            # Define o alvo de salvamento para o dono
            target_save_email = dashboard_owner_email
        else:
            st.warning("Este dashboard parece ter sido removido pelo proprietário original.")

# Extrai dados para renderização
tabs_layout = active_dashboard_config.get('tabs', {"Geral": []})
active_dashboard_name = active_dashboard_config.get('name', 'Dashboard')
dashboard_permission = active_dashboard_config.get('permission', 'owner')

is_owner = (dashboard_permission == 'owner')
can_edit = is_owner or (dashboard_permission == 'edit')

# Validação básica de gráficos
for tab_name, charts in list(tabs_layout.items()):
    if not isinstance(charts, list): tabs_layout[tab_name] = []
    tabs_layout[tab_name] = [chart for chart in charts if is_valid_chart(chart)]

all_charts = [chart for tab_charts in tabs_layout.values() for chart in tab_charts]
project_config = get_project_config(current_project_key) or {}
default_cols = project_config.get('dashboard_columns', 2)

# --- CONTROLES DO CABEÇALHO ---
with st.expander("Opções do Dashboard", expanded=False):
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
        edit_mode = st.toggle("Modo Edição", key="dashboard_edit_mode", help="Ative para organizar o dashboard e editar gráficos.", disabled=not can_edit)
    with cols[3]:
        if st.button("🤖 Análise AI", help="Gerar análise do dashboard com IA", width='stretch'):
            with st.spinner("A Gauge AI está a analisar os dados..."):
                summaries = [summarize_chart_data(c, df) for c in all_charts]
                provider = user_data.get('ai_provider_preference', 'Google Gemini')
                insights = get_ai_insights(st.session_state.project_name, summaries, provider)
                st.session_state.ai_dashboard_insights = insights
    with cols[4]:
        # No add_chart, se for compartilhado, o novo gráfico deve ir para o dashboard do owner?
        # A lógica atual do add_chart usa 'chart_to_edit' e redireciona.
        # Na página 5, ao salvar, precisaremos garantir que ele salva no lugar certo.
        # (Por enquanto, a página 5 salva no 'current active dashboard' do usuário. 
        # Se o usuário for editor, ele salvará na sua cópia local, e a sincronização acima 
        # pode sobrescrever. *Idealmente*, a página 5 também precisaria de ajuste, 
        # mas focaremos aqui na organização e exclusão primeiro conforme pedido*)
        if st.button("➕ Gráfico", width='stretch', type="primary", disabled=not can_edit, help="Adicionar um novo gráfico a este dashboard."):
            # Para garantir integridade, se for editor, avisamos que a criação completa depende da pág 5
            add_chart_callback()

# Se o modo edição não estiver ativo, garante que a variável `edit_mode` seja False
if 'dashboard_edit_mode' not in st.session_state:
    edit_mode = False

# --- FUNÇÃO DE RENDERIZAÇÃO DO DASHBOARD ---
def render_dashboard_view(is_edit_mode):
    tabs_with_charts = {name: charts for name, charts in tabs_layout.items() if charts}
    if not any(tabs_with_charts.values()):
        st.markdown("""<div style="text-align: center; padding: 2rem;"><h3>Seu Dashboard está vazio!</h3></div>""", unsafe_allow_html=True)
        if can_edit:
            if st.button("➕ Adicionar seu primeiro gráfico", type="primary"):
                add_chart_callback()
    else:
        tab_names = list(tabs_with_charts.keys())
        st_tabs = st.tabs(tab_names)
        for i, tab_name in enumerate(tab_names):
            with st_tabs[i]:
                charts_in_tab = [c for c in tabs_with_charts.get(tab_name, []) if is_valid_chart(c)]
                indicator_charts = [c for c in charts_in_tab if c.get('type') == 'indicator']
                other_charts = [c for c in charts_in_tab if c.get('type') != 'indicator']

                # Define owner email para passar aos callbacks
                cb_owner = dashboard_owner_email if (dashboard_owner_email and dashboard_owner_email != current_user_email) else None

                if indicator_charts:
                    num_indicator_cols = 4
                    for j in range(0, len(indicator_charts), num_indicator_cols):
                        row_indicators = indicator_charts[j:j + num_indicator_cols]
                        cols = st.columns(len(row_indicators))
                        for idx, chart_config in enumerate(row_indicators):
                            with cols[idx]:
                                with st.container(border=True):
                                    original_index = charts_in_tab.index(chart_config)
                                    if is_edit_mode and can_edit:
                                        st.markdown('<div class="card-actions">', unsafe_allow_html=True)
                                        b_cols = st.columns(4)
                                        b_cols[0].button("🔼", key=f"up_{chart_config['id']}", on_click=move_chart_callback, args=(charts_in_tab, tab_name, original_index, original_index - 1, current_project_key, active_dashboard_id, cb_owner), disabled=(original_index == 0))
                                        b_cols[1].button("🔽", key=f"down_{chart_config['id']}", on_click=move_chart_callback, args=(charts_in_tab, tab_name, original_index, original_index + 1, current_project_key, active_dashboard_id, cb_owner), disabled=(original_index >= len(charts_in_tab) - 1))
                                        if b_cols[2].button("✏️", key=f"edit_{chart_config['id']}"): edit_chart_callback(chart_config)
                                        b_cols[3].button("❌", key=f"del_{chart_config['id']}", on_click=remove_chart_callback, args=(chart_config['id'], tab_name, current_project_key, active_dashboard_id, cb_owner))
                                        st.markdown('</div>', unsafe_allow_html=True)
                                    render_chart(chart_config, df, f"chart_{chart_config['id']}")
                    if other_charts: st.divider()

                if other_charts:
                    layout_columns = st.session_state.get('dashboard_layout_radio', default_cols)
                    cols = st.columns(layout_columns)
                    for idx, chart_config in enumerate(other_charts):
                        with cols[idx % layout_columns]:
                            with st.container(border=True):
                                original_index = charts_in_tab.index(chart_config)
                                if is_edit_mode and can_edit:
                                    header_cols = st.columns([0.6, 0.1, 0.1, 0.1, 0.1])
                                    header_cols[0].markdown(f"**📊 {chart_config.get('title', 'Visualização')}**")
                                    header_cols[1].button("🔼", key=f"up_other_{chart_config['id']}", on_click=move_chart_callback, args=(charts_in_tab, tab_name, original_index, original_index - 1, current_project_key, active_dashboard_id, cb_owner), disabled=(original_index == 0))
                                    header_cols[2].button("🔽", key=f"down_other_{chart_config['id']}", on_click=move_chart_callback, args=(charts_in_tab, tab_name, original_index, original_index + 1, current_project_key, active_dashboard_id, cb_owner), disabled=(original_index >= len(charts_in_tab) - 1))
                                    if header_cols[3].button("✏️", key=f"edit_other_{chart_config['id']}"): edit_chart_callback(chart_config)
                                    header_cols[4].button("❌", key=f"del_other_{chart_config['id']}", on_click=remove_chart_callback, args=(chart_config['id'], tab_name, current_project_key, active_dashboard_id, cb_owner))
                                else:
                                    st.markdown(f"**📊 {chart_config.get('title', 'Visualização')}**")
                                render_chart(chart_config, df, f"chart_other_{chart_config['id']}")

# --- LÓGICA DE EXIBIÇÃO ---
if edit_mode and can_edit:
    config_tab, view_tab = st.tabs(["⚙️ Configurar Dashboard", "🎨 Personalizar Dashboard"])
    
    with config_tab:
        with st.expander("🛠️ Organizar Dashboard e Abas", expanded=True):
            if is_owner:
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
                                    proj_layouts['dashboards'][new_id] = {"id": new_id, "name": new_dashboard_name, "tabs": {"Geral": []}, "permission": "owner"}
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
                    
                    with st.form("duplicate_dashboard_form"):
                        copy_name = st.text_input(
                            "Nome para a Cópia:", 
                            value=f"Cópia de {active_dashboard_name}"
                        )
                        
                        if st.form_submit_button("📥 Duplicar Dashboard Atual", width='stretch'):
                            if copy_name:
                                layouts = find_user(st.session_state['email']).get('dashboard_layout', {})
                                proj_layouts = layouts.get(current_project_key, {})
                                
                                dashboard_copy = copy.deepcopy(active_dashboard_config)
                                new_id = str(uuid.uuid4())
                                dashboard_copy['id'] = new_id
                                dashboard_copy['name'] = copy_name
                                dashboard_copy['permission'] = 'owner'
                                if 'owner_email' in dashboard_copy:
                                    del dashboard_copy['owner_email']

                                proj_layouts['dashboards'][new_id] = dashboard_copy
                                proj_layouts['active_dashboard_id'] = new_id
                                layouts[current_project_key] = proj_layouts
                                save_user_dashboard(st.session_state['email'], layouts)
                                st.success(f"Dashboard '{copy_name}' criado com sucesso!")
                                st.rerun()

                    st.divider()
                    
                    st.markdown("###### Partilhar Dashboard Atual")
                    with st.form("assign_dashboard_form"):
                        current_user_email_val = st.session_state.get('email', '')
                        other_users_emails = get_all_users(exclude_email=current_user_email_val)
                        if not other_users_emails:
                            st.info("Não há outros utilizadores registados.")
                            st.form_submit_button("Partilhar", width='stretch', disabled=True)
                        else:
                            target_user_email_sel = st.selectbox("Partilhar com o utilizador:", options=other_users_emails)
                            permission_level = st.radio("Nível de Permissão:", ["Pode Visualizar", "Pode Editar"], horizontal=True)
                            if st.form_submit_button("📬 Partilhar", width='stretch'):
                                target_user_data_share = find_user(target_user_email_sel)
                                if target_user_data_share:
                                    # Copia, mas mantém a referência ao owner (o atual)
                                    dashboard_copy = copy.deepcopy(active_dashboard_config)
                                    dashboard_copy['owner_email'] = current_user_email_val
                                    dashboard_copy['permission'] = 'edit' if permission_level == "Pode Editar" else 'view'
                                    
                                    target_layouts = target_user_data_share.get('dashboard_layout', {})
                                    if current_project_key not in target_layouts: target_layouts[current_project_key] = {'dashboards': {}}
                                    target_layouts[current_project_key]['dashboards'][active_dashboard_id] = dashboard_copy
                                    
                                    save_user_dashboard(target_user_email_sel, target_layouts)
                                    st.success(f"Dashboard '{active_dashboard_name}' partilhado com {target_user_email_sel}!")
                                else:
                                    st.error("Utilizador de destino não encontrado.")
                    st.divider()

                    st.markdown("###### Gerir Partilhas")
                    current_user_email_val = st.session_state.get('email', '')
                    shared_with_list = []
                    all_other_users_emails = get_all_users(exclude_email=current_user_email_val)
                    for other_user_email in all_other_users_emails:
                        other_user_data = find_user(other_user_email)
                        if other_user_data:
                            other_user_dashboards = other_user_data.get('dashboard_layout', {}).get(current_project_key, {}).get('dashboards', {})
                            if active_dashboard_id in other_user_dashboards:
                                dashboard_info = other_user_dashboards[active_dashboard_id]
                                if dashboard_info.get('owner_email') == current_user_email_val:
                                    permission = dashboard_info.get('permission', 'view')
                                    shared_with_list.append({'email': other_user_email, 'permission': permission})
                    
                    if not shared_with_list:
                        st.info("Este dashboard ainda não foi partilhado com outros utilizadores.")
                    else:
                        st.write("Partilhado com:")
                        for shared_user in shared_with_list:
                            shared_user_email = shared_user['email']
                            permission_text = "Edição" if shared_user['permission'] == 'edit' else "Visualização"
                            
                            r_cols = st.columns([0.6, 0.2, 0.2])
                            r_cols[0].write(f"- {shared_user_email}")
                            r_cols[1].write(f"_{permission_text}_")
                            if r_cols[2].button("Revogar", key=f"revoke_{shared_user_email}", help=f"Revogar acesso de {shared_user_email}", width='stretch'):
                                target_user_data_rev = find_user(shared_user_email)
                                if target_user_data_rev:
                                    target_layouts = target_user_data_rev.get('dashboard_layout', {})
                                    if current_project_key in target_layouts and active_dashboard_id in target_layouts[current_project_key]['dashboards']:
                                        del target_layouts[current_project_key]['dashboards'][active_dashboard_id]
                                        save_user_dashboard(shared_user_email, target_layouts)
                                        st.success(f"Acesso de {shared_user_email} revogado com sucesso!")
                                        st.rerun()

                    st.divider()
                    if len(available_dashboards) > 1:
                        if st.button("❌ Apagar Dashboard Atual", width='stretch', type="secondary"):
                            layouts = find_user(st.session_state['email']).get('dashboard_layout', {})
                            del layouts[current_project_key]['dashboards'][active_dashboard_id]
                            layouts[current_project_key]['active_dashboard_id'] = next(iter(layouts[current_project_key]['dashboards']))
                            save_user_dashboard(st.session_state['email'], layouts)
                            st.success("Dashboard apagado!"); st.rerun()
                    else:
                        st.button("❌ Apagar Dashboard Atual", width='stretch', disabled=True, help="Não pode apagar o seu último dashboard.")
            else:
                st.info("Apenas o proprietário do dashboard pode renomear, partilhar ou apagar o dashboard.")

            with st.container(border=True):
                st.markdown("**2. Gerir Abas e Gráficos do Dashboard Atual**")
                st.markdown("###### Gerir Abas")
                                
                if 'updated_tabs_layout' in st.session_state:
                    current_tabs_layout = st.session_state.updated_tabs_layout
                else:
                    current_tabs_layout = copy.deepcopy(tabs_layout)
                    st.session_state.updated_tabs_layout = current_tabs_layout
                
                tab_items = list(current_tabs_layout.items())
                
                for i, (tab_name, charts) in enumerate(tab_items):
                    cols = st.columns([0.7, 0.1, 0.1, 0.1])
                    new_name = cols[0].text_input("Nome da Aba", value=tab_name, key=f"tab_rename_key_{tab_name}")
                    
                    if cols[1].button("🔼", key=f"up_tab_{tab_name}", help="Mover para cima", width='stretch', disabled=(i == 0)):
                        moved_items = move_item(list(current_tabs_layout.items()), i, i - 1)
                        st.session_state.updated_tabs_layout = dict(moved_items)
                        st.rerun()

                    if cols[2].button("🔽", key=f"down_tab_{tab_name}", help="Mover para baixo", width='stretch', disabled=(i == len(tab_items) - 1)):
                        moved_items = move_item(list(current_tabs_layout.items()), i, i + 1)
                        st.session_state.updated_tabs_layout = dict(moved_items)
                        st.rerun()

                    if cols[3].button("❌", key=f"del_tab_{tab_name}", help="Apagar aba", width='stretch', disabled=(len(tab_items) <= 1)):
                        charts_to_move = current_tabs_layout.pop(tab_name)
                        first_tab_name = next(iter(current_tabs_layout))
                        current_tabs_layout[first_tab_name].extend(charts_to_move)
                        st.session_state.updated_tabs_layout = current_tabs_layout
                        st.rerun()
                    
                    if new_name != tab_name and new_name:
                        current_items_list = list(current_tabs_layout.items())
                        current_items_list[i] = (new_name, charts)
                        st.session_state.updated_tabs_layout = dict(current_items_list)
                        st.rerun()

                if st.button("➕ Adicionar Nova Aba", width='stretch'):
                    new_tab_name = f"Nova Aba {len(current_tabs_layout) + 1}"
                    current_tabs_layout[new_tab_name] = []
                    st.session_state.updated_tabs_layout = current_tabs_layout
                    st.rerun()
                
                st.divider()

                st.markdown("###### Atribuir Gráficos às Abas")
                
                all_charts_in_state = [chart for tab_charts in current_tabs_layout.values() for chart in tab_charts]

                if not all_charts_in_state:
                    st.info("Nenhum gráfico neste dashboard. Adicione um para começar a organizar.")
                    updated_chart_assignments = {}
                else:
                    updated_chart_assignments = {}
                    tab_options = list(current_tabs_layout.keys())
                    
                    for chart in all_charts_in_state:
                        chart_id = chart['id']
                        current_tab_in_state = next((tab for tab, charts in current_tabs_layout.items() if chart_id in [c['id'] for c in charts]), None)
                        
                        if current_tab_in_state is None:
                            if not tab_options: continue
                            current_tab_in_state = tab_options[0]

                        default_index = tab_options.index(current_tab_in_state)
                        
                        cols = st.columns([3, 2])
                        cols[0].write(f"📊 {chart.get('title', 'Gráfico sem título')}")
                        new_tab = cols[1].selectbox("Mover para a aba:", options=tab_options, index=default_index, key=f"select_tab_{chart_id}")
                        updated_chart_assignments[chart_id] = new_tab

                st.divider()

                if st.button("Salvar Alterações de Organização", type="primary", width='stretch'):
                    
                    final_tabs_layout = {name: [] for name in current_tabs_layout.keys()}
                    
                    for chart in all_charts_in_state:
                        assigned_tab = updated_chart_assignments.get(chart['id'])
                        if assigned_tab in final_tabs_layout:
                            final_tabs_layout[assigned_tab].append(chart)
                    
                    # --- SALVAMENTO NA FONTE CORRETA (LIVE SYNC) ---
                    user_to_save_data = find_user(target_save_email)
                    layouts_to_save = user_to_save_data.get('dashboard_layout', {})
                    
                    if current_project_key in layouts_to_save and active_dashboard_id in layouts_to_save[current_project_key]['dashboards']:
                         layouts_to_save[current_project_key]['dashboards'][active_dashboard_id]['tabs'] = final_tabs_layout
                         save_user_dashboard(target_save_email, layouts_to_save)
                         
                         if 'updated_tabs_layout' in st.session_state:
                             del st.session_state.updated_tabs_layout
                             
                         st.success(f"Organização salva com sucesso em '{target_save_email}'!")
                         st.rerun()
                    else:
                        st.error(f"Erro: Dashboard {active_dashboard_id} não encontrado no perfil de destino {target_save_email}.")
                                                
    with view_tab:
        render_dashboard_view(is_edit_mode=True)
        
else:
    if 'updated_tabs_layout' in st.session_state:
        del st.session_state.updated_tabs_layout
    
    render_dashboard_view(is_edit_mode=False)

# --- EXECUTOR DE SINAL ---
if st.session_state.get('needs_rerun', False):
    del st.session_state['needs_rerun']
    st.rerun()
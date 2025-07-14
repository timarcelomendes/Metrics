# pages/2_🏠_Meu_Dashboard.py

import streamlit as st
import pandas as pd
import os
from jira_connector import *
from metrics_calculator import *
from security import *
from utils import *
from config import *
from pathlib import Path

st.set_page_config(page_title="Meu Dashboard", page_icon="🏠", layout="wide")

st.markdown("""<style> ... </style>""", unsafe_allow_html=True) # Seu CSS aqui

def on_project_change():
    """Limpa o estado relevante ao trocar de projeto."""
    for key in ['dynamic_df', 'loaded_project_key', 'chart_to_edit']:
        if key in st.session_state:
            st.session_state.pop(key, None)

# --- Bloco de Autenticação e Conexão ---
if 'email' not in st.session_state:
    st.warning("⚠️ Por favor, faça login para aceder."); st.page_link("1_🔑_Login.py", label="Ir para Login", icon="🔑"); st.stop()

if 'jira_client' not in st.session_state or st.session_state.jira_client is None:
    user_data = find_user(st.session_state['email'])
    if user_data and user_data.get('encrypted_token'):
        with st.spinner("A conectar ao Jira..."):
            token = decrypt_token(user_data['encrypted_token'])
            client = connect_to_jira(user_data['jira_url'], user_data['jira_email'], token)
            if client:
                st.session_state.jira_client = client
                st.session_state.projects = get_projects(client)
                st.rerun()
            else:
                st.error("Falha na conexão com o Jira."); st.page_link("pages/6_👤_Minha_Conta.py", label="Verificar Credenciais", icon="👤"); st.stop()
    else:
        st.warning("Credenciais do Jira não configuradas."); st.page_link("pages/6_👤_Minha_Conta.py", label="Configurar Credenciais", icon="👤"); st.stop()

# --- BARRA LATERAL ---
with st.sidebar:
    project_root = Path(__file__).parent.parent
    logo_path = project_root / "images" / "gauge-logo.svg"
    try: st.image(str(logo_path), width=150)
    except: pass
    st.divider()
    st.markdown(f"Logado como: **{st.session_state.get('email', '')}**")
    st.header("Fonte de Dados")
    projects = st.session_state.get('projects', {})
    project_names = list(projects.keys())
    
    # Lógica para pré-selecionar o último projeto usado
    default_index = None
    if 'last_project_key' in st.session_state:
        project_name_map = {v: k for k, v in projects.items()}
        default_project_name = project_name_map.get(st.session_state['last_project_key'])
        if default_project_name in project_names:
            default_index = project_names.index(default_project_name)

    selected_project_name = st.selectbox("Selecione um Projeto", options=project_names, key="project_selector_dashboard", index=default_index, on_change=on_project_change, placeholder="Escolha um projeto...")
    
    if selected_project_name:
        if st.button("Visualizar / Atualizar Dashboard", use_container_width=True, type="primary"):
            project_key = projects[selected_project_name]
            st.session_state.project_key = project_key
            st.session_state.project_name = selected_project_name
            save_last_project(st.session_state['email'], project_key)
            
            with st.spinner(f"A carregar dados do projeto '{selected_project_name}'..."):
                issues = get_all_project_issues(st.session_state.jira_client, st.session_state.project_key)
                # (Lógica completa para processar 'issues' e criar a lista 'data')
                data = [] # Certifique-se que esta lógica está completa
                st.session_state.dynamic_df = pd.DataFrame(data)
                st.session_state.loaded_project_key = project_key
                st.rerun()

    if st.button("Logout", use_container_width=True):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.switch_page("1_🔑_Login.py")

# --- CONTEÚDO PRINCIPAL ---
st.header(f"🏠 Meu Dashboard: {st.session_state.get('project_name', 'Nenhum Projeto Carregado')}", divider='rainbow')

# Verifica se os dados carregados correspondem ao projeto selecionado na sidebar
if st.session_state.get('loaded_project_key') != st.session_state.get('project_key') and st.session_state.get('project_key'):
     st.info("⬅️ Clique em 'Visualizar / Atualizar Dashboard' na barra lateral para carregar os dados do projeto selecionado.")
     st.stop()

df = st.session_state.get('dynamic_df')
if df is None:
    st.info("⬅️ Na barra lateral, selecione um projeto e clique em 'Visualizar / Atualizar Dashboard' para começar.")
    st.stop()
if df.empty:
    st.warning(f"Nenhuma issue encontrada para o projeto **{st.session_state.project_name}**."); st.stop()
    
# Lógica de carregamento e exibição do dashboard por projeto
user_data = find_user(st.session_state['email'])
all_dashboards = user_data.get('dashboard_layout', {})
current_project_key = st.session_state.project_key
dashboard_items = all_dashboards.get(current_project_key, [])

with st.container(border=True):
    col1, col2 = st.columns([3, 1])
    with col1:
        st.metric("Visualizações no Dashboard", f"{len(dashboard_items)} / 12")
    with col2:
        use_two_columns = st.toggle("Layout com 2 Colunas", value=True, help="Ative para duas colunas, desative para uma.")
        num_columns = 2 if use_two_columns else 1

st.divider()

if not dashboard_items:
    st.info(f"O dashboard para o projeto **{st.session_state.project_name}** está vazio.")
    st.page_link("pages/3_🔬_Análise_Dinâmica.py", label="Criar a sua primeira visualização", icon="➕")
else:
    cols = st.columns(num_columns, gap="large")
    for i, chart_to_render in enumerate(list(dashboard_items)):
        with cols[i % num_columns]:
            with st.container(border=True):
                header_cols = st.columns([0.8, 0.1, 0.1])
                with header_cols[0]:
                    card_title = chart_to_render.get('title', 'Visualização'); card_icon = chart_to_render.get('icon', '📊')
                    st.markdown(f"##### {card_icon} {card_title}")
                with header_cols[1]:
                    if st.button("✏️", key=f"edit_{chart_to_render['id']}", help="Editar Visualização"):
                        st.session_state['chart_to_edit'] = chart_to_render; st.switch_page("pages/3_🔬_Análise_Dinâmica.py")
                with header_cols[2]:
                    if st.button("❌", key=f"del_{chart_to_render['id']}", help="Remover Visualização"):
                        all_dashboards[current_project_key] = [item for item in dashboard_items if item['id'] != chart_to_render['id']]
                        save_user_dashboard(st.session_state['email'], all_dashboards); st.rerun()
                render_chart(chart_to_render, df)
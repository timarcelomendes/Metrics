# pages/2_🏠_Meu_Dashboard.py

import streamlit as st
import pandas as pd
import os
from utils import render_chart, save_config, load_config
from config import *
from security import *
from jira_connector import *
from metrics_calculator import *

st.set_page_config(page_title="Meu Dashboard", page_icon="🏠", layout="wide")

def on_project_change():
    if 'dynamic_df' in st.session_state:
        del st.session_state['dynamic_df']

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
                st.session_state.jira_client = client; st.session_state.projects = get_projects(client); st.rerun()
            else: st.error("Falha na conexão com o Jira."); st.page_link("pages/6_👤_Minha_Conta.py", label="Verificar Credenciais", icon="👤"); st.stop()
    else: st.warning("Credenciais do Jira não configuradas."); st.page_link("pages/6_👤_Minha_Conta.py", label="Configurar Credenciais", icon="👤"); st.stop()

# --- BARRA LATERAL ---
with st.sidebar:
    logo_path = os.path.join(os.path.dirname(__file__), "..", "images", "gauge-logo.svg")
    try: st.image(logo_path, width=150)
    except: pass
    st.divider()
    st.markdown(f"Logado como: **{st.session_state.get('email', '')}**")
    st.header("Fonte de Dados")
    projects = st.session_state.get('projects', {})
    
    # Seletor de projeto sem on_change
    selected_project_name = st.selectbox(
        "Selecione um Projeto", options=list(projects.keys()), 
        key="project_selector_dashboard", 
        index=None,
        placeholder="Escolha um projeto..."
    )
    
    if st.button("Visualizar / Atualizar Dashboard", use_container_width=True, type="primary"):
        if selected_project_name:
            st.session_state.project_key = projects[selected_project_name]
            st.session_state.project_name = selected_project_name
            save_last_project(st.session_state['email'], st.session_state.project_key)
            
            with st.spinner(f"A carregar dados do projeto '{selected_project_name}'..."):
                issues = get_all_project_issues(st.session_state.jira_client, st.session_state.project_key)
                # Lógica completa de processamento de dados para criar a variável 'data'
                data = []; 
                selected_standard_fields = load_config(STANDARD_FIELDS_FILE, [])
                custom_fields_to_fetch = load_config(CUSTOM_FIELDS_FILE, [])
                AVAILABLE_STANDARD_FIELDS_LOCAL = st.session_state.get('available_standard_fields', {})
                for i in issues:
                    completion_date = find_completion_date(i)
                    issue_data = {'Issue': i.key, 'Data de Criação': pd.to_datetime(i.fields.created).tz_localize(None),'Data de Conclusão': completion_date, 'Mês de Conclusão': completion_date.strftime('%Y-%m') if completion_date else None, 'Lead Time (dias)': calculate_lead_time(i), 'Cycle Time (dias)': calculate_cycle_time(i), 'Tipo de Issue': i.fields.issuetype.name, 'Responsável': i.fields.assignee.displayName if i.fields.assignee else 'Não atribuído', 'Criado por': i.fields.reporter.displayName if i.fields.reporter else 'N/A', 'Status': i.fields.status.name, 'Prioridade': i.fields.priority.name if i.fields.priority else 'N/A', 'Story Points': getattr(i.fields, STORY_POINTS_FIELD_ID, 0) or 0, 'Labels': ', '.join(i.fields.labels) if i.fields.labels else 'Nenhum'}
                    for field_name in selected_standard_fields:
                        field_id = AVAILABLE_STANDARD_FIELDS_LOCAL.get(field_name)
                        if field_id:
                            value = getattr(i.fields, field_id, None)
                            if isinstance(value, list): issue_data[field_name] = ', '.join([getattr(v, 'name', str(v)) for v in value]) if value else 'Nenhum'
                            elif hasattr(value, 'name'): issue_data[field_name] = value.name
                            elif value: issue_data[field_name] = str(value).split('T')[0]
                            else: issue_data[field_name] = 'N/A'
                    for field in custom_fields_to_fetch:
                        field_name, field_id = field['name'], field['id']
                        value = getattr(i.fields, field_id, None)
                        if hasattr(value, 'displayName'): issue_data[field_name] = value.displayName
                        elif hasattr(value, 'value'): issue_data[field_name] = value.value
                        elif value is not None: issue_data[field_name] = str(value)
                        else: issue_data[field_name] = 'N/A'
                    data.append(issue_data)
                st.session_state.dynamic_df = pd.DataFrame(data)
                st.session_state.loaded_project_key = st.session_state.project_key
                st.rerun()
        else:
            st.warning("Por favor, selecione um projeto primeiro.")

# --- CONTEÚDO PRINCIPAL ---
st.header("🏠 Meu Dashboard Personalizado")

df = st.session_state.get('dynamic_df')
if df is None:
    st.info("⬅️ Na barra lateral, selecione um projeto e clique em 'Visualizar / Atualizar Dashboard' para começar.")
    st.stop()

# Limpa o estado de 'edição' ao entrar nesta página
if 'chart_to_edit' in st.session_state:
    del st.session_state['chart_to_edit']
    
st.caption(f"A exibir visualizações para o projeto: **{st.session_state.get('project_name', 'Nenhum')}**.")
st.session_state.dashboard_items = load_config(DASHBOARD_LAYOUT_FILE, [])
dashboard_items = st.session_state.dashboard_items

col1, col2 = st.columns([3, 1])
with col1: st.caption(f"Exibindo {len(dashboard_items)} de um máximo de 12 visualizações.")
with col2: num_columns = st.radio("Nº de Colunas:", [1, 2], index=1, horizontal=True)
st.divider()

if not dashboard_items:
    st.info("O seu dashboard está vazio.")
    st.page_link("pages/7_🔬_Análise_Dinâmica.py", label="Criar a sua primeira visualização", icon="➕")
else:
    cols = st.columns(num_columns)
    for i, chart_to_render in enumerate(list(dashboard_items)):
        with cols[i % num_columns]:
            with st.container(border=True):
                # --- LAYOUT DO CARTÃO ATUALIZADO COM BOTÃO DE EDIÇÃO ---
                header_cols = st.columns([0.8, 0.1, 0.1])
                with header_cols[0]:
                    card_title = chart_to_render.get('title', 'Visualização'); card_icon = chart_to_render.get('icon', '📊')
                    st.markdown(f"**{card_icon} {card_title}**")
                
                with header_cols[1]:
                    if st.button("✏️", key=f"edit_{chart_to_render['id']}", help="Editar Gráfico"):
                        st.session_state['chart_to_edit'] = chart_to_render
                        st.switch_page("pages/7_🔬_Análise_Dinâmica.py")

                with header_cols[2]:
                    if st.button("❌", key=f"del_{chart_to_render['id']}", help="Remover Gráfico"):
                        st.session_state.dashboard_items = [item for item in st.session_state.dashboard_items if item['id'] != chart_to_render['id']]
                        save_config(st.session_state.dashboard_items, DASHBOARD_LAYOUT_FILE); st.rerun()
                
                render_chart(chart_to_render, df)
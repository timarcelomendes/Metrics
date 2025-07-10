# pages/5_📈_Forecast_de_Projetos.py

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np
import os
from jira_connector import *
from metrics_calculator import *
from security import *
from utils import *
from pathlib import Path

st.set_page_config(page_title="Forecast de Projetos", page_icon="📈", layout="wide")

# --- BLOCO DE AUTENTICAÇÃO E CONEXÃO ---
if 'email' not in st.session_state:
    st.warning("⚠️ Por favor, faça login para aceder."); st.page_link("1_🔑_Login.py", label="Ir para Login", icon="🔑"); st.stop()
if 'jira_client' not in st.session_state:
    user_data = find_user(st.session_state['email'])
    if user_data and user_data.get('encrypted_token'):
        with st.spinner("A conectar ao Jira..."):
            token = decrypt_token(user_data['encrypted_token'])
            client = connect_to_jira(user_data['jira_url'], user_data['jira_email'], token)
            if client:
                st.session_state.jira_client = client; st.session_state.projects = get_projects(client)
                st.rerun()
            else:
                st.error("Falha na conexão com o Jira."); st.page_link("pages/6_👤_Minha_Conta.py", label="Verificar Credenciais", icon="👤"); st.stop()
    else:
        st.warning("Credenciais do Jira não configuradas."); st.page_link("pages/6_👤_Minha_Conta.py", label="Configurar Credenciais", icon="👤"); st.stop()

def on_project_change():
    for key in ['view_to_show', 'selected_scope', 'team_size']:
        if key in st.session_state:
            st.session_state[key] = None

# --- BARRA LATERAL ---
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
    
    st.header("Configurações de Análise")
    projects = st.session_state.get('projects', {})
    project_names = list(projects.keys())
    default_index = project_names.index(st.session_state.get('project_name')) if st.session_state.get('project_name') in project_names else None
    
    selected_project_name = st.selectbox("1. Selecione o Projeto", options=project_names, key="project_selector_forecast", index=default_index, on_change=on_project_change, placeholder="Escolha um projeto...")
    
    if selected_project_name:
        st.session_state.project_key = projects[selected_project_name]
        st.session_state.project_name = selected_project_name
        
        with st.expander("2. Opções de Análise", expanded=True):
            versions = get_fix_versions(st.session_state.jira_client, st.session_state.project_key)
            
            scope_options = {"— Projeto Inteiro —": "full_project"}
            if versions:
                for v in sorted(versions, key=lambda x: (not x.released, x.name)):
                    scope_options[f"{v.name} ({'Lançada' if v.released else 'Não Lançada'})"] = v
            
            selected_scope_name = st.selectbox("2. Selecione o Escopo da Análise", options=list(scope_options.keys()))
            
            if selected_scope_name:
                st.session_state.selected_scope = scope_options[selected_scope_name]
                st.session_state.unit_selector = st.radio("Unidade de Análise", ["Story Points", "Contagem de Issues"], horizontal=True)
                st.session_state.team_size = st.number_input("Tamanho da Equipa (pessoas)", min_value=1, value=st.session_state.get('team_size', 1))
                
                if st.button("Analisar Escopo", use_container_width=True, type="primary"):
                    st.session_state.view_to_show = 'forecast_view'

    if st.button("Logout", use_container_width=True):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.switch_page("1_🔑_Login.py")

# --- LÓGICA PRINCIPAL DA PÁGINA ---
st.header("📈 Forecast & Planeamento de Entregas", divider='rainbow')

if st.session_state.get('view_to_show') != 'forecast_view':
    st.info("⬅️ Na barra lateral, selecione um projeto, um escopo e clique em 'Analisar Escopo' para começar.")
    st.stop()

@st.cache_data
def load_and_process_forecast_data(project_key, scope, unit, team_size):
    scope_name_for_title = ""
    if scope == "full_project":
        issues = get_all_project_issues(st.session_state.jira_client, project_key)
        scope_name_for_title = f"Projeto {st.session_state.project_name} (Completo)"
    else:
        issues = get_issues_by_fix_version(st.session_state.jira_client, project_key, scope.id)
        scope_name_for_title = scope.name

    unit_param = 'points' if unit == 'Story Points' else 'count'
    burnup_df = prepare_project_burnup_data(issues, unit_param)
    
    if burnup_df.empty: return None, None, None, None, None, None
        
    df_trend, forecast_date, weekly_velocity = calculate_trend_and_forecast(burnup_df, 4)
    throughput_per_person = weekly_velocity / team_size if team_size > 0 else 0
    
    return burnup_df, df_trend, forecast_date, weekly_velocity, throughput_per_person, scope_name_for_title

scope = st.session_state.selected_scope
unit = st.session_state.unit_selector
team_size = st.session_state.team_size
burnup_df, df_trend, forecast_date, weekly_velocity, throughput_per_person, scope_name = load_and_process_forecast_data(st.session_state.project_key, scope, unit, team_size)

if burnup_df is None:
    st.error("Não foi possível gerar a análise. Pode não haver issues ou dados suficientes no escopo selecionado.")
    st.stop()
    
unit_param = "pts" if unit == 'Story Points' else 'issues'

tab1, tab2 = st.tabs(["Burnup & Previsão de Data", "Planeamento de Vazão"])

with tab1:
    st.subheader("Indicadores Chave de Progresso")
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    current_scope = burnup_df['Escopo Total'].iloc[-1]; completed_work = burnup_df['Trabalho Concluído'].iloc[-1]
    kpi1.metric("📦 Escopo Total", f"{current_scope:.0f} {unit_param}")
    kpi2.metric("✅ Concluído", f"{completed_work:.0f} ({(completed_work/current_scope)*100:.0f}%)" if current_scope > 0 else "0%")
    kpi3.metric("🚀 Velocidade Semanal", f"{weekly_velocity:.1f} {unit_param}/semana")
    if forecast_date: kpi4.metric("🎯 Previsão de Entrega", forecast_date.strftime('%d/%m/%Y'))
    else: kpi4.metric("🎯 Previsão de Entrega", "Incalculável")
        
    st.divider()
    st.subheader(f"Gráfico de Burnup: {scope_name}")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=burnup_df.index, y=burnup_df['Escopo Total'], mode='lines', name='Escopo Total', line=dict(color='red', width=2)))
    fig.add_trace(go.Scatter(x=burnup_df.index, y=burnup_df['Trabalho Concluído'], mode='lines', name='Trabalho Concluído', line=dict(color='blue', width=3)))
    if df_trend is not None:
        fig.add_trace(go.Scatter(x=df_trend.index, y=df_trend['Tendência'], mode='lines', name='Tendência', line=dict(color='green', dash='dash')))
    
    # --- CORREÇÃO AQUI ---
    fig.update_layout(title=None, xaxis_title="Data", yaxis_title=unit, legend_title="Legenda", template="plotly_white")
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.subheader("Qual a vazão necessária para atingir uma data?")
    remaining_work = current_scope - completed_work
    target_date = st.date_input("Data de Entrega Desejada", value=forecast_date if forecast_date else datetime.now() + timedelta(weeks=4), min_value=datetime.now().date())
    if target_date:
        remaining_weeks = (target_date - datetime.now().date()).days / 7
        if remaining_weeks > 0:
            required_velocity = remaining_work / remaining_weeks
            st.divider()
            col1, col2, col3 = st.columns(3)
            col1.metric(f"🏁 Trabalho Restante", f"{remaining_work:.1f} {unit_param}")
            col2.metric("🗓️ Semanas Restantes", f"{remaining_weeks:.1f} semanas")
            col3.metric("⚡ Vazão Semanal Necessária", f"{required_velocity:.1f} {unit_param}/semana", delta=f"{required_velocity - weekly_velocity:.1f} vs. atual", delta_color="inverse")
            if throughput_per_person > 0:
                required_team_size = required_velocity / throughput_per_person
                st.divider()
                st.subheader("Análise da Equipa")
                st.info(f"Considerando a produtividade média histórica de **{throughput_per_person:.1f} {unit_param}/pessoa/semana**:")
                st.metric("👩‍💻 Pessoas Necessárias para Atingir a Meta", f"{np.ceil(required_team_size):.0f} pessoas", delta=f"{np.ceil(required_team_size) - team_size:.0f} vs. equipa atual")
        else:
            st.error("A data de entrega desejada deve ser no futuro.")
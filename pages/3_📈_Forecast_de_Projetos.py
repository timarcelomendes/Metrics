# pages/3_📈_Forecast_de_Projetos.py

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
from jira_connector import *
from metrics_calculator import *
from security import find_user, decrypt_token
from sklearn.linear_model import LinearRegression

st.set_page_config(page_title="Forecast de Projetos", page_icon="📈", layout="wide")

# --- CORREÇÃO: Definindo o container principal ---
main_content = st.container()

# --- Função de Callback ---
def on_project_change():
    keys_to_clear = ['view_to_show', 'selected_version']
    for key in keys_to_clear:
        if key in st.session_state: st.session_state[key] = None

# --- Função de Display Principal ---
def display_burnup_forecast():
    st.header("📈 Burnup de Projeto & Previsão de Entrega")
    version = st.session_state.get('selected_version')
    if version is None: 
        st.info("⬅️ Por favor, selecione os parâmetros na barra lateral e clique em 'Gerar Gráfico'.")
        return
        
    with st.spinner("Analisando o progresso do projeto..."):
        issues = get_issues_by_fix_version(st.session_state.jira_client, st.session_state.project_key, version.id)
        unit = st.session_state.get('unit_selector', 'Contagem de Issues')
        trend_weeks = st.session_state.get('trend_slider', 4)
        unit_param = 'points' if unit == 'Story Points' else 'count'
        burnup_df = prepare_project_burnup_data(issues, unit_param)
        df_trend, forecast_date, weekly_velocity = calculate_trend_and_forecast(burnup_df, trend_weeks)

    if burnup_df.empty:
        st.error("Não foi possível gerar o gráfico. Pode não haver issues ou dados suficientes na versão selecionada."); return

    st.subheader("Indicadores Chave de Progresso")
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    current_scope = burnup_df['Escopo Total'].iloc[-1]
    completed_work = burnup_df['Trabalho Concluído'].iloc[-1]
    
    kpi1.metric("📦 Escopo Total", f"{current_scope:.0f} {unit_param.replace('_', ' ').title()}")
    kpi2.metric("✅ Concluído", f"{completed_work:.0f} ({(completed_work/current_scope)*100:.0f}%)" if current_scope > 0 else "0%")
    kpi3.metric("🚀 Velocidade Semanal", f"{weekly_velocity:.1f} {unit_param.replace('_', ' ').title()}/semana")
    if forecast_date:
        kpi4.metric("🎯 Previsão de Entrega", forecast_date.strftime('%d/%m/%Y'))
    else:
        kpi4.metric("🎯 Previsão de Entrega", "Incalculável")
        
    st.divider()
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=burnup_df.index, y=burnup_df['Escopo Total'], mode='lines', name='Escopo Total', line=dict(color='red', width=2)))
    fig.add_trace(go.Scatter(x=burnup_df.index, y=burnup_df['Trabalho Concluído'], mode='lines', name='Trabalho Concluído', line=dict(color='blue', width=3)))
    if df_trend is not None:
        fig.add_trace(go.Scatter(x=df_trend.index, y=df_trend['Tendência'], mode='lines', name='Tendência', line=dict(color='green', dash='dash')))
        
    fig.update_layout(title=f"Burnup do Projeto: {version.name}", xaxis_title="Data", yaxis_title=unit, legend_title="Legenda")
    st.plotly_chart(fig, use_container_width=True)

# --- LÓGICA DA PÁGINA ---
if 'email' not in st.session_state:
    st.warning("Por favor, faça login primeiro na página principal.")
    st.page_link("1_⚙️_Configurações.py", label="Ir para Login", icon="🔑")
    st.stop()

if 'jira_client' not in st.session_state:
    user_data = find_user(st.session_state['email'])
    if user_data and user_data.get('encrypted_token'):
        with st.spinner("A conectar ao Jira com as suas credenciais..."):
            token = decrypt_token(user_data['encrypted_token'])
            client = connect_to_jira(user_data['jira_url'], user_data['jira_email'], token)
            if client:
                st.session_state.jira_client = client
                st.session_state.projects = get_projects(client)
            else:
                st.error("Não foi possível conectar ao Jira com as suas credenciais guardadas. Por favor, verifique-as na página 'Minha Conta'.")
                st.page_link("pages/5_👤_Minha_Conta.py", label="Verificar Credenciais", icon="👤")
                st.stop()
    else:
        st.warning("Credenciais do Jira não encontradas. Por favor, adicione-as na página 'Minha Conta'.")
        st.page_link("pages/5_👤_Minha_Conta.py", label="Configurar Credenciais", icon="👤")
        st.stop()

with st.sidebar:
    try: st.image("images/gauge-logo.png", width=150)
    except Exception: st.write("Gauge Metrics")
    st.divider()
    
    st.markdown("#### 1. Selecione o Projeto")
    projects = st.session_state.get('projects', {})
    project_name = st.selectbox("Selecione um Projeto", options=list(projects.keys()), key="project_selector_forecast", on_change=on_project_change, index=None, placeholder="Escolha um projeto...", label_visibility="collapsed")
    
    if project_name:
        st.session_state.project_key = projects.get(project_name)
        st.session_state.project_name = project_name
        
        with st.expander("2. Opções de Forecast", expanded=True):
            versions = get_fix_versions(st.session_state.jira_client, st.session_state.project_key)
            if versions:
                version_options = {f"{v.name} ({'Lançada' if v.released else 'Não Lançada'})": v for v in sorted(versions, key=lambda x: (x.released, x.name))}
                selected_version_display_name = st.selectbox("Versão (Fix Version)", options=version_options.keys(), key="version_selector", index=None, placeholder="Escolha uma versão...")
                if selected_version_display_name:
                    st.session_state.selected_version = version_options.get(selected_version_display_name)
                    st.session_state.unit_selector = st.radio("Unidade", ["Story Points", "Contagem de Issues"], horizontal=True)
                    st.session_state.trend_slider = st.slider("Semanas para Tendência", 2, 12, 4)
                    if st.button("Gerar Gráfico Burnup", use_container_width=True, type="primary"):
                        st.session_state.view_to_show = 'burnup_display'
            else: st.warning("Nenhuma 'Fix Version' encontrada para este projeto.")

with main_content:
    if st.session_state.get('jira_client'):
        st.caption(f"Conectado como: {st.session_state.get('email', '')}")

    if st.session_state.get('view_to_show') == 'burnup_display':
        display_burnup_forecast()
    else:
        if st.session_state.get('project_key'):
            st.info("⬅️ Por favor, selecione os parâmetros na barra lateral e clique em 'Gerar Gráfico Burnup'.")
        else:
            st.info("⬅️ Por favor, comece por selecionar um projeto na barra lateral.")
# pages/4_📈_Forecast_de_Projetos.py

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

# --- CSS para ajustar o tamanho dos KPIs ---
st.markdown("""
<style>
[data-testid="stMetricLabel"] {
    font-size: 0.95em !important;
}
[data-testid="stMetricValue"] {
    font-size: 1.75em !important;
}
</style>
""", unsafe_allow_html=True)

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
                st.session_state.jira_client = client; st.session_state.projects = get_projects(client); st.rerun()
            else:
                st.error("Falha na conexão com o Jira."); st.page_link("pages/6_👤_Minha_Conta.py", label="Verificar Credenciais", icon="👤"); st.stop()
    else:
        st.warning("Credenciais do Jira não configuradas."); st.page_link("pages/6_👤_Minha_Conta.py", label="Configurar Credenciais", icon="👤"); st.stop()

def on_project_change():
    for key in ['view_to_show', 'selected_scope', 'team_size']:
        if key in st.session_state:
            st.session_state.pop(key, None)

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
                st.session_state.selected_scope_object = scope_options[selected_scope_name]
                st.session_state.unit_selector = st.radio("Unidade de Análise", ["Story Points", "Contagem de Issues"], horizontal=True)
                
                if 'team_size' not in st.session_state or st.session_state.team_size is None:
                    st.session_state.team_size = 1
                st.number_input("Tamanho da Equipa (pessoas)", min_value=1, key='team_size')
                st.session_state.trend_slider = st.slider("Semanas para Tendência", 2, 12, 4, help="Número de semanas recentes a considerar para a linha de tendência.")

                if st.button("Analisar Escopo", use_container_width=True, type="primary"):
                    st.session_state.view_to_show = 'forecast_view'

    if st.button("Logout", use_container_width=True):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.switch_page("1_🔑_Login.py")
    
# --- LÓGICA PRINCIPAL DA PÁGINA ---
st.header("📈 Forecast & Planeamento de Entregas", divider='rainbow')

if st.session_state.get('view_to_show') != 'forecast_view':
    st.info("⬅️ Na barra lateral, selecione os parâmetros e clique em 'Analisar Escopo' para começar.")
    st.stop()

@st.cache_data (show_spinner="Carregando os dados")
def load_and_process_forecast_data(project_key, scope_id, unit, team_size, trend_weeks):
    # Garante que team_size nunca seja nulo para os cálculos
    team_size = team_size or 1

    if scope_id == "full_project":
        issues = get_all_project_issues(st.session_state.jira_client, project_key)
    else: # É um ID de versão
        issues = get_issues_by_fix_version(st.session_state.jira_client, project_key, scope_id)

    unit_param = 'points' if unit == 'Story Points' else 'count'
    burnup_df = prepare_project_burnup_data(issues, unit_param)
    
    # --- CORREÇÃO AQUI ---
    # Se o dataframe estiver vazio, retorna uma tupla com 6 valores padrão
    if burnup_df.empty:
        return None, None, None, 0, 0, 0

    df_trend, forecast_date, trend_velocity, avg_velocity = calculate_trend_and_forecast(burnup_df, trend_weeks)
    
    throughput_per_person = avg_velocity / team_size if team_size > 0 else 0
    
    return burnup_df, df_trend, forecast_date, trend_velocity, avg_velocity, throughput_per_person

scope_obj = st.session_state.selected_scope_object
unit = st.session_state.unit_selector
team_size = st.session_state.team_size
trend_weeks = st.session_state.trend_slider

if scope_obj == "full_project":
    scope_id_for_cache = "full_project"
    scope_name_for_title = f"Projeto {st.session_state.project_name} (Completo)"
else:
    scope_id_for_cache = scope_obj.id
    scope_name_for_title = scope_obj.name

burnup_df, df_trend, forecast_date, trend_velocity, avg_velocity, throughput_per_person = load_and_process_forecast_data(
    st.session_state.project_key, scope_id_for_cache, unit, team_size, trend_weeks
)

if burnup_df is None:
    st.error("Não foi possível gerar a análise. Pode não haver issues ou dados suficientes no escopo selecionado.")
    st.stop()
    
unit_param = "pts" if unit == 'Story Points' else ' issues'

tab1, tab2 = st.tabs(["Burnup & Previsão de Data", "Planeamento de Vazão"])

with tab1:
    st.subheader("Indicadores Chave de Progresso")
    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
    current_scope = burnup_df['Escopo Total'].iloc[-1]; completed_work = burnup_df['Trabalho Concluído'].iloc[-1]
    
    kpi1.metric("📦 Escopo Total", f"{current_scope:.0f}{unit_param}")
    kpi2.metric("✅ Concluído", f"{completed_work:.0f} ({((completed_work/current_scope)*100):.0f}%)" if current_scope > 0 else "0%")
    kpi3.metric("Velocidade Média", f"{avg_velocity:.1f} {unit_param}/sem", help="Média de entrega em todo o histórico do escopo.")
    kpi4.metric(f"Tendência ({trend_weeks} sem.)", f"{trend_velocity:.1f} {unit_param}/sem", help=f"Velocidade baseada apenas nas últimas {trend_weeks} semanas.")
    if forecast_date: kpi5.metric("🎯 Previsão de Entrega", forecast_date.strftime('%d/%m/%Y'), help=f"Baseado na tendência das últimas {trend_weeks} semanas.")
    else: kpi5.metric("🎯 Previsão de Entrega", "Incalculável")
        
    st.divider()
    st.subheader(f"Gráfico de Burnup: {scope_name_for_title}")
    
    fig = go.Figure()
    
    # --- CORREÇÃO AQUI ---
    # Garante que a variável exista antes de ser usada
    burnup_df_cleaned = burnup_df.dropna()
    
    fig.add_trace(go.Scatter(x=burnup_df_cleaned.index, y=burnup_df_cleaned['Escopo Total'], mode='lines', name='Escopo Total', line=dict(color='red', width=2)))
    fig.add_trace(go.Scatter(x=burnup_df_cleaned.index, y=burnup_df_cleaned['Trabalho Concluído'], mode='lines', name='Trabalho Concluído', line=dict(color='blue', width=3)))
    if df_trend is not None:
        df_trend_cleaned = df_trend.dropna()
        if not df_trend_cleaned.empty:
            fig.add_trace(go.Scatter(x=df_trend_cleaned.index, y=df_trend_cleaned['Tendência'], mode='lines', name='Tendência', line=dict(color='green', dash='dash')))
            
    fig.update_layout(title_text="", xaxis_title="Data", yaxis_title=unit, legend_title="Legenda", template="plotly_white")
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.subheader("Qual a vazão necessária para atingir uma data?")
    st.caption("Use esta ferramenta para simular cenários. Se definirmos uma data de entrega, qual o ritmo que a equipa precisa de ter?")
    
    remaining_work = current_scope - completed_work
    target_date = st.date_input("Data de Entrega Desejada", value=forecast_date if forecast_date else datetime.now() + timedelta(weeks=4), min_value=datetime.now().date())
    
    if target_date:
        remaining_weeks = (datetime.combine(target_date, datetime.min.time()) - datetime.now()).days / 7
        if remaining_weeks > 0:
            required_velocity = remaining_work / remaining_weeks
            st.divider()
            col1, col2, col3 = st.columns(3)
            col1.metric(f"🏁 Trabalho Restante", f"{remaining_work:.1f}{unit_param}")
            col2.metric("🗓️ Semanas Restantes", f"{remaining_weeks:.1f} semanas")
            col3.metric("⚡ Vazão Necessária", f"{required_velocity:.1f} {unit_param}/sem", delta=f"{required_velocity - avg_velocity:.1f} vs. média", delta_color="inverse")
                    
            st.divider()
            st.subheader("Análise da Equipa")
            
            # --- NOVO SELETOR PARA A BASE DA PROJEÇÃO ---
            projection_basis = st.radio(
                "Base para projeção da equipa:",
                ("Velocidade Média (Histórico Total)", f"Tendência ({trend_weeks} semanas)"),
                horizontal=True,
                help="Escolha qual velocidade usar para estimar a produtividade por pessoa."
            )
            
            # Determina qual velocidade usar com base na seleção
            velocity_for_projection = avg_velocity if "Média" in projection_basis else trend_velocity
            basis_text = "média histórica" if "Média" in projection_basis else "tendência recente"

            if velocity_for_projection > 0:
                throughput_per_person = velocity_for_projection / team_size
                required_team_size = required_velocity / throughput_per_person if throughput_per_person > 0 else float('inf')
                
                st.info(f"Considerando a produtividade da **{basis_text}** de **{throughput_per_person:.1f} {unit_param}/pessoa/semana**:")
                st.metric(
                    "👩‍💻 Pessoas Necessárias para Atingir a Meta",
                    f"{np.ceil(required_team_size):.0f} pessoas",
                    delta=f"{np.ceil(required_team_size) - team_size:.0f} vs. equipa atual"
                )
            else:
                st.warning("Não é possível estimar a equipa necessária.", icon="⚠️")
                st.info(f"A base de cálculo selecionada ('{basis_text}') é zero ou negativa. Não é possível estimar a produtividade por pessoa.")
        else:
            st.error("A data de entrega desejada deve ser no futuro.")
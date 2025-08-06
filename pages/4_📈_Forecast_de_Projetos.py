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

# --- LÓGICA PRINCIPAL DA PÁGINA ---
st.header("📈 Forecast & Planeamento de Entregas", divider='rainbow')

if 'email' not in st.session_state:
    st.warning("⚠️ Por favor, faça autenticação para acessar esta página."); st.page_link("1_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑"); st.stop()

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

    if st.session_state.get("email"):
        st.markdown(f"🔐 Logado como: **{st.session_state['email']}**")
    else:
        st.info("⚠️ Usuário não conectado!")    
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
                
                # --- LÓGICA PARA USAR O CAMPO DE ESTIMATIVA CONFIGURADO ---
                project_config = get_project_config(st.session_state.project_key) or {}
                estimation_config = project_config.get('estimation_field', {})
                estimation_field_name = estimation_config.get('name')
                unit_options = [estimation_field_name, "Contagem de Issues"] if estimation_field_name else ["Contagem de Issues"]

                st.session_state.unit_selector = st.radio("Unidade de Análise", options=unit_options, horizontal=True)
                st.session_state.trend_slider = st.slider("Semanas para Tendência", 2, 12, 4)
                
                if st.button("Analisar Escopo", use_container_width=True, type="primary"):
                    st.session_state.view_to_show = 'forecast_view'

    if st.button("Logout", use_container_width=True, type='secondary'):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.switch_page("1_🔑_Autenticação.py")
    
if st.session_state.get('view_to_show') != 'forecast_view':
    st.info("⬅️ Na barra lateral, selecione os parâmetros e clique em 'Analisar Escopo' para começar.")
    st.stop()

@st.cache_data (show_spinner="Carregando os dados")
def load_and_process_forecast_data(project_key, scope_id, unit, team_size, trend_weeks, estimation_config):
    unit_param = 'count' # Padrão
    if unit != 'Contagem de Issues':
        unit_param = 'points'
    
    issues = get_all_project_issues(st.session_state.jira_client, project_key) if scope_id == "full_project" else get_issues_by_fix_version(st.session_state.jira_client, project_key, scope_id)
    burnup_df = prepare_project_burnup_data(issues, unit_param, estimation_config)
    if burnup_df.empty: return None, None, None, 0, 0, 0
    df_trend, forecast_date, trend_velocity, avg_velocity = calculate_trend_and_forecast(burnup_df, trend_weeks)
    safe_team_size = team_size or 1
    throughput_per_person = avg_velocity / safe_team_size if avg_velocity > 0 and safe_team_size > 0 else 0
    return burnup_df, df_trend, forecast_date, trend_velocity, avg_velocity, throughput_per_person

scope_obj = st.session_state.selected_scope_object
unit = st.session_state.unit_selector
team_size = st.session_state.team_size
trend_weeks = st.session_state.trend_slider
project_config = get_project_config(st.session_state.project_key) or {}
estimation_config = project_config.get('estimation_field', {})
scope_id_for_cache = "full_project" if scope_obj == "full_project" else scope_obj.id
scope_name_for_title = f"Projeto {st.session_state.project_name} (Completo)" if scope_obj == "full_project" else scope_obj.name

burnup_df, df_trend, forecast_date, trend_velocity, avg_velocity, throughput_per_person = load_and_process_forecast_data(st.session_state.project_key, scope_id_for_cache, unit, team_size, trend_weeks, estimation_config)
if burnup_df is None:
    st.error("Não foi possível gerar a análise. Pode não haver issues ou dados suficientes no escopo selecionado."); st.stop()

unit = st.session_state.unit_selector
estimation_config = project_config.get('estimation_field', {})

unit_display = " itens" # Padrão para "Contagem de Issues"
if unit != 'Contagem de Issues':
    if estimation_config.get('source') == 'standard_time':
        unit_display = 'hs' # Para Horas
    else: # Para qualquer outro campo numérico, como Story Points
        unit_display = 'pts'

tab1, tab2 = st.tabs(["Burnup & Previsão de Data", "Planeamento de Vazão"])

with tab1:
    st.subheader("Indicadores Chave de Progresso")
    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
    current_scope = burnup_df['Escopo Total'].iloc[-1]; completed_work = burnup_df['Trabalho Concluído'].iloc[-1]
    
    # --- KPIs ATUALIZADOS COM A NOVA FORMATAÇÃO ---
    kpi1.metric("📦 Escopo Total", f"{current_scope:.0f}{unit_display}")
    kpi2.metric("✅ Concluído", f"{completed_work:.0f} ({((completed_work/current_scope)*100):.0f}%)" if current_scope > 0 else "0%")
    kpi3.metric("Velocidade Média", f"{avg_velocity:.1f} {unit_display}/sem", help="Média de entrega em todo o histórico do escopo.")
    kpi4.metric(f"Tendência ({trend_weeks} sem.)", f"{trend_velocity:.1f} {unit_display}/sem", help=f"Velocidade baseada apenas nas últimas {trend_weeks} semanas.")
    if forecast_date: kpi5.metric("🎯 Previsão de Entrega", forecast_date.strftime('%d/%m/%Y'), help=f"Baseado na tendência das últimas {trend_weeks} semanas.")
    else: kpi5.metric("🎯 Previsão de Entrega", "Incalculável")
        
    st.divider()
    st.subheader(f"Gráfico de Burnup: {scope_name_for_title}")
    
    fig = go.Figure()
    
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

        # ===== NOVA SECÇÃO: RESUMO COM IA =====
    st.divider()
    with st.expander("🤖 Resumo Executivo com IA"):
        st.info("Clique no botão abaixo para que a IA analise os indicadores e o gráfico de burnup, e gere um resumo executivo sobre a saúde e previsibilidade do projeto.")
        
        if st.button("Gerar Resumo com IA", use_container_width=True):
            with st.spinner("A IA está a analisar o seu forecast..."):
                forecast_date_str = forecast_date.strftime('%d/%m/%Y') if forecast_date else "Incalculável"
                
                ai_summary = get_ai_forecast_analysis(
                    project_name=st.session_state.get('project_name', 'este projeto'),
                    scope_total=f"{burnup_df['Escopo Total'].iloc[-1]:.0f} {unit_display}",
                    completed_pct=f"{(burnup_df['Trabalho Concluído'].iloc[-1] / burnup_df['Escopo Total'].iloc[-1]) * 100:.0f}",
                    avg_velocity=avg_velocity,
                    trend_velocity=trend_velocity,
                    forecast_date_str=forecast_date_str
                )
                st.session_state.ai_forecast_summary = ai_summary
        
        if 'ai_forecast_summary' in st.session_state:
            st.markdown(st.session_state.ai_forecast_summary)

with tab2:
    st.subheader("Qual a vazão necessária para atingir uma data?")
    st.caption("Use esta ferramenta para simular cenários. Se definirmos uma data de entrega, qual o ritmo que a equipe precisa de ter?")
    
    # Adiciona o input para o tamanho da equipe, que estava em falta na sua versão
    team_size = st.number_input("Tamanho da Equipe Atual", min_value=1, value=5)

    remaining_work = current_scope - completed_work
    target_date = st.date_input("Data de Entrega Desejada", value=forecast_date if forecast_date else datetime.now() + timedelta(weeks=4), min_value=datetime.now().date())
    
    if target_date:
        remaining_weeks = (datetime.combine(target_date, datetime.min.time()) - datetime.now()).days / 7
        if remaining_weeks > 0:
            required_velocity = remaining_work / remaining_weeks
            st.divider()
            col1, col2, col3 = st.columns(3)
            col1.metric(f"🏁 Trabalho Restante", f"{remaining_work:.1f} {unit_display}")
            col2.metric("🗓️ Semanas Restantes", f"{remaining_weeks:.1f} semanas")
            col3.metric("⚡ Vazão Necessária", f"{required_velocity:.1f} {unit_display}/sem", delta=f"{required_velocity - avg_velocity:.1f} vs. média")
            
            st.divider()
            st.subheader("Análise da Equipe")
            
            projection_basis = st.radio(
                "Base para projeção da equipe:",
                ("Velocidade Média (Histórico Total)", f"Tendência ({trend_weeks} semanas)"),
                horizontal=True
            )
            
            velocity_for_projection = avg_velocity if "Média" in projection_basis else trend_velocity
            basis_text = "média histórica" if "Média" in projection_basis else "tendência recente"

            if velocity_for_projection > 0:
                throughput_per_person = velocity_for_projection / team_size
                required_team_size = required_velocity / throughput_per_person if throughput_per_person > 0 else float('inf')
                
                st.info(f"Considerando a produtividade da **{basis_text}** de **{throughput_per_person:.1f} {unit_display}/pessoa/semana**:")
                st.metric(
                    "👩‍💻 Pessoas Necessárias para Atingir a Meta",
                    f"{np.ceil(required_team_size):.0f} pessoas",
                    delta=f"{np.ceil(required_team_size) - team_size:.0f} vs. equipe atual"
                )

                # ===== NOVA SECÇÃO: ANÁLISE DE VIABILIDADE COM IA =====
                st.divider()
                with st.expander("🤖 Análise de Viabilidade com IA"):
                    st.info("Clique no botão para que a IA analise este cenário de planeamento e forneça uma análise sobre a sua viabilidade e riscos.")
                    
                    if st.button("Analisar Cenário com IA", use_container_width=True):
                        with st.spinner("A IA está a analisar o seu plano..."):
                            
                            ai_planning_summary = get_ai_planning_analysis(
                                project_name=st.session_state.get('project_name', 'este projeto'),
                                remaining_work=f"{remaining_work:.0f} {unit_display}",
                                remaining_weeks=remaining_weeks,
                                required_throughput=required_velocity,
                                trend_velocity=trend_velocity,
                                people_needed=f"{np.ceil(required_team_size):.0f}",
                                current_team_size=f"{team_size}"
                            )
                            st.session_state.ai_planning_summary = ai_planning_summary
                    
                    if 'ai_planning_summary' in st.session_state:
                        st.markdown(st.session_state.ai_planning_summary)

            else:
                st.warning("Não é possível estimar a equipe necessária.", icon="⚠️")
        else:
            st.error("A data de entrega desejada deve ser no futuro.")
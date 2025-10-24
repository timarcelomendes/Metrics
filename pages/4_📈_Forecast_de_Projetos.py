# pages/4_📈_Forecast_de_Projetos.py (VERSÃO CORRIGIDA)

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np
import os
from config import SESSION_TIMEOUT_MINUTES
from jira_connector import *
from metrics_calculator import *
from security import *
from utils import *
from pathlib import Path

st.set_page_config(page_title="Forecast & Planeamento", page_icon="📈", layout="wide")

# --- LÓGICA PRINCIPAL DA PÁGINA ---
st.header("📈 Forecast & Planeamento de Entregas", divider='rainbow')

# --- Bloco de Autenticação e Conexão ---
if 'email' not in st.session_state:
    st.warning("⚠️ Por favor, faça login para acessar."); st.page_link("1_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑"); st.stop()

if check_session_timeout():
    # Usa uma f-string para formatar a mensagem com o valor da variável
    st.warning(f"Sua sessão expirou por inatividade de {SESSION_TIMEOUT_MINUTES} minutos. Por favor, faça login novamente.")
    st.page_link("1_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑")
    st.stop()

if 'jira_client' not in st.session_state:
    # (A verificação original estava buscando 'get_users_collection' sem o e-mail, corrigido para 'find_user')
    user_data = find_user(st.session_state['email'])
    user_connections = user_data.get('jira_connections', []) # Busca as conexões do objeto 'user'
    
    if not user_connections:
        st.warning("Nenhuma conexão Jira foi configurada ainda.", icon="🔌")
        st.info("Para começar, você precisa de adicionar as suas credenciais do Jira.")
        st.page_link("pages/8_🔗_Conexões_Jira.py", label="Configurar sua Primeira Conexão", icon="🔗")
        st.stop()
    else:
        st.warning("Nenhuma conexão Jira está ativa para esta sessão.", icon="⚡")
        st.info("Por favor, ative uma das suas conexões guardadas para carregar os dados.")
        st.page_link("pages/8_🔗_Conexões_Jira.py", label="Ativar uma Conexão", icon="🔗")
        st.stop()

# --- CSS para um design mais "clean" ---
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

# --- Funções de Callback ---
def on_project_change():
    """Limpa o estado relevante ao trocar de projeto."""
    keys_to_clear = ['view_to_show', 'burnup_df', 'burnup_figure', 'forecast_date', 'trend_velocity', 'avg_velocity', 'unit_display', 'scope_name_for_title']
    for key in keys_to_clear:
        if key in st.session_state: st.session_state.pop(key, None)

# --- BARRA LATERAL ---
with st.sidebar:
    project_root = Path(__file__).parent.parent
    logo_path = project_root / "images" / "gauge-logo.svg"
    try:
        st.logo(str(logo_path), size="large")
    except (FileNotFoundError, AttributeError):
        st.write("Gauge Metrics") 

    st.markdown(f"Logado como: **{st.session_state.get('email', '')}**")
    st.header("Configurações de Análise")
    
    projects = st.session_state.get('projects', {}); project_names = list(projects.keys())
    last_project_key = find_user(st.session_state['email']).get('last_project_key')
    default_index = project_names.index(next((name for name, key in projects.items() if key == last_project_key), None)) if last_project_key and projects else 0
    
    selected_project_name = st.selectbox("1. Selecione o Projeto", options=project_names, index=default_index, on_change=on_project_change, placeholder="Escolha um projeto...")
    
    if selected_project_name:
        st.session_state.project_key = projects[selected_project_name]
        st.session_state.project_name = selected_project_name
        
        scope_type = st.radio("2. Analisar por:", ["Projeto Inteiro", "Versão (Fix Version)", "Quadro (Board)"], horizontal=True)
        
        scope_options = {}
        if scope_type == "Versão (Fix Version)":
            versions = get_fix_versions(st.session_state.jira_client, st.session_state.project_key)
            scope_options = {f"{v.name} ({'Lançada' if v.released else 'Não Lançada'})": v for v in sorted(versions, key=lambda x: (not x.released, x.name))}
        elif scope_type == "Quadro (Board)":
            boards = get_project_boards(st.session_state.jira_client, st.session_state.project_key)
            scope_options = {board.name: board for board in boards}
        else:
            scope_options = {"— Projeto Inteiro —": "full_project"}

        if not scope_options:
            st.warning(f"Nenhum(a) {scope_type} encontrado(a) para este projeto.")
        else:
            selected_scope_name = st.selectbox("3. Selecione o Escopo Específico", options=list(scope_options.keys()))
            
            project_config = get_project_config(st.session_state.project_key) or {}
            estimation_config = project_config.get('estimation_field', {})
            estimation_field_name = estimation_config.get('name')
            estimation_field_id = estimation_config.get('id') if estimation_config else None
            
            # (Garante que 'Contagem de Issues' é a opção padrão se a estimativa não estiver configurada)
            unit_options_display = []
            if estimation_field_name and estimation_field_id:
                unit_options_display.append("Story Points")
            unit_options_display.append("Contagem de Issues")
            
            default_unit_index = 0 if estimation_field_name and estimation_field_id else 0 

            # 4. Cria o radio button com as opções de exibição
            unit_selected_label = st.radio(
                "4. Unidade de Análise", 
                options=unit_options_display,
                horizontal=True, 
                index=default_unit_index
            )
            
            if unit_selected_label == "Story Points":
                unit = estimation_field_name
            else:
                unit = unit_selected_label 
            
            trend_weeks = st.slider("5. Semanas para Tendência", 2, 12, 4)

            if st.button("Analisar Escopo", use_container_width=True, type="primary"):
                with st.spinner("A buscar issues do escopo selecionado..."):
                    scope_obj = scope_options[selected_scope_name]

                    # 1. Cria a lista de campos extras para pedir
                    extra_fields_to_fetch = []
                    if estimation_field_id:
                        extra_fields_to_fetch.append(estimation_field_id)
                        
                    # 2. Passa a lista de campos extras para as funções de busca              
                    if scope_type == "Versão (Fix Version)":
                        issues = get_issues_by_fix_version(st.session_state.jira_client, st.session_state.project_key, scope_obj.id, extra_fields=extra_fields_to_fetch)
                    elif scope_type == "Quadro (Board)":
                        issues = get_issues_by_board(st.session_state.jira_client, scope_obj.id, extra_fields=extra_fields_to_fetch)
                    else: # Projeto Inteiro
                        issues = get_all_project_issues(st.session_state.jira_client, st.session_state.project_key, extra_fields=extra_fields_to_fetch)
                    
                    st.session_state.scope_issues = issues
                    # (Modificado para usar o 'estimation_field_name' dinâmico)
                    st.session_state.unit_param = 'count' if unit == 'Contagem de Issues' else 'points'
                    st.session_state.trend_weeks = trend_weeks
                    st.session_state.scope_name_for_title = f"{selected_project_name} ({selected_scope_name})"
                    st.session_state.view_to_show = 'forecast_view'
                    st.rerun()

# --- LÓGICA PRINCIPAL DA PÁGINA ---
if st.session_state.get('view_to_show') != 'forecast_view':
    st.info("⬅️ Na barra lateral, selecione os parâmetros e clique em 'Analisar Escopo' para começar.")
    st.stop()

# --- Carrega e Prepara os Dados ---
issues = st.session_state.scope_issues
unit_param = st.session_state.unit_param
trend_weeks = st.session_state.trend_weeks
project_key = st.session_state.project_key
project_config = get_project_config(project_key) or {}
estimation_config = project_config.get('estimation_field', {})
scope_name_for_title = st.session_state.scope_name_for_title

burnup_df = prepare_project_burnup_data(issues, unit_param, estimation_config, project_config)

if burnup_df is None or burnup_df.empty:
    st.error(f"Não foi possível gerar a análise. Foram encontradas {len(issues)} issues, mas pode não haver dados suficientes (ex: issues concluídas) no escopo selecionado."); st.stop()

burnup_figure, forecast_date, trend_velocity, avg_velocity = calculate_trend_and_forecast(burnup_df, trend_weeks)
unit_display = "itens" if unit_param == 'count' else "pts"
total_scope = burnup_df['Escopo Total'].iloc[-1]; total_completed = burnup_df['Trabalho Concluído'].iloc[-1]

tab1, tab2 = st.tabs(["**Burnup & Previsão de Data**", "**Planeamento de Vazão**"])

with tab1:
    with st.container(border=True):
        st.subheader("Indicadores Chave de Progresso")
        kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
        
        completed_pct = (total_completed / total_scope) * 100 if total_scope > 0 else 0
        
        kpi1.metric("📦 Escopo Total", f"{total_scope:.0f} {unit_display}")
        kpi2.metric("✅ Concluído", f"{total_completed:.0f} {unit_display} ({completed_pct:.0f}%)")
        kpi3.metric("Velocidade Média", f"{avg_velocity:.1f} {unit_display}/sem")
        kpi4.metric(f"Tendência ({trend_weeks} sem.)", f"{trend_velocity:.1f} {unit_display}/sem")
        kpi5.metric("🎯 Previsão de Entrega", forecast_date.strftime('%d/%m/%Y') if forecast_date else "Incalculável")

    st.subheader(f"Gráfico de Burnup: {scope_name_for_title}")
    if burnup_figure:
        st.plotly_chart(burnup_figure, use_container_width=True)
    else:
        st.warning("Não foi possível gerar o gráfico de burnup.")
    
    with st.expander("🤖 Resumo Executivo com IA"):
        if st.button("Gerar Resumo com IA", use_container_width=True):
            with st.spinner("Gauge AI está a analisar o seu forecast..."):
                forecast_date_str = forecast_date.strftime('%d/%m/%Y') if forecast_date else "Incalculável"
                ai_summary = get_ai_forecast_analysis(
                    project_name=st.session_state.get('project_name', 'este projeto'),
                    scope_total=f"{total_scope:.0f} {unit_display}",
                    completed_pct=f"{completed_pct:.0f}",
                    avg_velocity=avg_velocity,
                    trend_velocity=trend_velocity,
                    forecast_date_str=forecast_date_str
                )
                st.session_state.ai_forecast_summary = ai_summary
        
        if 'ai_forecast_summary' in st.session_state:
            st.markdown(st.session_state.ai_forecast_summary)

with tab2:
    st.subheader("Qual a vazão necessária para atingir uma data?")
    st.caption("Use esta ferramenta para simular cenários e entender a viabilidade de uma data de entrega.")
    
    with st.form("planning_form"):
        st.markdown("**1. Defina os Parâmetros da Simulação**")
        c1, c2 = st.columns(2)
        
        target_date = c1.date_input("Data de Entrega Desejada", value=None)
        team_size = c2.number_input("Tamanho da Equipe Atual", min_value=1, value=None, placeholder="Nº de pessoas")
        
        projection_base = st.radio("Base para projeção da equipe:", ["Velocidade Média (Histórico Total)", f"Tendência ({trend_weeks} semanas)"], horizontal=True)
        
        submitted = st.form_submit_button("Simular Cenário", use_container_width=True, type="primary")

    if submitted:
        if not target_date or not team_size:
            st.warning("Por favor, preencha a 'Data de Entrega Desejada' e o 'Tamanho da Equipe Atual' para simular.")
        else:
            remaining_work = total_scope - total_completed
            if target_date > datetime.now().date() and remaining_work > 0:
                remaining_weeks = (target_date - datetime.now().date()).days / 7
                required_throughput = remaining_work / remaining_weeks if remaining_weeks > 0 else float('inf')
                
                base_velocity = avg_velocity if projection_base == "Velocidade Média (Histórico Total)" else trend_velocity
                productivity_per_person = base_velocity / team_size if team_size > 0 else 0
                people_needed = required_throughput / productivity_per_person if productivity_per_person > 0 else float('inf')

                st.divider()
                st.subheader("2. Análise do Cenário")
                kpi1, kpi2, kpi3 = st.columns(3)
                kpi1.metric("🏁 Trabalho Restante", f"{remaining_work:.1f} {unit_display}")
                kpi2.metric("🗓️ Semanas Restantes", f"{remaining_weeks:.1f} semanas")
                kpi3.metric(label="⚡ Vazão Necessária", value=f"{required_throughput:.1f} {unit_display}/sem", delta=f"{(required_throughput - trend_velocity):.1f} vs. tendência")

                st.subheader("3. Análise da Equipe")
                kpi_team1, kpi_team2 = st.columns(2)
                kpi_team1.metric(f"Produtividade ({projection_base})", f"{productivity_per_person:.1f} {unit_display}/pessoa/semana")
                kpi_team2.metric(label="👩‍💻 Pessoas Necessárias", value=f"{np.ceil(people_needed):.0f} pessoas", delta=f"{(np.ceil(people_needed) - team_size):.0f} vs. equipe atual", delta_color="inverse" if np.ceil(people_needed) > team_size else "normal")
                
                with st.expander("🤖 Análise de Viabilidade com IA"):
                    with st.spinner("A IA está a analisar o seu plano..."):
                        ai_planning_summary = get_ai_planning_analysis(
                            project_name=st.session_state.get('project_name', 'este projeto'),
                            remaining_work=f"{remaining_work:.0f} {unit_display}",
                            remaining_weeks=remaining_weeks,
                            required_throughput=required_throughput,
                            trend_velocity=trend_velocity,
                            people_needed=f"{np.ceil(people_needed):.0f}",
                            current_team_size=f"{team_size}"
                        )
                        st.markdown(ai_planning_summary)
            else:
                st.error("A data de entrega desejada deve ser no futuro ou ainda há trabalho restante.")
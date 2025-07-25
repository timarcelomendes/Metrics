# pages/2_📊_Métricas_de_Fluxo.py

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os
import numpy as np
from jira_connector import *
from metrics_calculator import *
from security import *
from config import *
from pathlib import Path
from utils import *

st.set_page_config(page_title="Métricas de Fluxo", page_icon="📊", layout="wide")

# --- Bloco de Autenticação e Conexão ---
st.header("📊 Métricas de Fluxo e Performance da Equipe", divider='rainbow')

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
            else: st.error("Falha na conexão com o Jira."); st.page_link("pages/6_👤_Minha_Conta.py", label="Verificar Credenciais", icon="👤"); st.stop()
    else: st.warning("Credenciais do Jira não configuradas."); st.page_link("pages/6_👤_Minha_Conta.py", label="Configurar Credenciais", icon="👤"); st.stop()

def on_project_change():
    if 'issues_data_fluxo' in st.session_state: st.session_state.pop('issues_data_fluxo', None)
    if 'raw_issues_for_fluxo' in st.session_state: st.session_state.pop('raw_issues_for_fluxo', None)

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
    
    selected_project_name = st.selectbox("1. Selecione o Projeto", options=project_names, key="project_selector_fluxo", index=default_index, on_change=on_project_change, placeholder="Escolha um projeto...")
    
    if selected_project_name:
        st.session_state.project_key = projects[selected_project_name]; st.session_state.project_name = selected_project_name
        st.subheader("2. Período de Análise")
        end_date_default = datetime.now(); start_date_default = end_date_default - timedelta(days=30)
        date_range = st.date_input("Selecione o período:", value=(start_date_default, end_date_default))

        if len(date_range) == 2:
            st.session_state.start_date_fluxo, st.session_state.end_date_fluxo = date_range[0], date_range[1]
            if st.button("Analisar Fluxo", use_container_width=True, type="primary"):
                with st.spinner("Buscando e processando issues..."):
                    all_issues_raw = get_all_project_issues(st.session_state.jira_client, st.session_state.project_key)
                    st.session_state['raw_issues_for_fluxo'] = all_issues_raw
                    st.rerun()
    if st.button("Logout", use_container_width=True, type='secondary'):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.switch_page("1_🔑_Autenticação.py")

# --- LÓGICA PRINCIPAL DA PÁGINA ---
all_raw_issues = st.session_state.get('raw_issues_for_fluxo')
if not all_raw_issues:
    st.info("⬅️ Na barra lateral, selecione um projeto, um período e clique em 'Analisar Fluxo' para começar.")
    st.stop()

start_date = st.session_state.start_date_fluxo; end_date = st.session_state.end_date_fluxo
completed_issues_in_period = [i for i in all_raw_issues if (cd := find_completion_date(i)) and start_date <= cd.date() <= end_date]
time_data = [{'Issue': i.key, 'Lead Time (dias)': calculate_lead_time(i), 'Cycle Time (dias)': calculate_cycle_time(i)} for i in completed_issues_in_period]
df_times = pd.DataFrame(time_data)
wip_issues = [i for i in all_raw_issues if i.fields.status.name.lower() not in (DEFAULT_INITIAL_STATES + DEFAULT_DONE_STATES) and pd.to_datetime(i.fields.created).date() <= end_date]
throughput = len(completed_issues_in_period)

tab_comum, tab_kanban, tab_scrum = st.tabs(["Métricas de Fluxo Comuns", "Análise Kanban", "Análise Scrum"])

with tab_comum:
    st.subheader("Visão Geral do Fluxo no Período Selecionado")
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("🚀 Throughput (Vazão)", f"{throughput} itens")
    kpi2.metric("⚙️ Work in Progress (WIP)", f"{len(wip_issues)} itens")
    kpi3.metric("⏱️ Lead Time Médio", f"{df_times['Lead Time (dias)'].mean():.1f} dias" if not df_times.empty else "N/A")
    kpi4.metric("⚙️ Cycle Time Médio", f"{df_times['Cycle Time (dias)'].mean():.1f} dias" if not df_times.empty else "N/A")
    st.divider()
    st.subheader("Diagrama de Fluxo Cumulativo (CFD)")
    st.caption("Mostra a evolução dos itens em cada etapa ao longo do tempo. Ideal para visualizar gargalos e a estabilidade do fluxo.")
    cfd_df, _ = prepare_cfd_data(all_raw_issues, start_date, end_date)
    if not cfd_df.empty:
        status_order = ['Criado'] + [s for s in cfd_df.columns if s != 'Criado' and s not in DEFAULT_DONE_STATES] + [s for s in cfd_df.columns if s in DEFAULT_DONE_STATES]
        cfd_df_ordered = cfd_df[[s for s in status_order if s in cfd_df.columns]]
        st.area_chart(cfd_df_ordered)
    else: st.info("Não há dados suficientes para gerar o CFD.")

with tab_kanban:
    st.subheader("Métricas de Eficiência e Previsibilidade Kanban")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Aging Work in Progress**"); st.caption("Itens em andamento há mais tempo, potenciais bloqueios.")
        aging_df = get_aging_wip(all_raw_issues); st.dataframe(aging_df.head(10), use_container_width=True, hide_index=True)
    with col2:
        st.markdown("**Eficiência do Fluxo (Estimativa)**")
        avg_flow_efficiency = np.mean([eff for i in completed_issues_in_period if (eff := calculate_flow_efficiency(i)) is not None])
        st.metric("Eficiência Média", f"{avg_flow_efficiency:.1f}%" if pd.notna(avg_flow_efficiency) else "Incalculável", help="Percentagem de tempo em que as tarefas estão ativamente a ser trabalhadas vs. em espera.")
        st.markdown("**Service Level Expectation (SLE)**")
        sle_days = st.slider("Definir SLE (em dias)", 1, 90, 15)
        if not df_times.empty:
            completed_within_sle = df_times[df_times['Cycle Time (dias)'] <= sle_days].shape[0]
            sle_percentage = (completed_within_sle / throughput) * 100 if throughput > 0 else 0
            st.metric(f"Conclusão em até {sle_days} dias", f"{sle_percentage:.1f}%", help=f"Percentagem de itens concluídos dentro do prazo definido.")

with tab_scrum:
    st.subheader("Análise de Performance de Sprints")
    
    project_config = get_project_config(st.session_state.project_key) or {}
    estimation_config = project_config.get('estimation_field', {})
    has_estimation_field = 'id' in estimation_config and estimation_config['id']
    if not estimation_config.get('id'):
        st.warning("Nenhum campo de estimativa configurado para este projeto. As métricas de Scrum podem não ser precisas.", icon="⚠️")
        st.page_link("pages/6_⚙️_Configurações.py", label="Configurar Campo de Estimativa", icon="⚙️")
    st.info("Para uma análise Scrum precisa, selecione um período na barra lateral que corresponda a uma ou mais Sprints concluídas.")
    all_sprints_in_view = get_sprints_in_range(st.session_state.jira_client, st.session_state.project_key, start_date, end_date)
    active_sprints = [s for s in all_sprints_in_view if s.state == 'active']
    closed_sprints_in_period = [s for s in all_sprints_in_view if s.state == 'closed']
    if active_sprints:
        st.markdown("#### Sprint(s) em Andamento")
        for sprint in active_sprints:
            with st.expander(f"🏃 **{sprint.name}** (Ativa)", expanded=True):
                sprint_issues = get_sprint_issues(st.session_state.jira_client, sprint.id)
                if sprint_issues:
                    # Exibe KPIs apenas se houver campo de estimativa
                    if has_estimation_field:
                        velocity_so_far = calculate_velocity(sprint_issues, estimation_config)
                        predictability_so_far = calculate_predictability(sprint_issues, estimation_config)
                        kpi1, kpi2 = st.columns(2)
                        kpi1.metric("🚀 Pontos Concluídos (até agora)", f"{velocity_so_far:.1f} pts")
                        kpi2.metric("🎯 Progresso do Comprometido", f"{predictability_so_far:.1f}%")
                    
                    st.markdown("**Progresso do Burndown**")
                    # --- LÓGICA DE DECISÃO PARA O BURNDOWN ---
                    if has_estimation_field:
                        burndown_df = prepare_burndown_data_by_estimation(st.session_state.jira_client, sprint, estimation_config)
                        y_axis_label = "Pontos Restantes"
                    else:
                        burndown_df = prepare_burndown_data_by_count(st.session_state.jira_client, sprint)
                        y_axis_label = "Issues Restantes"
                    
                    if not burndown_df.empty:
                        real_column = [col for col in burndown_df.columns if '(Real)' in col][0]
                        fig = go.Figure()
                        fig.add_trace(go.Scatter(x=burndown_df.index, y=burndown_df['Linha Ideal'], name='Ideal', mode='lines', line=dict(dash='dash', color='gray')))
                        fig.add_trace(go.Scatter(x=burndown_df.index, y=burndown_df[real_column], name='Real', mode='lines+markers', line=dict(color='blue')))
                        fig.update_layout(title=None, template="plotly_white", yaxis_title=y_axis_label, xaxis_title="Data", height=300)
                        st.plotly_chart(fig, use_container_width=True, key=f"burndown_active_{sprint.id}")
                    else:
                        st.warning("Não foi possível gerar o gráfico de Burndown para esta sprint.")
        st.divider()
    st.markdown("#### Análise de Sprints Concluídas")
    if not closed_sprints_in_period:
        st.info("Nenhuma sprint concluída foi encontrada no período de datas selecionado.")
    else:
        threshold = st.session_state.get('global_configs', {}).get('sprint_goal_threshold', 90)
        success_rate = calculate_sprint_goal_success_rate(closed_sprints_in_period, threshold, estimation_config)
        st.metric(f"🎯 Taxa de Sucesso de Objetivos (Meta > {threshold}%)", f"{success_rate:.1f}%", help="Percentagem de sprints no período que atingiram a meta de previsibilidade.")
        st.divider()
        st.markdown("**Análise Detalhada por Sprint**")
        sprint_names = [s.name for s in closed_sprints_in_period]
        selected_sprint_name = st.selectbox("Selecione uma Sprint para ver os detalhes:", options=[""] + sprint_names, format_func=lambda x: "Selecione uma sprint..." if x == "" else x)
        if selected_sprint_name:
            sprint_obj = next((s for s in closed_sprints_in_period if s.name == selected_sprint_name), None)
            if sprint_obj:
                sprint_issues = get_sprint_issues(st.session_state.jira_client, sprint_obj.id)
                if sprint_issues:
                    velocity = calculate_velocity(sprint_issues, estimation_config); throughput_sprint = calculate_throughput(sprint_issues); predictability = calculate_predictability(sprint_issues, estimation_config); sprint_defects = calculate_sprint_defects(sprint_issues)
                    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
                    kpi1.metric("🚀 Velocidade", f"{velocity} pts"); kpi2.metric("✅ Throughput", f"{throughput_sprint} issues")
                    kpi3.metric("🎯 Previsibilidade", f"{predictability:.1f}%"); kpi4.metric("🐞 Defeitos Concluídos", f"{sprint_defects} bugs")
                    st.subheader("Gráfico de Burndown da Sprint")
                    burndown_df = prepare_burndown_data(st.session_state.jira_client, sprint_obj, estimation_config)
                    if not burndown_df.empty:
                        fig = go.Figure(); fig.add_trace(go.Scatter(x=burndown_df.index, y=burndown_df['Linha Ideal'], name='Ideal', mode='lines', line=dict(dash='dash', color='gray'))); fig.add_trace(go.Scatter(x=burndown_df.index, y=burndown_df['Pontos Restantes (Real)'], name='Real', mode='lines+markers', line=dict(color='blue')))
                        fig.update_layout(title=None, template="plotly_white", yaxis_title="Pontos Restantes", xaxis_title="Data"); st.plotly_chart(fig, use_container_width=True, key=f"burndown_closed_{sprint_obj.id}")
# pages/2_📊_Métricas_de_Fluxo.py

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from jira_connector import *
from metrics_calculator import *
from sklearn.linear_model import LinearRegression
import json, os
from config import * 


st.set_page_config(page_title="Métricas de Iteração", page_icon="📊", layout="wide")

# --- RESERVANDO O ESPAÇO PRINCIPAL DA TELA ---
main_content = st.container()

def load_status_mapping():
    """Carrega o mapeamento de status do ficheiro de configuração."""
    default_mapping = {'initial': DEFAULT_INITIAL_STATES, 'done': DEFAULT_DONE_STATES}
    if os.path.exists(STATUS_MAPPING_FILE):
        with open(STATUS_MAPPING_FILE, 'r', encoding='utf-8') as f:
            try:
                config = json.load(f)
                config.setdefault('initial', default_mapping['initial'])
                config.setdefault('done', default_mapping['done'])
                return config['initial'], config['done']
            except json.JSONDecodeError: return default_mapping['initial'], default_mapping['done']
    return default_mapping['initial'], default_mapping['done']

# --- Funções de Callback ---
def on_project_change():
    keys_to_clear = ['view_to_show', 'selected_board', 'sprint_id', 'sprint_name']
    for key in keys_to_clear:
        if key in st.session_state: st.session_state[key] = None

def on_board_change():
    keys_to_clear = ['view_to_show', 'sprint_id', 'sprint_name']
    for key in keys_to_clear:
        if key in st.session_state: st.session_state[key] = None

# --- Funções de Renderização (Completas) ---
def create_delivery_time_scatter_plot(df_times, context_key: str):
    if df_times.empty:
        st.info("Nenhuma issue concluída com dados de tempo para exibir.")
        return
    
    unique_key = f"scatter_selector_{context_key}"
    metric_to_plot = st.selectbox("Selecione a Métrica de Tempo", ['Cycle Time (dias)', 'Lead Time (dias)'], key=unique_key)
    
    def map_issue_type_to_category(issue_type):
        it_lower = str(issue_type).lower()
        if 'história' in it_lower or 'story' in it_lower: return 'História'
        if 'bug' in it_lower: return 'Bug'
        return 'Outro'
    
    df_times['Categoria'] = df_times['Tipo de Issue'].apply(map_issue_type_to_category)
    
    fig = px.scatter(
        df_times, x='Data de Conclusão', y=metric_to_plot, color='Categoria', size='Story Points',
        hover_name='Issue', hover_data=['Tipo de Issue', 'Lead Time (dias)', 'Cycle Time (dias)'],
        title=f"Dispersão de Tempo de Entrega ({metric_to_plot})",
        opacity=0.6, color_discrete_map={'História': '#1f77b4', 'Bug': '#d62728', 'Outro': '#7f7f7f'}
    )
    
    df_trend = df_times.dropna(subset=[metric_to_plot, 'Data de Conclusão'])
    if len(df_trend) > 1:
        X = df_trend['Data de Conclusão'].map(pd.Timestamp.toordinal).values.reshape(-1, 1); y = df_trend[metric_to_plot].values
        model = LinearRegression(); model.fit(X, y); trend_line_y = model.predict(X)
        fig.add_trace(go.Scatter(x=df_trend['Data de Conclusão'], y=trend_line_y, mode='lines', name='Tendência', line=dict(color='rgba(0,0,0,0.5)', width=2, dash='dash')))
    
    fig.update_layout(xaxis_title="Data de Conclusão", yaxis_title="Tempo (dias)", legend_title="Categoria")
    st.plotly_chart(fig, use_container_width=True)

def display_project_overview_metrics():
    with st.spinner("Buscando issues do projeto..."):
        start_date = st.session_state.get('start_date'); end_date = st.session_state.get('end_date')
        all_issues = get_all_project_issues(st.session_state.jira_client, st.session_state.project_key)
        if start_date and end_date:
            issues = [i for i in all_issues if (cd := find_completion_date(i)) and start_date.date() <= cd.date() <= end_date.date()]
        else: issues = all_issues
        
    st.header(f"Visão Geral do Projeto: {st.session_state.get('project_name', '')}")
    if not issues: st.warning("Nenhuma issue encontrada."); return
    
    completed_issues = [i for i in issues if find_completion_date(i) is not None]
    time_data = [{'Issue': i.key, 'Lead Time (dias)': calculate_lead_time(i), 'Cycle Time (dias)': calculate_cycle_time(i), 'Tipo de Issue': i.fields.issuetype.name, 'Story Points': getattr(i.fields, 'customfield_10016', 0) or 0, 'Data de Conclusão': find_completion_date(i)} for i in completed_issues]
    df_times = pd.DataFrame(time_data).dropna(subset=['Lead Time (dias)', 'Cycle Time (dias)'])

    st.subheader("Métricas de Entrega do Projeto"); col1, col2, col3, col4 = st.columns(4)
    col1.metric("📋 Total de Issues", f"{len(issues)} issues"); col2.metric("✅ Throughput", f"{len(completed_issues)} issues")
    avg_lead_time = df_times['Lead Time (dias)'].mean() if not df_times.empty else 0
    avg_cycle_time = df_times['Cycle Time (dias)'].mean() if not df_times.empty else 0
    col3.metric("⏱️ Lead Time Médio", f"{avg_lead_time:.1f} dias"); col4.metric("⚙️ Cycle Time Médio", f"{avg_cycle_time:.1f} dias"); st.divider()
    
    st.subheader("Dispersão dos Tempos de Entrega")
    create_delivery_time_scatter_plot(df_times, "project_overview")

def display_kanban_metrics():
    st.write(f"Métricas do Quadro Kanban: {st.session_state.selected_board.get('name', '')}")
    with st.spinner("Buscando issues..."):
        issues = get_issues_by_date_range(st.session_state.jira_client, st.session_state.project_key, st.session_state.get('start_date'), st.session_state.get('end_date'))
    if not issues: st.warning("Nenhuma issue encontrada."); return
    
    completed_issues = [i for i in issues if find_completion_date(i) is not None]
    time_data = [{'Issue': i.key, 'Lead Time (dias)': calculate_lead_time(i), 'Cycle Time (dias)': calculate_cycle_time(i), 'Tipo de Issue': i.fields.issuetype.name, 'Story Points': getattr(i.fields, 'customfield_10016', 0) or 0, 'Data de Conclusão': find_completion_date(i)} for i in completed_issues]
    df_times = pd.DataFrame(time_data).dropna(subset=['Lead Time (dias)', 'Cycle Time (dias)'])
    
    st.subheader("Visão Geral do Fluxo"); col1, col2, col3 = st.columns(3)
    col1.metric("🚀 Throughput", f"{len(completed_issues)} issues")
    avg_lead_time = df_times['Lead Time (dias)'].mean() if not df_times.empty else 0; avg_cycle_time = df_times['Cycle Time (dias)'].mean() if not df_times.empty else 0
    col2.metric("⏱️ Lead Time Médio", f"{avg_lead_time:.1f} dias"); col3.metric("⚙️ Cycle Time Médio", f"{avg_cycle_time:.1f} dias"); st.divider()
    
    tab1, tab2, tab3 = st.tabs(["🌊 CFD", "⌛ WIP", "📊 Dispersão de Tempos"]); 
    with tab1:
        cfd_df, _ = prepare_cfd_data(issues)
        if not cfd_df.empty: st.plotly_chart(px.area(cfd_df, x=cfd_df.index, y=cfd_df.columns), use_container_width=True)
    with tab2:
        _, wip_df = prepare_cfd_data(issues)
        if not wip_df.empty: st.plotly_chart(px.line(wip_df, x='Data', y='WIP'), use_container_width=True)
    with tab3:
        st.subheader("Dispersão dos Tempos de Entrega"); create_delivery_time_scatter_plot(df_times, "kanban")

def display_scrum_metrics():
    sprint_id = st.session_state.get('sprint_id');
    if sprint_id is None: return
    
    st.caption(f"Métricas da Sprint: {st.session_state.sprint_name}")
    with st.spinner("Buscando issues..."): issues = get_sprint_issues(st.session_state.jira_client, sprint_id)
    if not issues: st.warning("Nenhuma issue encontrada para esta sprint."); return
    
    velocity = calculate_velocity(issues); completed_issues_count = calculate_throughput(issues); predictability = calculate_predictability(issues)
    st.subheader("Visão Geral da Iteração"); col1, col2, col3, col4 = st.columns(4)
    col1.metric("🚀 Velocidade", f"{velocity} pts"); col2.metric("✅ Throughput", f"{completed_issues_count} issues"); col3.metric("🎯 Previsibilidade", f"{predictability:.1f}%"); col4.metric("📋 Total de Issues", len(issues)); st.divider()
    
    st.subheader("💡 Diagnóstico da Sprint");
    with st.container(border=True): st.markdown("\n".join(f"- {insight}" for insight in generate_sprint_health_summary(issues, predictability)))
    st.divider()

    tab1, tab2 = st.tabs(["📈 Burndown", "🌊 Fluxo e Tempos"])
    with tab1:
        st.subheader("Sprint Burndown Chart"); burndown_df = prepare_burndown_data(st.session_state.jira_client, sprint_id)
        if not burndown_df.empty:
            fig = go.Figure(); fig.add_trace(go.Scatter(x=burndown_df.index, y=burndown_df['Linha Ideal'], name='Ideal', mode='lines', line=dict(dash='dash', color='gray'))); fig.add_trace(go.Scatter(x=burndown_df.index, y=burndown_df['Pontos Restantes (Real)'], name='Real', mode='lines+markers', line=dict(color='blue'))); fig.update_layout(title='Progresso da Sprint'); st.plotly_chart(fig, use_container_width=True)
    with tab2:
        st.subheader("Diagrama de Fluxo Cumulativo da Sprint"); cfd_df, _ = prepare_cfd_data(issues)
        if not cfd_df.empty: st.plotly_chart(px.area(cfd_df, x=cfd_df.index, y=cfd_df.columns), use_container_width=True)
        st.subheader("Dispersão dos Tempos de Entrega na Sprint")
        completed_issues_sprint = [i for i in issues if find_completion_date(i) is not None]
        time_data = [{'Issue': i.key, 'Lead Time (dias)': calculate_lead_time(i), 'Cycle Time (dias)': calculate_cycle_time(i), 'Tipo de Issue': i.fields.issuetype.name, 'Story Points': getattr(i.fields, 'customfield_10016', 0) or 0, 'Data de Conclusão': find_completion_date(i)} for i in completed_issues_sprint]
        df_times_sprint = pd.DataFrame(time_data).dropna(subset=['Lead Time (dias)', 'Cycle Time (dias)'])
        create_delivery_time_scatter_plot(df_times_sprint, "scrum")

# --- LÓGICA PRINCIPAL DA PÁGINA ---
if 'jira_client' not in st.session_state or st.session_state.jira_client is None:
    st.warning("⚠️ Por favor, conecte-se ao Jira na página de Configurações.")
    st.page_link("1_⚙️_Configurações.py", label="Ir para Configurações", icon="⚙️")
    st.stop()

# --- BARRA LATERAL COM NOVO DESIGN ---
with st.sidebar:
    try:
        st.image("images/gauge-logo.png", width=150)
    except Exception:
        st.header("Gauge Metrics")
    st.divider()
    
    projects = st.session_state.get('projects', {})
    
    st.markdown("#### 1. Selecione o Projeto")
    project_name = st.selectbox(
        "Selecione um Projeto", 
        options=list(projects.keys()), 
        key="project_selector", 
        on_change=on_project_change, 
        index=None, 
        placeholder="Escolha um projeto...",
        label_visibility="collapsed"
    )
    
    if project_name:
        st.session_state.project_key = projects.get(project_name)
        st.session_state.project_name = project_name
        
        st.divider()
        st.markdown("#### 2. Selecione a Análise")
        
        boards = get_boards(st.session_state.jira_client, st.session_state.project_key)
        if boards:
            board_options = {b['name']: b for b in boards}
            selected_board_name = st.selectbox("Quadro", options=board_options.keys(), key="board_selector", on_change=on_board_change, index=None, placeholder="Escolha um quadro...")
            if selected_board_name:
                selected_board = board_options.get(selected_board_name)
                st.caption(f"Tipo: **{selected_board['type'].capitalize()}**")
                
                if selected_board['type'] == 'scrum':
                    st.markdown("###### 3. Escolha a Sprint")
                    sprints = get_sprints(st.session_state.jira_client, selected_board['id'])
                    if sprints:
                        sprint_name = st.selectbox("Sprint", options=sprints.keys(), key="sprint_selector", index=None, placeholder="Escolha uma sprint...", label_visibility="collapsed")
                        if sprint_name: st.session_state.sprint_id = sprints.get(sprint_name); st.session_state.sprint_name = sprint_name
                    else: st.warning("Nenhuma sprint encontrada.")
                
                elif selected_board['type'] == 'kanban':
                    st.markdown("###### 3. Escolha o Período")
                    use_date_filter = st.checkbox("Filtrar por data", value=True)
                    if use_date_filter:
                        date_range = st.date_input("Período", (datetime.now() - timedelta(days=30), datetime.now()), label_visibility="collapsed")
                        st.session_state.start_date, st.session_state.end_date = date_range if len(date_range) == 2 else (None, None)
                    else: st.session_state.start_date, st.session_state.end_date = (None, None)
                
                if st.button("Analisar Quadro", use_container_width=True, type="primary"):
                    st.session_state.view_to_show = 'board_view'; st.session_state.selected_board = selected_board
        else:
            # Lógica para projetos sem quadro
            st.warning("Nenhum quadro encontrado.")
            use_date_filter = st.checkbox("Filtrar por data", value=False)
            if use_date_filter:
                date_range = st.date_input("Período", (datetime.now() - timedelta(days=30), datetime.now()))
                st.session_state.start_date, st.session_state.end_date = date_range if len(date_range) == 2 else (None, None)
            else: st.session_state.start_date, st.session_state.end_date = (None, None)
            if st.button("Analisar Visão Geral do Projeto", use_container_width=True, type="primary"):
                st.session_state.view_to_show = 'project_overview'

# --- CONTEÚDO PRINCIPAL ---
with main_content:
    st.header("📊 Métricas de Iteração e Fluxo")
    if st.session_state.get('jira_client'):
        st.caption(f"Conectado a: {st.session_state.jira_client._options['server']}")
    
    view = st.session_state.get('view_to_show')
    if view == 'board_view':
        selected_board = st.session_state.get('selected_board')
        if selected_board:
            if selected_board['type'] == 'scrum':
                if st.session_state.get('sprint_id'): display_scrum_metrics()
                else: st.info("⬅️ Selecione uma Sprint e clique em 'Analisar Quadro' para ver as métricas.")
            elif selected_board['type'] == 'kanban':
                display_kanban_metrics()
    elif view == 'project_overview':
        display_project_overview_metrics()
    else:
        if st.session_state.get('project_key'):
             st.info("⬅️ Por favor, selecione uma análise na barra lateral e clique no botão correspondente.")
        else:
             st.info("⬅️ Por favor, comece selecionando um projeto na barra lateral.")
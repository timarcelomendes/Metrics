# pages/3_📊_Métricas_de_Fluxo.py

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np
from jira_connector import *
from metrics_calculator import *
from security import *
from utils import *
from config import *
from pathlib import Path

st.set_page_config(page_title="Métricas de Fluxo", page_icon="📊", layout="wide")

# --- Funções de Callback ---
def on_project_change():
    """Limpa o estado relevante ao trocar de projeto."""
    keys_to_clear = ['dynamic_df', 'raw_issues_for_fluxo', 'flow_filters']
    for key in keys_to_clear:
        if key in st.session_state:
            st.session_state.pop(key, None)

st.header("📊 Métricas de Fluxo e Performance da Equipe", divider='rainbow')

# --- Bloco de Autenticação e Conexão ---
if 'email' not in st.session_state:
    st.warning("⚠️ Por favor, faça login para acessar."); st.page_link("1_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑"); st.stop()

if 'jira_client' not in st.session_state:
    user_connections = get_user_connections(st.session_state['email'])
    
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

# --- BARRA LATERAL ---
with st.sidebar:
    project_root = Path(__file__).parent.parent
    logo_path = project_root / "images" / "gauge-logo.svg"
    try:
        st.logo(str(logo_path), size="large")
    except (FileNotFoundError, AttributeError):
        st.write("Gauge Metrics")

    if st.session_state.get("email"):
        st.markdown(f"🔐 Logado como: **{st.session_state['email']}**")
    else:
        st.info("⚠️ Usuário não conectado!")

    st.divider()
    st.header("Fonte de Dados")
    projects = st.session_state.get('projects', {})
    project_names = list(projects.keys())

    last_project_key = find_user(st.session_state['email']).get('last_project_key')
    default_index = project_names.index(next((name for name, key in projects.items() if key == last_project_key), None)) if last_project_key and projects else None
    
    selected_project_name = st.selectbox("1. Selecione o Projeto", options=project_names, index=default_index, on_change=on_project_change, placeholder="Escolha um projeto...")
    
    if selected_project_name:
        st.session_state.project_key = projects[selected_project_name]
        st.session_state.project_name = selected_project_name
        
        st.subheader("2. Período de Análise")
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=30)
        date_range = st.date_input("Selecione o período:", value=(start_date, end_date), key="flow_date_range")

        if len(date_range) == 2:
            st.session_state.start_date_fluxo, st.session_state.end_date_fluxo = date_range[0], date_range[1]
        
        is_data_loaded = 'dynamic_df' in st.session_state and st.session_state.dynamic_df is not None
        if st.button("Carregar Dados", width='stretch', type="primary"):
            df_loaded = load_and_process_project_data(st.session_state.jira_client, st.session_state.project_key)
            st.session_state.dynamic_df = df_loaded
            st.rerun()
 
    if st.button("Logout", width='stretch', type='secondary'):
        # Guarda o valor de 'remember_email' antes de limpar a sessão
        email_to_remember = st.session_state.get('remember_email', '')
        
        # Limpa todas as chaves da sessão
        for key in list(st.session_state.keys()):
            del st.session_state[key]
            
        # Restaura a chave 'remember_email' se ela existia
        if email_to_remember:
            st.session_state['remember_email'] = email_to_remember
            
        st.switch_page("1_🔑_Autenticação.py")

# --- LÓGICA PRINCIPAL DA PÁGINA ---
df = st.session_state.get('dynamic_df')
if df is None or df.empty:
    st.info("⬅️ Na barra lateral, selecione um projeto e clique em 'Analisar / Atualizar Dados' para começar.")
    st.stop()

# --- Lógica de construção de listas de colunas dinâmicas ---
project_key = st.session_state.get('project_key')
global_configs = get_global_configs()
user_data = find_user(st.session_state['email'])
project_config = get_project_config(project_key) or {}
user_enabled_standard = user_data.get('standard_fields', [])
user_enabled_custom = user_data.get('enabled_custom_fields', [])
all_available_standard = global_configs.get('available_standard_fields', {})
all_available_custom = global_configs.get('custom_fields', [])
estimation_config = project_config.get('estimation_field', {})
master_field_list = []
for field in all_available_custom:
    if field.get('name') in user_enabled_custom: master_field_list.append({'name': field['name'], 'type': field.get('type', 'Texto')})
for field_name in user_enabled_standard:
    details = all_available_standard.get(field_name, {})
    if details: master_field_list.append({'name': field_name, 'type': details.get('type', 'Texto')})
if estimation_config and estimation_config.get('name') not in [f['name'] for f in master_field_list]:
    est_type = 'Numérico' if estimation_config.get('source') != 'standard_time' else 'Horas'
    master_field_list.append({'name': estimation_config['name'], 'type': est_type})
base_numeric_cols = ['Lead Time (dias)', 'Cycle Time (dias)']
base_date_cols = ['Data de Criação', 'Data de Conclusão']
numeric_cols = sorted(list(set(base_numeric_cols + [f['name'] for f in master_field_list if f['type'] in ['Numérico', 'Horas']])))
date_cols = sorted(list(set(base_date_cols + [f['name'] for f in master_field_list if f['type'] == 'Data'])))
categorical_cols = sorted(list(set([f['name'] for f in master_field_list if f['type'] in ['Texto (Alfanumérico)', 'Texto']])))
sla_policies = global_configs.get('sla_policies', [])

# --- Painel de Filtros ---
with st.expander("Filtros da Análise", expanded=True):
    if 'flow_filters' not in st.session_state: st.session_state.flow_filters = []
    
    for i, f in enumerate(st.session_state.flow_filters):
        cols = st.columns([2, 2, 3, 1])
        all_filterable_fields = [""] + categorical_cols + numeric_cols
        selected_field = cols[0].selectbox("Campo", options=all_filterable_fields, key=f"flow_field_{i}", index=all_filterable_fields.index(f.get('field')) if f.get('field') in all_filterable_fields else 0)
        st.session_state.flow_filters[i]['field'] = selected_field
        
        if selected_field:
            field_type = 'numeric' if selected_field in numeric_cols else 'categorical'
            op_options = ['está em', 'não está em', 'é igual a', 'não é igual a'] if field_type == 'categorical' else ['maior que', 'menor que', 'entre', 'é igual a', 'não é igual a']
            operator = cols[1].selectbox("Operador", options=op_options, key=f"flow_op_{i}", index=op_options.index(f.get('operator')) if f.get('operator') in op_options else 0)
            st.session_state.flow_filters[i]['operator'] = operator
            
            with cols[2]:
                if operator in ['está em', 'não está em']:
                    options = sorted(df[selected_field].dropna().unique()); value = st.multiselect("Valores", options=options, key=f"flow_val_multi_{i}", default=f.get('value', []))
                elif operator == 'entre':
                    min_val, max_val = df[selected_field].min(), df[selected_field].max(); value = st.slider("Intervalo", float(min_val), float(max_val), f.get('value', [min_val, max_val]), key=f"flow_val_slider_{i}")
                else:
                    if field_type == 'categorical':
                        options = sorted(df[selected_field].dropna().unique()); value = st.selectbox("Valor", options=options, key=f"flow_val_single_cat_{i}", index=options.index(f.get('value')) if f.get('value') in options else 0)
                    else:
                        value = st.number_input("Valor", key=f"flow_val_single_num_{i}", value=f.get('value', 0.0))
            st.session_state.flow_filters[i]['value'] = value
        cols[3].button("❌", key=f"flow_remove_{i}", on_click=lambda i=i: st.session_state.flow_filters.pop(i), width='stretch')
    
    st.button("➕ Adicionar Filtro", on_click=lambda: st.session_state.flow_filters.append({}))

# --- Aplica os filtros ---
filtered_df = df.copy()
for f in st.session_state.flow_filters:
    field, op, val = f.get('field'), f.get('operator'), f.get('value')
    if field and op and val is not None:
        try:
            if op == 'é igual a': filtered_df = filtered_df[filtered_df[field] == val]
            elif op == 'não é igual a': filtered_df = filtered_df[filtered_df[field] != val]
            elif op == 'está em': filtered_df = filtered_df[filtered_df[field].isin(val)]
            elif op == 'não está em': filtered_df = filtered_df[~filtered_df[field].isin(val)]
            elif op == 'maior que': filtered_df = filtered_df[pd.to_numeric(filtered_df[field], errors='coerce') > val]
            elif op == 'menor que': filtered_df = filtered_df[pd.to_numeric(filtered_df[field], errors='coerce') < val]
            elif op == 'entre' and len(val) == 2:
                filtered_df = filtered_df[pd.to_numeric(filtered_df[field], errors='coerce').between(val[0], val[1])]
        except Exception: pass

filtered_issue_keys = filtered_df['Issue'].tolist()
all_raw_issues = st.session_state.get('raw_issues_for_fluxo', [])
filtered_issues = [issue for issue in all_raw_issues if issue.key in filtered_issue_keys]

st.caption(f"A exibir métricas para {len(filtered_issues)} de {len(all_raw_issues)} issues, com base nos filtros aplicados.")
st.divider()

# --- CÁLCULO CENTRALIZADO DE MÉTRICAS ---
start_date, end_date = st.session_state.start_date_fluxo, st.session_state.end_date_fluxo
status_mapping = project_config.get('status_mapping', {})
done_statuses = status_mapping.get('done', [])
in_progress_statuses = status_mapping.get('in_progress', [])

if not done_statuses:
    st.warning("Nenhum 'status final' está configurado para este projeto. A aplicação não consegue identificar itens concluídos. "
               "Por favor, vá para 'Configurações' -> 'Configurações por Projeto' para definir os status que representam a conclusão de uma tarefa.",
               icon="⚠️")

completed_issues_in_period = [i for i in filtered_issues if (cd := find_completion_date(i, project_config)) and start_date <= cd.date() <= end_date]
completed_issue_keys = [i.key for i in completed_issues_in_period]
df_completed = filtered_df[filtered_df['Issue'].isin(completed_issue_keys)]

times_data = []
for issue in completed_issues_in_period:
    completion_date = find_completion_date(issue, project_config)
    if completion_date:
        lead_time = (completion_date - pd.to_datetime(issue.fields.created).tz_localize(None)).total_seconds() / (24 * 3600)
        cycle_time = calculate_cycle_time(issue, completion_date, project_config)

        times_data.append({
            'Lead Time (dias)': lead_time,
            'Cycle Time (dias)': cycle_time
        })

df_times = pd.DataFrame(times_data)
if not df_times.empty:
    df_times.dropna(subset=['Cycle Time (dias)'], inplace=True)

wip_issues = [i for i in filtered_issues if i.fields.status.name.lower() in [s.lower() for s in in_progress_statuses]]
throughput = len(completed_issues_in_period)
lead_time_avg = df_times['Lead Time (dias)'].mean() if not df_times.empty else 0
cycle_time_avg = df_times['Cycle Time (dias)'].mean() if not df_times.empty else 0
aging_df = get_aging_wip(filtered_issues)
sla_metrics = {}
if sla_policies:
    sla_metrics = calculate_sla_metrics_for_issues(filtered_issues, global_configs)

# --- Abas de Exibição ---
tab_comum, tab_kanban, tab_scrum, tab_performance = st.tabs(["Métricas de Fluxo Comuns", "Análise Kanban", "Análise Scrum", "Análise de Performance"])

with tab_comum:
    st.subheader("Visão Geral do Fluxo")
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("🚀 Throughput (Vazão)", f"{throughput} itens")
    kpi2.metric("⚙️ Work in Progress (WIP)", f"{len(wip_issues)} itens")
    kpi3.metric("⏱️ Lead Time Médio", f"{lead_time_avg:.1f} dias" if pd.notna(lead_time_avg) else "N/A")
    kpi4.metric("⚙️ Cycle Time Médio", f"{cycle_time_avg:.1f} dias" if pd.notna(cycle_time_avg) else "N/A")
    
    st.divider()
    st.subheader("Diagrama de Fluxo Cumulativo (CFD)")
    st.caption("Mostra a evolução dos itens em cada etapa ao longo do tempo.")
    cfd_df, _ = prepare_cfd_data(all_raw_issues, start_date, end_date)
    if not cfd_df.empty:
        done_statuses_cfd = [s.lower() for s in done_statuses]
        status_order = ['Created'] + [s for s in cfd_df.columns if s != 'Created' and s.lower() not in done_statuses_cfd] + [s for s in cfd_df.columns if s.lower() in done_statuses_cfd]
        cfd_df_ordered = cfd_df[[s for s in status_order if s in cfd_df.columns]]
        st.area_chart(cfd_df_ordered)
    else: st.info("Não há dados suficientes para gerar o CFD.")

with tab_kanban:
    if sla_metrics:
        st.subheader("Métricas de Eficiência e Atendimento")
        kpi1, kpi2, kpi3 = st.columns(3)
        kpi1.metric("% de chamados atendidos dentro do SLA", f"{sla_metrics.get('sla_resolution_met_pct', 0):.1f}%")
        kpi2.metric("% de chamados com SLA violado", f"{sla_metrics.get('sla_resolution_violated_pct', 0):.1f}%")
        kpi3.metric("Tempo médio para primeiro atendimento", f"{sla_metrics.get('avg_first_response_hours', 0):.1f} horas")
        st.divider()
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Aging Work in Progress**")
        st.caption("Itens em andamento há mais tempo, potenciais bloqueios.")
        st.dataframe(aging_df.head(10), use_container_width=True, hide_index=True)
    with col2:
        st.markdown("**Eficiência do Fluxo (Estimativa)**")
        avg_flow_efficiency = np.mean([eff for i in completed_issues_in_period if (eff := calculate_flow_efficiency(i, project_config)) is not None])
        st.metric("Eficiência Média", f"{avg_flow_efficiency:.1f}%" if pd.notna(avg_flow_efficiency) else "Incalculável", help="Percentagem de tempo em que as tarefas estão ativamente a ser trabalhadas vs. em espera.")
        
        st.markdown("**Service Level Expectation (SLE)**")
        sle_days = st.slider("Definir SLE (em dias)", 1, 90, 15)
        
        sle_percentage = 0.0
        total_items_for_sle = len(df_times)

        if throughput > 0 and total_items_for_sle > 0:
            completed_within_sle = df_times[df_times['Cycle Time (dias)'] <= sle_days].shape[0]
            sle_percentage = (completed_within_sle / total_items_for_sle) * 100
        
        st.metric(f"Conclusão em até {sle_days} dias", f"{sle_percentage:.1f}%", help=f"Percentagem de itens concluídos dentro do prazo definido.")
        
        if throughput == 0:
            st.caption("SLE é 0% porque não há itens concluídos no período selecionado.")
        elif total_items_for_sle == 0:
            st.caption("SLE é 0% porque não foi possível calcular o Cycle Time dos itens concluídos (verifique a configuração de status 'Em Andamento').")

with tab_scrum:
    st.subheader("Análise de Performance de Sprints")
    estimation_config = project_config.get('estimation_field', {})
    
    all_sprints_in_view = get_sprints_in_range(st.session_state.jira_client, project_key, start_date, end_date)
    closed_sprints_in_period = [s for s in all_sprints_in_view if s.state == 'closed']

    if not all_sprints_in_view:
        st.warning("Nenhuma sprint (ativa ou concluída) foi encontrada no período de datas selecionado.")
    else:
        st.markdown("#### Análise de Sprints Concluídas no Período")
        if not closed_sprints_in_period:
            st.info("Nenhuma sprint concluída foi encontrada no período de datas selecionado.")
        else:
            threshold = st.session_state.get('global_configs', {}).get('sprint_goal_threshold', 90)
            success_rate = calculate_sprint_goal_success_rate(closed_sprints_in_period, threshold, estimation_config)
            st.metric(f"🎯 Taxa de Sucesso de Objetivos (Meta > {threshold}%)", f"{success_rate:.1f}%")
            st.divider()

            st.markdown("**Análise Detalhada por Sprint**")
            sprint_names = [s.name for s in closed_sprints_in_period]
            selected_sprint_name = st.selectbox("Selecione uma Sprint concluída para ver os detalhes:", options=[""] + sprint_names, format_func=lambda x: "Selecione..." if x == "" else x)

            if selected_sprint_name:
                sprint = next((s for s in closed_sprints_in_period if s.name == selected_sprint_name), None)
                if sprint:
                    unit_burndown = st.selectbox(
                        "Calcular Burndown por:",
                        options=["Contagem de Issues", "Campo de Estimativa"],
                        key=f"burndown_unit_{sprint.id}"
                    )
                    
                    burndown_df = pd.DataFrame()
                    y_axis_label = ""

                    if unit_burndown == "Contagem de Issues":
                        burndown_df = prepare_burndown_data_by_count(st.session_state.jira_client, sprint, project_config)
                        y_axis_label = "Issues Restantes"
                    else: # Campo de Estimativa
                        if not estimation_config or not estimation_config.get('id'):
                            st.warning("Para ver o Burndown por estimativa, configure um 'Campo de Estimativa' para este projeto.")
                        else:
                            burndown_df = prepare_burndown_data_by_estimation(st.session_state.jira_client, sprint, estimation_config, project_config)
                            y_axis_label = f"{estimation_config.get('name', 'Pontos')} Restantes"

                    if not burndown_df.empty:
                        fig = px.line(burndown_df, x=burndown_df.index, y=burndown_df.columns, labels={"value": y_axis_label, "variable": "Legenda"})
                        fig.update_layout(template="plotly_white", title=f"Burndown da Sprint: {selected_sprint_name}")
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("Não há dados suficientes para gerar o gráfico de Burndown.")

with tab_performance:
    st.subheader("Análise de Acurácia e Performance da Equipe")

    project_config = get_project_config(st.session_state.project_key) or {}
    estimation_config = project_config.get('estimation_field', {})
    if not estimation_config.get('id'):
        st.warning("Nenhum campo de estimativa configurado. As métricas de acurácia não podem ser calculadas.", icon="⚠️")
        
        # --- INÍCIO DA CORREÇÃO ---
        st.page_link("pages/7_⚙️_Configurações.py", label="Configurar Campo de Estimativa", icon="⚙️")
        # --- FIM DA CORREÇÃO ---
    else:
        st.markdown("**Acurácia da Estimativa (Estimado vs. Realizado)**")
        st.caption("Compara o esforço estimado com o tempo real gasto nas tarefas concluídas no período.")
        
        accuracy_metrics = calculate_estimation_accuracy(completed_issues_in_period, estimation_config)
        
        kpi1, kpi2, kpi3 = st.columns(3)
        unit = "hs" if estimation_config.get('source') == 'standard_time' else "pts"
        
        kpi1.metric(f"Total Estimado (Concluídos)", f"{accuracy_metrics['total_estimated']:.1f} {unit}")
        kpi2.metric(f"Total Realizado (Concluídos)", f"{accuracy_metrics['total_actual']:.1f} hs")
        kpi3.metric("Acurácia (Realizado / Estimado)", f"{accuracy_metrics['accuracy_ratio']:.1f}%", 
                    delta=f"{accuracy_metrics['accuracy_ratio'] - 100:.1f}% vs. 100%", 
                    delta_color="inverse",
                    help="Valores acima de 100% indicam que o esforço real foi maior que o estimado.")

        st.divider()
        st.markdown("**Comparativo Visual: Estimado vs. Realizado**")

        chart_data = {
            'Métrica': ['Estimado', 'Realizado'],
            'Valor': [accuracy_metrics['total_estimated'], accuracy_metrics['total_actual']]
        }
        df_chart = pd.DataFrame(chart_data)

        if not df_chart.empty and df_chart['Valor'].sum() > 0:
            fig = px.bar(
                df_chart,
                x='Métrica',
                y='Valor',
                color='Métrica',
                text='Valor',
                color_discrete_map={'Estimado': '#1f77b4', 'Realizado': '#ff7f0e'},
                labels={'Valor': f'Valor ({unit} / hs)', 'Métrica': ''}
            )
            fig.update_traces(texttemplate='%{text:.1f}', textposition='outside')
            fig.update_layout(
                title_text=f"Comparativo Estimado vs. Realizado (em {unit})",
                template="plotly_white",
                showlegend=False
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Não há dados de estimativa e tempo gasto para exibir o gráfico.")
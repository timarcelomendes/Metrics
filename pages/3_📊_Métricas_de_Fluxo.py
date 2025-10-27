# pages/3_📊_Métricas_de_Fluxo.py (VERSÃO CORRIGIDA)

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
    
    st.divider()
    st.header("Fonte de Dados")
    projects = st.session_state.get('projects', {})
    project_names = list(projects.keys())

    last_project_key = find_user(st.session_state['email']).get('last_project_key')
    default_index = project_names.index(next((name for name, key in projects.items() if key == last_project_key), None)) if last_project_key and projects else 0
    
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
        
        if st.button("Analisar / Atualizar Dados", width='stretch', type="primary"):
            with st.spinner("A carregar e processar dados do Jira..."):
                df_loaded, raw_issues = load_and_process_project_data(st.session_state.jira_client, st.session_state.project_key)
                st.session_state.dynamic_df = df_loaded
                st.session_state.raw_issues_for_fluxo = raw_issues
            st.rerun()
 
    if st.button("Logout", width='stretch', type='secondary'):
        email_to_remember = st.session_state.get('remember_email', '')
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        if email_to_remember:
            st.session_state['remember_email'] = email_to_remember
        st.switch_page("1_🔑_Autenticação.py")

# --- LÓGICA PRINCIPAL DA PÁGINA ---
df = st.session_state.get('dynamic_df')
if df is None or df.empty:
    st.info("⬅️ Na barra lateral, selecione um projeto e clique em 'Analisar / Atualizar Dados' para começar.")
    st.stop()

if 'ID' not in df.columns and 'key' in df.columns:
    df.rename(columns={'key': 'ID'}, inplace=True)

project_key = st.session_state.get('project_key')
project_config = get_project_config(project_key) or {}
global_configs = get_global_configs()

status_mapping = project_config.get('status_mapping', {})
done_status_objects = status_mapping.get('done', [])
done_statuses_lower = {d['name'].lower() for d in done_status_objects if isinstance(d, dict) and 'name' in d}
ignored_status_objects = project_config.get('ignored_statuses', [])
ignored_statuses_lower = {d['name'].lower() for d in ignored_status_objects if isinstance(d, dict) and 'name' in d}
overlap = done_statuses_lower.intersection(ignored_statuses_lower)

if overlap:
    st.warning(
        f"""
        **⚠️ Alerta de Configuração:** Seus cálculos de fluxo podem estar incorretos!
        
        Detectamos que os seguintes status estão configurados tanto como **finais (Done)** quanto como **ignorados**:
        `{', '.join(list(overlap))}`.

        Isso faz com que os itens concluídos sejam filtrados e não apareçam nas métricas de Throughput, Lead Time, Cycle Time, etc.
        
        **Para corrigir:** Vá para **Configurações -> Configurações por Projeto** e remova estes status da lista de "Status a Ignorar".
        """,
        icon="⚙️"
    )

with st.expander("Filtros da Análise", expanded=True):
    if 'flow_filters' not in st.session_state: st.session_state.flow_filters = []
    
    for i, f in enumerate(st.session_state.flow_filters):
        cols = st.columns([2, 2, 3, 1])
        all_filterable_fields = [""] + sorted(list(set(c for c in df.columns if df[c].dtype in ['object', 'int64', 'float64'] and c not in ['ID', 'Issue'])))
        selected_field = cols[0].selectbox("Campo", options=all_filterable_fields, key=f"flow_field_{i}", index=all_filterable_fields.index(f.get('field')) if f.get('field') in all_filterable_fields else 0)
        st.session_state.flow_filters[i]['field'] = selected_field
        
        if selected_field:
            is_numeric = pd.api.types.is_numeric_dtype(df[selected_field])
            op_options = ['maior que', 'menor que', 'entre', 'é igual a', 'não é igual a'] if is_numeric else ['está em', 'não está em', 'é igual a', 'não é igual a']
            operator = cols[1].selectbox("Operador", options=op_options, key=f"flow_op_{i}", index=op_options.index(f.get('operator')) if f.get('operator') in op_options else 0)
            st.session_state.flow_filters[i]['operator'] = operator
            
            with cols[2]:
                if operator in ['está em', 'não está em']:
                    options = sorted(df[selected_field].dropna().unique()); value = st.multiselect("Valores", options=options, key=f"flow_val_multi_{i}", default=f.get('value', []))
                elif operator == 'entre' and is_numeric:
                    min_val, max_val = float(df[selected_field].min()), float(df[selected_field].max()); value = st.slider("Intervalo", min_val, max_val, f.get('value', (min_val, max_val)), key=f"flow_val_slider_{i}")
                else:
                    if not is_numeric:
                        options = sorted(df[selected_field].dropna().unique()); value = st.selectbox("Valor", options=options, key=f"flow_val_single_cat_{i}", index=options.index(f.get('value')) if f.get('value') in options else 0)
                    else:
                        value = st.number_input("Valor", key=f"flow_val_single_num_{i}", value=f.get('value', 0.0))
            st.session_state.flow_filters[i]['value'] = value
        cols[3].button("❌", key=f"flow_remove_{i}", on_click=lambda i=i: st.session_state.flow_filters.pop(i), width='stretch')
    
    st.button("➕ Adicionar Filtro", on_click=lambda: st.session_state.flow_filters.append({}))

filtered_df = apply_filters(df, st.session_state.get('flow_filters', []))

# Garante que a coluna 'ID' existe antes de tentar usá-la.
if 'ID' not in filtered_df.columns:
    st.error(
        "Ocorreu um erro inesperado: a coluna 'ID' não foi encontrada nos dados após a filtragem. "
        "Isso pode acontecer se não houver dados no período selecionado. "
        "Tente ajustar os filtros ou recarregar os dados na barra lateral."
    )
    st.stop()

filtered_issue_keys = filtered_df['ID'].tolist()
all_raw_issues = st.session_state.get('raw_issues_for_fluxo', [])
filtered_issues = [issue for issue in all_raw_issues if issue.key in filtered_issue_keys]

st.caption(f"A exibir métricas para {len(filtered_issues)} de {len(all_raw_issues)} issues, com base nos filtros aplicados.")
st.divider()

start_date, end_date = st.session_state.start_date_fluxo, st.session_state.end_date_fluxo
done_statuses = status_mapping.get('done', [])
in_progress_statuses = status_mapping.get('in_progress', [])

if not done_statuses:
    st.warning("Nenhum 'status final' está configurado para este projeto.", icon="⚠️")

completed_issues_in_period = [i for i in filtered_issues if (cd_datetime := find_completion_date(i, project_config)) and start_date <= cd_datetime.date() <= end_date]
times_data = []
for issue in completed_issues_in_period:
    completion_date_dt = find_completion_date(issue, project_config)
    if completion_date_dt:
        completion_date = pd.to_datetime(completion_date_dt)
        cycle_time = calculate_cycle_time(issue, completion_date, project_config)
        lead_time = calculate_lead_time(issue, completion_date)
        times_data.append({'Lead Time (dias)': lead_time, 'Cycle Time (dias)': cycle_time})

df_times = pd.DataFrame(times_data)
if not df_times.empty:
    df_times.dropna(subset=['Cycle Time (dias)'], inplace=True)

wip_issues = [i for i in filtered_issues if hasattr(i.fields, 'status') and i.fields.status and i.fields.status.name.lower() in [s.lower() for s in in_progress_statuses]]
throughput = len(completed_issues_in_period)
lead_time_avg = df_times['Lead Time (dias)'].mean() if not df_times.empty else 0
cycle_time_avg = df_times['Cycle Time (dias)'].mean() if not df_times.empty else 0
aging_df = get_aging_wip(filtered_issues)
sla_metrics = {}
if global_configs.get('sla_policies'):
    sla_metrics = calculate_sla_metrics_for_issues(filtered_issues, global_configs)

completed_issue_keys = [issue.key for issue in completed_issues_in_period]

if 'ID' in filtered_df.columns:
    df_done = filtered_df[filtered_df['ID'].isin(completed_issue_keys)].copy()
else:
    df_done = pd.DataFrame()

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
        done_statuses_cfd = [s['name'].lower() for s in done_statuses if isinstance(s, dict) and 'name' in s]
        status_order = ['Created'] + [s for s in cfd_df.columns if s != 'Created' and s.lower() not in done_statuses_cfd] + [s for s in cfd_df.columns if s.lower() in done_statuses_cfd]
        cfd_df_ordered = cfd_df[[s for s in status_order if s in cfd_df.columns]]
        st.area_chart(cfd_df_ordered)
    else: st.info("Não há dados suficientes para gerar o CFD.")

with tab_kanban:
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Aging Work in Progress**")
        st.caption("Itens em andamento há mais tempo, potenciais bloqueios.")
        st.dataframe(aging_df.head(10), hide_index=True)
    with col2:
        st.markdown("**Eficiência do Fluxo (Estimativa)**")
        efficiencies = [eff for i in completed_issues_in_period if (eff := calculate_flow_efficiency(i, project_config)) is not None]
        avg_flow_efficiency = np.mean(efficiencies) if efficiencies else 0.0
        st.metric("Eficiência Média", f"{avg_flow_efficiency:.1f}%", help="Percentagem de tempo em que as tarefas estão ativamente a ser trabalhadas vs. em espera.")
        
        st.markdown("**Service Level Expectation (SLE)**")
        sle_days = st.slider("Definir SLE (em dias)", 1, 90, 15)
        
        sle_percentage = 0.0
        total_items_for_sle = len(df_times)
        if throughput > 0 and total_items_for_sle > 0:
            completed_within_sle = df_times[df_times['Cycle Time (dias)'] <= sle_days].shape[0]
            sle_percentage = (completed_within_sle / total_items_for_sle) * 100

        if throughput > 0 and not df_times.empty:
            completed_within_sle = df_times[df_times['Cycle Time (dias)'] <= sle_days].shape[0]
            sle_percentage = (completed_within_sle / len(df_times)) * 100
        
        st.metric(f"Conclusão em até {sle_days} dias", f"{sle_percentage:.1f}%", help=f"Percentagem de itens concluídos dentro do prazo definido.")

        if throughput == 0:
            st.caption("Não há itens concluídos no período para calcular o SLE.")
        elif total_items_for_sle == 0 and throughput > 0:
            st.caption("SLE é 0% porque não foi possível calcular o Cycle Time dos itens concluídos.")

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
            success_rate = calculate_sprint_goal_success_rate(closed_sprints_in_period, threshold, estimation_config, project_config)
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
    st.caption("Compara o esforço estimado com o tempo real gasto nas tarefas concluídas no período.")

    project_config = get_project_config(st.session_state.project_key) or {}
    
    # 1. Obter as configurações completas
    estimation_config = project_config.get('estimation_field', {})
    timespent_config = project_config.get('timespent_field', {})

    estimation_field_id = estimation_config.get('id')
    timespent_field_id = timespent_config.get('id')
    
    # 2. Verificar se os campos foram configurados
    if not estimation_field_id or not timespent_field_id:
        st.warning("⚠️ Os campos de 'Estimativa' (Previsto) e 'Tempo Gasto' (Realizado) não foram configurados.")
        st.info("Por favor, vá até a página '7_⚙️_Configurações' -> 'Estimativa' e mapeie os dois campos.")
    
    # 3. (Assume que 'df_done' foi definido anteriormente no script)
    elif 'df_done' not in locals() or df_done.empty:
        st.info("Nenhuma issue foi concluída no período selecionado para calcular a acurácia.")
        
    # 4. (Verifica se colunas existem)
    elif estimation_field_id not in df_done.columns or timespent_field_id not in df_done.columns:
        missing_fields = []
        if estimation_field_id not in df_done.columns:
            missing_fields.append(f"'{estimation_config.get('name', estimation_field_id)}' (Previsto)")
        if timespent_field_id not in df_done.columns:
            missing_fields.append(f"'{timespent_config.get('name', timespent_field_id)}' (Realizado)")
        st.error(f"Os seguintes campos configurados não foram encontrados nos dados carregados: {', '.join(missing_fields)}. Por favor, verifique a sua 'Configuração de Conta' para garantir que estes campos estão a ser importados.")

    else:
        # --- PONTO DE ALTERAÇÃO 1: Lógica de verificação de unidade mais robusta ---
        estim_source = estimation_config.get('source')
        spent_source = timespent_config.get('source')

        # 'timespent' e 'timeoriginalestimate' são sempre 'standard_time'
        time_field_ids_padrao = {'timespent', 'timeoriginalestimate'}

        # A unidade é "tempo" se a fonte for 'standard_time' OU se o ID for um campo de tempo padrão
        estim_is_time = (estim_source == 'standard_time') or (estimation_field_id in time_field_ids_padrao)
        spent_is_time = (spent_source == 'standard_time') or (timespent_field_id in time_field_ids_padrao)
        # --- FIM DA ALTERAÇÃO 1 ---

        # VERIFICAÇÃO PRINCIPAL: As unidades são diferentes?
        if estim_is_time != spent_is_time:
            # SIM, são diferentes (ex: pts vs hs)
            estim_unit_display = "hs" if estim_is_time else "pts"
            spent_unit_display = "hs" if spent_is_time else "pts"
            
            st.warning(
                f"📈 Análise Incompatível: O seu campo 'Previsto' está em **{estim_unit_display}** e o seu 'Realizado' está em **{spent_unit_display}**.",
                icon="⚠️"
            )
            st.info(
                f"Para corrigir, vá à página '⚙️ Configurações' e defina **ambos** os campos para usarem a mesma unidade (ex: ambos em Pontos ou ambos em Horas)."
            )
            
            # Cálculo dos KPIs para exibição (mesmo incompatíveis)
            total_estimado = pd.to_numeric(df_done[estimation_field_id], errors='coerce').fillna(0).sum()
            total_realizado_segundos_ou_pontos = pd.to_numeric(df_done[timespent_field_id], errors='coerce').fillna(0).sum()

            # Converte para horas apenas se for um campo de tempo
            if estim_is_time:
                total_estimado = total_estimado / 3600.0
            if spent_is_time:
                total_realizado = total_realizado_segundos_ou_pontos / 3600.0
            else:
                total_realizado = total_realizado_segundos_ou_pontos

            col1, col2, col3 = st.columns(3)
            col1.metric("Total Estimado (Concluídos)", f"{total_estimado:,.1f} {estim_unit_display}")
            col2.metric("Total Realizado (Concluídos)", f"{total_realizado:,.1f} {spent_unit_display}")
            col3.metric("Média (Incompatível)", "N/A")
            
            st.caption("Gráfico comparativo oculto pois as unidades são incompatíveis.")

        else:
            # NÃO, as unidades são IGUAIS (ex: pts vs pts ou hs vs hs)
            
            # 5. Calcular os totais
            total_estimado = pd.to_numeric(df_done[estimation_field_id], errors='coerce').fillna(0).sum()
            total_realizado = pd.to_numeric(df_done[timespent_field_id], errors='coerce').fillna(0).sum()
            
            unit_display = "pts" # Padrão
            
            # 6. CONVERSÃO-CHAVE (Se ambos forem campos de tempo em segundos)
            if estim_is_time: # (sabemos que spent_is_time também é True)
                total_estimado = total_estimado / 3600.0
                total_realizado = total_realizado / 3600.0
                unit_display = "hs"

            # 7. Exibir as Métricas (Agora compatíveis)
            col1, col2, col3 = st.columns(3)
            col1.metric(f"Total Estimado (Concluídos)", f"{total_estimado:,.1f} {unit_display}")
            col2.metric(f"Total Realizado (Concluídos)", f"{total_realizado:,.1f} {unit_display}")
            
            if total_estimado > 0:
                ratio = total_realizado / total_estimado
                col3.metric("Rácio (Realizado / Previsto)", f"{ratio:,.2f}")
            else:
                col3.metric("Rácio (Realizado / Previsto)", "N/A")

            # 8. Exibir o Gráfico Comparativo (Agora compatível)
            if total_estimado > 0 or total_realizado > 0:
                
                # --- PONTO DE ALTERAÇÃO 2: Correção do Gráfico Altair ---
                # Esta estrutura é baseada no seu código original (que funciona)
                chart_data = pd.DataFrame({
                    'Tipo': ['Estimado', 'Realizado'],
                    'Valor': [total_estimado, total_realizado],
                    'Unidade': [unit_display, unit_display]
                })
                
                try:
                    import altair as alt
                    
                    base = alt.Chart(chart_data).encode(
                        x=alt.X('Tipo', title=None), # Agrupa por 'Tipo' (Estimado, Realizado)
                        tooltip=['Tipo', 'Valor', 'Unidade']
                    )
                    
                    bars = base.mark_bar().encode(
                        y=alt.Y('Valor', title=f'Total (em {unit_display})'),
                        color=alt.Color('Tipo', legend=alt.Legend(title="Métrica"))
                    )
                    
                    text = base.mark_text(
                        align='center',
                        baseline='bottom',
                        dy=-5 
                    ).encode(
                        text=alt.Text('Valor', format=',.1f')
                    )
                    
                    st.altair_chart(bars + text, use_container_width=True) # Camada simples (bars + text)
                    st.caption(f"Comparativo visual (Ambos em '{unit_display}')")

                except ImportError:
                    st.error("Biblioteca 'altair' não encontrada para gerar o gráfico.")
                except Exception as e:
                    st.error(f"Erro ao gerar gráfico: {e}")
                    
            else:
                st.markdown("<p style='text-align: center; padding: 10px;'>Não há dados de estimativa e tempo gasto para exibir o gráfico.</p>", unsafe_allow_html=True)
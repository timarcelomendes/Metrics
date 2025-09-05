# metrics_calculator.py (VERSÃO FINAL COM CORREÇÃO DE CYCLE TIME)
import streamlit as st
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from jira_connector import get_sprint_issues
from datetime import datetime, timedelta
import plotly.graph_objects as go
from config import DEFAULT_INITIAL_STATES, DEFAULT_DONE_STATES
from security import get_project_config

# --- Funções Auxiliares de Data ---
def find_completion_date(issue, project_config):
    """
    Encontra a data de conclusão, usando o campo personalizado se estiver
    configurado, ou o histórico de status como fallback.
    """
    date_mappings = project_config.get('date_mappings', {})
    completion_field_id = date_mappings.get('completion_date_field_id')

    if completion_field_id and hasattr(issue.fields, completion_field_id):
        completion_date = getattr(issue.fields, completion_field_id)
        if completion_date:
            return pd.to_datetime(completion_date).tz_localize(None)

    global_configs = st.session_state.get('global_configs', {})
    done_states = global_configs.get('status_mapping', {}).get('done', DEFAULT_DONE_STATES)
    
    try:
        if hasattr(issue.changelog, 'histories'):
            for history in reversed(issue.changelog.histories):
                for item in history.items:
                    if item.field == 'status' and item.toString.lower() in [s.lower() for s in done_states]:
                        return pd.to_datetime(history.created).tz_localize(None)
        
        if issue.fields.status.name.lower() in [s.lower() for s in done_states] and issue.fields.resolutiondate:
            return pd.to_datetime(issue.fields.resolutiondate).tz_localize(None)
        
        return None
    except Exception:
        return None

def find_start_date(issue):
    """Encontra a data de início do ciclo de trabalho."""
    status_mapping = st.session_state.get('global_configs', {}).get('status_mapping', {})
    initial_states = status_mapping.get('initial', DEFAULT_INITIAL_STATES)
    try:
        for history in sorted(issue.changelog.histories, key=lambda h: h.created):
            for item in history.items:
                if item.field == 'status' and item.fromString.lower() in initial_states and item.toString.lower() not in initial_states:
                    return pd.to_datetime(history.created).tz_localize(None).normalize()
    except Exception: pass
    created_date = pd.to_datetime(issue.fields.created).tz_localize(None).normalize()
    if issue.fields.status.name.lower() not in initial_states:
        return created_date
    return None

def calculate_lead_time(issue, completion_date=None):
    """Calcula o Lead Time (Criação até Conclusão) em dias."""
    if completion_date is None:
        return None
    creation_date = pd.to_datetime(issue.fields.created).tz_localize(None)
    return (completion_date - creation_date).days

def calculate_cycle_time(issue, completion_date=None):
    """Calcula o Cycle Time (Início do Trabalho até Conclusão) em dias."""
    if completion_date is None:
        return None
        
    initial_states = st.session_state.get('global_configs', {}).get('status_mapping', {}).get('initial', DEFAULT_INITIAL_STATES)
    
    start_date = None
    if hasattr(issue.changelog, 'histories'):
        for history in issue.changelog.histories:
            for item in history.items:
                if item.field == 'status' and item.fromString.lower() in [s.lower() for s in initial_states]:
                    start_date = pd.to_datetime(history.created).tz_localize(None)
                    break
            if start_date:
                break
    
    if start_date:
        return (completion_date - start_date).days
    return None

def calculate_throughput(issues, project_config):
    return len([i for i in issues if find_completion_date(i, project_config) is not None])

def get_filtered_issues(issues):
    """Função auxiliar para remover issues com status ignorados."""
    global_configs = st.session_state.get('global_configs', {})
    status_mapping = global_configs.get('status_mapping', {})
    ignored_states = status_mapping.get('ignored', [])
    
    if not ignored_states:
        return issues
        
    return [issue for issue in issues if issue.fields.status.name.lower() not in ignored_states]

def filter_ignored_issues(raw_issues_list):
    """
    Função central que recebe uma lista de issues e remove aquelas com status ignorados,
    com base nas configurações globais.
    """
    global_configs = st.session_state.get('global_configs', {})
    status_mapping = global_configs.get('status_mapping', {})
    ignored_states = status_mapping.get('ignored', [])
    
    if not ignored_states:
        return raw_issues_list
        
    return [
        issue for issue in raw_issues_list 
        if issue.fields.status.name.lower() not in ignored_states
    ]

def get_issue_estimation(issue, estimation_config):
    """Retorna o valor da estimativa de uma issue, convertendo de segundos para horas se necessário."""
    if not estimation_config or not estimation_config.get('id'):
        return 0.0
        
    field_id = estimation_config['id']
    source = estimation_config.get('source')
    
    value = getattr(issue.fields, field_id, 0) or 0
    
    # Converte de segundos para horas se for um campo de tempo padrão do Jira
    if source == 'standard_time':
        return float(value) / 3600
    
    return float(value)

def calculate_predictability(sprint_issues, estimation_config, project_config):
    if not sprint_issues or not estimation_config.get('id'): return 0.0
    story_points_field = estimation_config.get('id'); total_points_planned = 0; total_points_completed = 0
    for issue in sprint_issues:
        points = get_issue_estimation(issue, estimation_config) or 0
        total_points_planned += points
        if find_completion_date(issue, project_config) is not None:
            completed_points_value = get_issue_estimation(issue, estimation_config) or 0
            total_points_completed += completed_points_value
    if total_points_planned == 0: return 100.0
    return (total_points_completed / total_points_planned) * 100

def generate_sprint_health_summary(issues, predictability, project_config):
    insights = []
    if predictability >= 95: insights.append(f"✅ **Previsibilidade Excelente ({predictability:.0f}%):** O time demonstrou um domínio notável do seu planejamento.")
    elif 80 <= predictability < 95: insights.append(f"✅ **Previsibilidade Saudável ({predictability:.0f}%):** O time é bastante confiável em suas previsões.")
    elif 60 <= predictability < 80: insights.append(f"⚠️ **Previsibilidade em Desenvolvimento ({predictability:.0f}%):** Há espaço para melhorar a precisão do planejamento ou a gestão de interrupções.")
    else: insights.append(f"🚨 **Alerta de Previsibilidade ({predictability:.0f}%):** Forte indicação de que o planejamento não está conectado à entrega.")
    completed_issues = [i for i in issues if find_completion_date(i, project_config) is not None]
    if not completed_issues: insights.append("ℹ️ Não há dados de fluxo ou qualidade, pois nenhuma issue foi concluída."); return insights
    issue_types = [i.fields.issuetype.name.lower() for i in completed_issues]
    bug_count = sum(1 for t in issue_types if 'bug' in t); total_completed = len(completed_issues)
    bug_ratio = (bug_count / total_completed) * 100 if total_completed > 0 else 0
    if bug_ratio > 30: insights.append(f"⚠️ **Foco em Qualidade ({bug_ratio:.0f}% de bugs):** Uma parte considerável do esforço foi para corrigir bugs.")
    cycle_times = [ct for ct in [calculate_cycle_time(i) for i in completed_issues] if ct is not None and ct >= 0]
    if len(cycle_times) > 1:
        avg_cycle_time = np.mean(cycle_times); std_dev_cycle_time = np.std(cycle_times)
        coeff_var = (std_dev_cycle_time / avg_cycle_time) if avg_cycle_time > 0 else 0
        if coeff_var > 0.7: insights.append(f"⚠️ **Fluxo Instável:** O tempo para concluir as tarefas (Cycle Time) variou muito.")
        else: insights.append(f"✅ **Fluxo de Trabalho Estável:** O tempo de conclusão das tarefas foi consistente.")
    return insights

# ############### FUNÇÃO CORRIGIDA ###############
def prepare_burndown_data(client, sprint_obj, estimation_config, project_config):
    """
    Prepara os dados para o gráfico de Burndown de uma sprint.
    """
    estimation_field_id = estimation_config.get('id')
    if not estimation_field_id:
        st.warning("Burndown não pode ser calculado sem um campo de estimativa configurado para o projeto.")
        return pd.DataFrame()

    try:
        start_date = pd.to_datetime(sprint_obj.startDate).tz_localize(None).normalize()
        end_date = pd.to_datetime(sprint_obj.endDate).tz_localize(None).normalize()
        sprint_id = sprint_obj.id
    except AttributeError:
        return pd.DataFrame()

    issues = get_sprint_issues(client, sprint_id)
    if not issues: return pd.DataFrame()
        
    total_points_planned = sum(get_issue_estimation(i, estimation_config) for i in issues)
    
    date_range = pd.date_range(start=start_date, end=end_date, freq='D')
    points_completed_per_day = {day: 0 for day in date_range}
    
    for issue in issues:
        completion_date = find_completion_date(issue, project_config)
        if completion_date and start_date <= completion_date <= end_date:
            points = get_issue_estimation(issue, estimation_config)
            points_completed_per_day[completion_date] += points

    burndown_values = []
    remaining_points = total_points_planned
    for day in date_range:
        remaining_points -= points_completed_per_day.get(day, 0)
        burndown_values.append(remaining_points)
        
    ideal_line = np.linspace(total_points_planned, 0, len(date_range)) if len(date_range) > 0 else []
    
    return pd.DataFrame({
        'Data': date_range,
        'Pontos Restantes (Real)': burndown_values,
        'Linha Ideal': ideal_line
    }).set_index('Data')

def prepare_cfd_data(issues, start_date, end_date):
    """
    Prepara os dados para o Diagrama de Fluxo Cumulativo (CFD), com a lógica de
    fuso horário corrigida.
    """
    if not issues:
        return pd.DataFrame(), {}

    global_configs = st.session_state.get('global_configs', {})
    initial_states = global_configs.get('initial_states', DEFAULT_INITIAL_STATES)
    done_states = global_configs.get('done_states', DEFAULT_DONE_STATES)

    all_statuses = set()
    transitions = []

    for issue in issues:
        # --- CORREÇÃO AQUI: Remove o fuso horário ---
        created_date = pd.to_datetime(issue.fields.created).tz_localize(None).normalize()
        transitions.append({'date': created_date, 'status': 'Criado', 'change': 1})
        all_statuses.add('Criado')

        if hasattr(issue.changelog, 'histories'):
            for history in issue.changelog.histories:
                for item in history.items:
                    if item.field == 'status':
                        # --- CORREÇÃO AQUI: Remove o fuso horário ---
                        transition_date = pd.to_datetime(history.created).tz_localize(None).normalize()
                        transitions.append({'date': transition_date, 'status': item.fromString, 'change': -1})
                        transitions.append({'date': transition_date, 'status': item.toString, 'change': 1})
                        all_statuses.add(item.fromString)
                        all_statuses.add(item.toString)

    if not transitions:
        return pd.DataFrame(), {}

    df = pd.DataFrame(transitions)
    
    # Garante que as datas de input sejam do tipo correto
    start_date = pd.to_datetime(start_date)
    end_date = pd.to_datetime(end_date)
    
    df_filtered = df[df['date'].between(start_date, end_date)]
    
    if df_filtered.empty:
        return pd.DataFrame(), {}

    cfd_pivot = df_filtered.pivot_table(index='date', columns='status', values='change', aggfunc='sum').fillna(0)
    cfd_cumulative = cfd_pivot.cumsum()

    wip_statuses = [s for s in cfd_cumulative.columns if s.lower() not in initial_states and s.lower() not in done_states]
    wip_df = pd.DataFrame({'Data': cfd_cumulative.index, 'WIP': cfd_cumulative[wip_statuses].sum(axis=1)})

    return cfd_cumulative, wip_df

def prepare_project_burnup_data(issues, unit, estimation_config, project_config):
    """Prepara o burnup, agora ignorando issues canceladas."""
    valid_issues = get_filtered_issues(issues)

    if unit == 'points' and (not estimation_config or not estimation_config.get('id')):
        st.warning("Para análise por pontos, configure um 'Campo de Estimativa' para este projeto.")
        return pd.DataFrame()
    
    data = []
    for issue in valid_issues: # Usa a lista filtrada
        created_date = pd.to_datetime(issue.fields.created).tz_localize(None).normalize()
        completion_date = find_completion_date(issue, project_config)
        value = get_issue_estimation(issue, estimation_config) if unit == 'points' else 1
        data.append({'created': created_date, 'resolved': completion_date, 'value': value})
        
    df = pd.DataFrame(data)
    if df.empty or df['created'].dropna().empty: return pd.DataFrame()
    
    start_date = df['created'].min(); end_date = pd.Timestamp.now(tz=None).normalize()
    date_range = pd.date_range(start=start_date, end=end_date, freq='D')
    
    scope_over_time = [df[df['created'] <= day]['value'].sum() for day in date_range]
    completed_over_time = [df[(df['resolved'].notna()) & (df['resolved'] <= day)]['value'].sum() for day in date_range]
    
    return pd.DataFrame({'Data': date_range, 'Escopo Total': scope_over_time, 'Trabalho Concluído': completed_over_time}).set_index('Data')

def calculate_trend_and_forecast(burnup_df, trend_weeks):
    """
    Calcula a linha de tendência, a previsão de entrega e as velocidades.
    Retorna a figura do gráfico, a data de previsão e as métricas.
    """
    if burnup_df.empty or 'Trabalho Concluído' not in burnup_df.columns:
        return None, None, 0, 0

    # --- Cálculo da Velocidade Média (Histórica) ---
    total_completed = burnup_df['Trabalho Concluído'].iloc[-1]
    first_work_day = burnup_df[burnup_df['Trabalho Concluído'] > 0].index.min()
    last_day = burnup_df.index.max()
    
    avg_weekly_velocity = 0
    if pd.notna(first_work_day):
        duration_days = (last_day - first_work_day).days
        if duration_days > 0:
            avg_daily_velocity = total_completed / duration_days
            avg_weekly_velocity = avg_daily_velocity * 7
        elif total_completed > 0:
            avg_weekly_velocity = total_completed * 7

    # --- Cálculo da Velocidade de Tendência (Recente) ---
    end_date = burnup_df.index.max()
    start_date_trend = end_date - pd.Timedelta(weeks=trend_weeks)
    trend_data = burnup_df[burnup_df.index >= start_date_trend]
    
    trend_weekly_velocity = 0
    if len(trend_data) > 1:
        total_work_increase = trend_data['Trabalho Concluído'].iloc[-1] - trend_data['Trabalho Concluído'].iloc[0]
        days_in_trend = (trend_data.index.max() - trend_data.index.min()).days
        trend_weekly_velocity = (total_work_increase / days_in_trend * 7) if days_in_trend > 0 else 0

    # --- Cálculo da Previsão de Entrega (Forecast) ---
    total_scope = burnup_df['Escopo Total'].iloc[-1]
    remaining_work = total_scope - total_completed
    forecast_date = None
    
    if trend_weekly_velocity > 0 and remaining_work > 0:
        days_to_complete = (remaining_work / trend_weekly_velocity) * 7
        forecast_date = end_date + pd.Timedelta(days=days_to_complete)

    # --- Construção da Figura do Gráfico (Burnup) ---
    fig = go.Figure()
    burnup_df_cleaned = burnup_df.dropna()
    fig.add_trace(go.Scatter(x=burnup_df_cleaned.index, y=burnup_df_cleaned['Escopo Total'], mode='lines', name='Escopo Total', line=dict(color='red', width=2)))
    fig.add_trace(go.Scatter(x=burnup_df_cleaned.index, y=burnup_df_cleaned['Trabalho Concluído'], mode='lines', name='Trabalho Concluído', line=dict(color='blue', width=3)))
    
    if trend_weekly_velocity > 0 and len(trend_data) > 1:
        X = np.array(range(len(trend_data))).reshape(-1, 1)
        model = LinearRegression().fit(X, trend_data['Trabalho Concluído'])
        trend_line = model.predict(X)
        
        if forecast_date:
            future_days = (forecast_date - trend_data.index[-1]).days
            if future_days > 0:
                future_X = np.array(range(len(trend_data), len(trend_data) + future_days)).reshape(-1, 1)
                future_trend = model.predict(future_X)
                extended_dates = pd.to_datetime([trend_data.index[-1] + timedelta(days=i) for i in range(1, future_days + 1)])
                full_trend_dates = trend_data.index.append(extended_dates)
                full_trend_values = np.concatenate([trend_line, future_trend])
                fig.add_trace(go.Scatter(x=full_trend_dates, y=full_trend_values, mode='lines', name='Tendência', line=dict(color='green', dash='dash')))
    
    fig.update_layout(
        title_text=None,
        xaxis_title="Data",
        yaxis_title=f"Escopo ({st.session_state.get('unit_display', 'itens')})",
        legend_title="Legenda",
        template="plotly_white"
    )
    
    return fig, forecast_date, trend_weekly_velocity, avg_weekly_velocity

def calculate_time_in_status(issue, target_status):
    """Calcula o tempo total que uma issue passou em um ou mais status."""
    total_time = pd.Timedelta(0)
    try:
        for history in issue.changelog.histories:
            for item in history.items:
                if item.field == 'status':
                    if item.fromString.lower() in target_status:
                        # Assume que o tempo no status é a diferença para a próxima mudança
                        total_time += pd.to_datetime(history.created) - pd.to_datetime(issue.fields.created) # Simplificação
    except Exception:
        return 0 # Retorna 0 se houver erro ou o histórico for complexo
    return total_time.total_seconds() / 86400 # em dias

def calculate_flow_efficiency(issue):
    """Calcula a Eficiência de Fluxo (simplificado)."""
    cycle_time = calculate_cycle_time(issue)
    if cycle_time is None or cycle_time == 0:
        return None
    
    # Supondo que status de espera são 'blocked', 'waiting for approval', etc.
    # Esta é uma simplificação. Uma implementação real precisaria de um mapeamento de status de "espera".
    waiting_statuses = ['blocked', 'impedimento'] 
    waiting_time = calculate_time_in_status(issue, waiting_statuses)
    
    active_time = cycle_time - waiting_time
    return (active_time / cycle_time) * 100 if cycle_time > 0 else 0

def get_aging_wip(issues):
    """
    Calcula há quantos dias úteis um item está no seu status atual.
    Esta é a versão final e à prova de falhas.
    """
    global_configs = st.session_state.get('global_configs', {})
    initial_states = global_configs.get('initial_states', DEFAULT_INITIAL_STATES)
    done_states = global_configs.get('done_states', DEFAULT_DONE_STATES)
    
    # --- Lógica de Identificação Corrigida ---
    wip_issues = [
        i for i in issues 
        if hasattr(i.fields, 'status') and 
        i.fields.status.name.lower() not in [s.lower() for s in initial_states] and
        i.fields.status.name.lower() not in [s.lower() for s in done_states]
    ]
    
    if not wip_issues:
        return pd.DataFrame(columns=['Issue', 'Status Atual', 'Dias no Status'])

    wip_data = []
    today = datetime.now().date()

    for issue in wip_issues:
        # --- Lógica de Cálculo de Idade Corrigida ---
        last_status_change_date = pd.to_datetime(issue.fields.created).date() # Padrão
        if hasattr(issue.changelog, 'histories'):
            for history in reversed(issue.changelog.histories):
                for item in history.items:
                    if item.field == 'status':
                        last_status_change_date = pd.to_datetime(history.created).date()
                        break
                else: continue
                break
        
        days_in_status = np.busday_count(last_status_change_date, today)
        
        wip_data.append({
            'Issue': issue.key,
            'Status Atual': issue.fields.status.name,
            'Dias no Status': days_in_status
        })

    df = pd.DataFrame(wip_data)
    return df.sort_values(by='Dias no Status', ascending=False)

def calculate_flow_efficiency(issue):
    """Calcula a eficiência do fluxo (tempo em atividade vs. tempo total)."""
    cycle_time = calculate_cycle_time(issue)
    if cycle_time is None or cycle_time == 0:
        return None
    # Esta é uma implementação simplificada.
    return 25.0 # Placeholder

def calculate_velocity(sprint_issues, estimation_config):
    if not sprint_issues or not estimation_config.get('id'): return 0
    status_mapping = st.session_state.get('global_configs', {}).get('status_mapping', {})
    done_states = status_mapping.get('done', DEFAULT_DONE_STATES)
    completed_points = 0
    for issue in sprint_issues:
        if issue.fields.status.name.lower() in done_states:
            completed_points += get_issue_estimation(issue, estimation_config)
    return completed_points

def calculate_predictability(sprint_issues, estimation_config):
    if not sprint_issues or not estimation_config.get('id'): return 0.0
    status_mapping = st.session_state.get('global_configs', {}).get('status_mapping', {})
    done_states = status_mapping.get('done', DEFAULT_DONE_STATES)
    total_committed_points = 0; total_completed_points = 0
    for issue in sprint_issues:
        points = get_issue_estimation(issue, estimation_config)
        total_committed_points += points
        if issue.fields.status.name.lower() in done_states:
            total_completed_points += points
    if total_committed_points == 0: return 100.0 if total_completed_points == 0 else 0.0
    return (total_completed_points / total_committed_points) * 100

def calculate_sprint_defects(sprint_issues):
    """Calcula a quantidade de defeitos (bugs) concluídos na sprint."""
    if not sprint_issues: return 0
    
    # Usa as configurações da sessão
    global_configs = st.session_state.get('global_configs', {})
    done_states = global_configs.get('done_states', DEFAULT_DONE_STATES)
    
    defect_count = 0
    for issue in sprint_issues:
        issue_type_lower = issue.fields.issuetype.name.lower()
        if 'bug' in issue_type_lower or 'defeito' in issue_type_lower:
            if issue.fields.status.name.lower() in [s.lower() for s in done_states]:
                defect_count += 1
    return defect_count

def calculate_sprint_goal_success_rate(sprints, threshold, estimation_config):
    """Calcula a taxa de sucesso de sprints com base num limiar de previsibilidade."""
    if not sprints:
        return 0.0
    
    successful_sprints = 0
    for sprint in sprints:
        # Passa a configuração para a função de previsibilidade
        sprint_issues = get_sprint_issues(st.session_state.jira_client, sprint.id)
        predictability = calculate_predictability(sprint_issues, estimation_config)
        if predictability >= threshold:
            successful_sprints += 1
            
    return (successful_sprints / len(sprints)) * 100 if sprints else 0.0

def prepare_burndown_data_by_count(client, sprint_obj, project_config):
    """Prepara os dados para o gráfico de Burndown por CONTAGEM DE ISSUES."""
    try:
        start_date = pd.to_datetime(sprint_obj.startDate).tz_localize(None).normalize()
        end_date = pd.to_datetime(sprint_obj.endDate).tz_localize(None).normalize()
        sprint_id = sprint_obj.id
    except AttributeError:
        return pd.DataFrame()

    issues = get_sprint_issues(client, sprint_id)
    if not issues: return pd.DataFrame()

    total_issues_planned = len(issues)
    date_range = pd.date_range(start=start_date, end=end_date, freq='D')
    issues_completed_per_day = {day: 0 for day in date_range}

    for issue in issues:
        completion_date = find_completion_date(issue, project_config)
        if completion_date and start_date <= completion_date <= end_date:
            issues_completed_per_day[completion_date] += 1

    burndown_values = []
    remaining_issues = total_issues_planned
    for day in date_range:
        remaining_issues -= issues_completed_per_day.get(day, 0)
        burndown_values.append(remaining_issues)

    ideal_line = np.linspace(total_issues_planned, 0, len(date_range)) if len(date_range) > 0 else []
    
    return pd.DataFrame({
        'Data': date_range,
        'Issues Restantes (Real)': burndown_values,
        'Linha Ideal': ideal_line
    }).set_index('Data')

def prepare_burndown_data_by_estimation(client, sprint_obj, estimation_config, project_config):
    """Prepara os dados para o gráfico de Burndown por um CAMPO DE ESTIMATIVA."""
    try:
        start_date = pd.to_datetime(sprint_obj.startDate).tz_localize(None).normalize()
        end_date = pd.to_datetime(sprint_obj.endDate).tz_localize(None).normalize()
        sprint_id = sprint_obj.id
    except AttributeError: return pd.DataFrame()

    issues = get_sprint_issues(client, sprint_id)
    if not issues: return pd.DataFrame()

    total_points_planned = sum(get_issue_estimation(i, estimation_config) for i in issues)
    date_range = pd.date_range(start=start_date, end=end_date, freq='D')
    points_completed_per_day = {day: 0 for day in date_range}

    for issue in issues:
        completion_date = find_completion_date(issue, project_config)
        if completion_date and start_date <= completion_date <= end_date:
            points = get_issue_estimation(issue, estimation_config)
            points_completed_per_day[completion_date] += points

    burndown_values = []; remaining_points = total_points_planned
    for day in date_range:
        remaining_points -= points_completed_per_day.get(day, 0)
        burndown_values.append(remaining_points)
        
    ideal_line = np.linspace(total_points_planned, 0, len(date_range)) if len(date_range) > 0 else []
    
    return pd.DataFrame({
        'Data': date_range,
        'Pontos Restantes (Real)': burndown_values,
        'Linha Ideal': ideal_line
    }).set_index('Data')

def calculate_executive_summary_metrics(project_issues, project_config):
    """Calcula todas as métricas, agora com a lógica de fuso horário corrigida."""
    if not project_issues:
        return {'completion_pct': 0, 'deliveries_month': 0, 'avg_deadline_diff': 0, 'schedule_adherence': 0}

    total_issues = len(project_issues)
    completed_issues_list = [i for i in project_issues if find_completion_date(i, project_config) is not None]
    
    completion_pct = (len(completed_issues_list) / total_issues) * 100 if total_issues > 0 else 0

    current_month = datetime.now().month; current_year = datetime.now().year
    deliveries_month = len([
        i for i in completed_issues_list 
        if (cd := find_completion_date(i, project_config)) and cd.month == current_month and cd.year == current_year
    ])

    date_mappings = project_config.get('date_mappings', {}); due_date_field_id = date_mappings.get('due_date_field_id')
    
    deadline_diffs = []
    if due_date_field_id:
        for i in completed_issues_list:
            if hasattr(i.fields, due_date_field_id) and getattr(i.fields, due_date_field_id):
                due_date = pd.to_datetime(getattr(i.fields, due_date_field_id)).tz_localize(None).normalize()
                completion_date = find_completion_date(i, project_config)
                if completion_date:
                    deadline_diffs.append((completion_date.normalize() - due_date).days)
    
    avg_deadline_diff = np.mean(deadline_diffs) if deadline_diffs else 0
    
    schedule_adherence = calculate_schedule_adherence(project_issues, project_config)
    
    return {
        'completion_pct': completion_pct, 'deliveries_month': deliveries_month,
        'avg_deadline_diff': avg_deadline_diff, 'schedule_adherence': schedule_adherence
    }

def calculate_throughput_trend(project_issues, num_weeks=4):
    """Calcula o número de entregas por semana para as últimas semanas."""
    if not project_issues:
        return pd.DataFrame({'Semana': [], 'Entregas': []})

    completed_issues = [{'completion_date': find_completion_date(i)} for i in project_issues]
    df = pd.DataFrame(completed_issues).dropna()
    
    if df.empty:
        return pd.DataFrame({'Semana': [], 'Entregas': []})

    df['completion_date'] = pd.to_datetime(df['completion_date'])
    df = df[df['completion_date'] >= pd.Timestamp.now() - pd.DateOffset(weeks=num_weeks)]
    
    # Agrupa por semana, usando o final da semana como rótulo
    trend = df.groupby(pd.Grouper(key='completion_date', freq='W-MON')).size().reset_index(name='Entregas')
    trend['Semana'] = trend['completion_date'].dt.strftime('Semana %U')
    
    return trend[['Semana', 'Entregas']]

def calculate_risk_level(probability, impact):
    """
    Calcula o nível de risco e a cor correspondente com base na probabilidade e impacto.
    """
    level_map = {'Baixa': 1, 'Média': 2, 'Alta': 3}
    prob_score = level_map.get(probability, 1)
    impact_score = level_map.get(impact, 1)
    
    risk_score = prob_score * impact_score
    
    if risk_score <= 2:
        return "Baixo", "#28a745" # Verde
    elif risk_score <= 4:
        return "Moderado", "#ffc107" # Amarelo
    elif risk_score <= 6:
        return "Alto", "#fd7e14" # Laranja
    else: # risk_score > 6
        return "Crítico", "#dc3545" # Vermelho

def calculate_time_to_first_response(issue, first_response_field_id):
    """Calcula o tempo em horas entre a criação e o primeiro atendimento."""
    if not hasattr(issue.fields, first_response_field_id) or not getattr(issue.fields, first_response_field_id):
        return None
        
    creation_date = pd.to_datetime(issue.fields.created)
    response_date = pd.to_datetime(getattr(issue.fields, first_response_field_id))
    
    # Usa apenas dias úteis (segunda a sexta)
    business_hours = np.busday_count(creation_date.date(), response_date.date()) * 8
    return business_hours

def calculate_sla_metrics(issues):
    """
    Calcula as métricas de SLA com base nos campos configurados.
    """
    global_configs = st.session_state.get('global_configs', {})
    sla_configs = global_configs.get('sla_fields', {})
    sla_field_name = sla_configs.get('sla_hours_field')
    response_field_name = sla_configs.get('first_response_field')

    # Busca os IDs dos campos
    all_fields_map = {f['name']: f['id'] for f in global_configs.get('custom_fields', [])}
    sla_field_id = all_fields_map.get(sla_field_name)
    response_field_id = all_fields_map.get(response_field_name)
    
    if not sla_field_id or not response_field_id:
        return {'met_sla_pct': 'N/A', 'violated_sla_pct': 'N/A', 'avg_time_to_response': 'N/A'}

    total_with_response = 0
    met_sla_count = 0
    all_response_times = []

    for issue in issues:
        time_to_response = calculate_time_to_first_response(issue, response_field_id)
        sla_hours = getattr(issue.fields, sla_field_id, None)

        if time_to_response is not None and sla_hours is not None:
            total_with_response += 1
            all_response_times.append(time_to_response)
            if time_to_response <= float(sla_hours):
                met_sla_count += 1
    
    if total_with_response == 0:
        return {'met_sla_pct': 0, 'violated_sla_pct': 0, 'avg_time_to_response': 0}

    met_sla_pct = (met_sla_count / total_with_response) * 100
    violated_sla_pct = 100 - met_sla_pct
    avg_time_to_response = np.mean(all_response_times)

    return {
        'met_sla_pct': f"{met_sla_pct:.1f}%",
        'violated_sla_pct': f"{violated_sla_pct:.1f}%",
        'avg_time_to_response': f"{avg_time_to_response:.1f}h"
    }

def calculate_estimation_accuracy(completed_issues, estimation_config):
    """
    Calcula a soma do estimado vs. realizado para uma lista de issues concluídas.
    """
    total_estimated = 0
    total_actual = 0

    if not completed_issues:
        return {'total_estimated': 0, 'total_actual': 0, 'accuracy_ratio': 100}

    for issue in completed_issues:
        estimated_value = get_issue_estimation(issue, estimation_config) or 0
        
        time_spent_seconds = issue.fields.timespent if hasattr(issue.fields, 'timespent') and issue.fields.timespent is not None else 0
        actual_value = time_spent_seconds / 3600 # Converte para horas

        # Apenas considera issues que tinham uma estimativa
        if estimated_value > 0:
            total_estimated += estimated_value
            total_actual += actual_value
    
    accuracy_ratio = (total_actual / total_estimated) * 100 if total_estimated > 0 else 100

    return {
        'total_estimated': total_estimated,
        'total_actual': total_actual,
        'accuracy_ratio': accuracy_ratio
    }

def calculate_schedule_adherence(issues, project_config):
    """
    Calcula a percentagem de issues com 'due date' que foram concluídas no prazo,
    usando os campos de data personalizados.
    """
    date_mappings = project_config.get('date_mappings', {})
    due_date_field_id = date_mappings.get('due_date_field_id')

    if not due_date_field_id:
        return 0.0 # Retorna 0 se o campo de data prevista não estiver mapeado

    with_due_date = 0
    met_deadline = 0

    for issue in issues:
        if hasattr(issue.fields, due_date_field_id) and getattr(issue.fields, due_date_field_id):
            with_due_date += 1
            completion_date = find_completion_date(issue, project_config)
            
            if completion_date:
                due_date = pd.to_datetime(getattr(issue.fields, due_date_field_id)).tz_localize(None)
                if completion_date <= due_date:
                    met_deadline += 1
    
    if with_due_date == 0:
        return 0.0
    
    return (met_deadline / with_due_date) * 100

def calculate_executive_summary_metrics(project_issues, project_config):
    """Calcula todas as métricas, agora com a lógica de fuso horário corrigida."""
    if not project_issues:
        return {'completion_pct': 0, 'deliveries_month': 0, 'avg_deadline_diff': 0, 'schedule_adherence': 0}

    total_issues = len(project_issues)
    completed_issues_list = [i for i in project_issues if find_completion_date(i, project_config) is not None]
    
    completion_pct = (len(completed_issues_list) / total_issues) * 100 if total_issues > 0 else 0

    current_month = datetime.now().month; current_year = datetime.now().year
    deliveries_month = len([
        i for i in completed_issues_list 
        if (cd := find_completion_date(i, project_config)) and cd.month == current_month and cd.year == current_year
    ])

    date_mappings = project_config.get('date_mappings', {}); due_date_field_id = date_mappings.get('due_date_field_id')
    
    deadline_diffs = []
    if due_date_field_id:
        for i in completed_issues_list:
            if hasattr(i.fields, due_date_field_id) and getattr(i.fields, due_date_field_id):
                # --- CORREÇÃO AQUI: Remove o fuso horário da data prevista ---
                due_date = pd.to_datetime(getattr(i.fields, due_date_field_id)).tz_localize(None).normalize()
                completion_date = find_completion_date(i, project_config)
                if completion_date:
                    deadline_diffs.append((completion_date.normalize() - due_date).days)
    
    avg_deadline_diff = np.mean(deadline_diffs) if deadline_diffs else 0
    
    schedule_adherence = calculate_schedule_adherence(project_issues, project_config)
    
    return {
        'completion_pct': completion_pct, 'deliveries_month': deliveries_month,
        'avg_deadline_diff': avg_deadline_diff, 'schedule_adherence': schedule_adherence,
        'total_issues': total_issues, 'completed_issues': len(completed_issues_list)
    }
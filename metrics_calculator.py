# metrics_calculator.py (VERSÃO CORRIGIDA E SEM DUPLICADOS)
import streamlit as st
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from datetime import datetime, timedelta
import plotly.graph_objects as go
from config import DEFAULT_INITIAL_STATES, DEFAULT_DONE_STATES
from security import *
from datetime import datetime, timedelta, date

# --- Funções Auxiliares de Data ---
def find_completion_date(issue, project_config):
    """
    Encontra a data de conclusão real de uma issue analisando seu histórico (changelog).
    Retorna a data da última transição para um status da categoria 'Done'.
    """
    if not issue or not hasattr(issue, 'changelog') or not issue.changelog:
        return None

    # Usa a chave 'done' (minúscula) para consistência
    done_statuses = [s.lower() for s in project_config.get('status_mapping', {}).get('done', [])]

    if not done_statuses:
        resolution_date = getattr(issue.fields, 'resolutiondate', None)
        return pd.to_datetime(resolution_date).date() if resolution_date else None

    completion_dates = []
    for history in issue.changelog.histories:
        for item in history.items:
            if item.field == 'status' and item.toString.lower() in done_statuses:
                completion_dates.append(pd.to_datetime(history.created).date())

    return max(completion_dates) if completion_dates else None

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

def calculate_lead_time(issue, completion_date):
    """Calcula o Lead Time em dias."""
    if completion_date:
        creation_date = pd.to_datetime(issue.fields.created).tz_localize(None)
        if isinstance(completion_date, date) and not isinstance(completion_date, datetime):
            completion_date = pd.to_datetime(completion_date)
        return (completion_date - creation_date).days
    return None

def calculate_cycle_time(issue, completion_date, project_config):
    """Calcula o Cycle Time em dias, com conversão de data robusta."""
    if not completion_date:
        return None

    # Garante que a data de conclusão seja um objeto datetime para a subtração
    if isinstance(completion_date, date) and not isinstance(completion_date, datetime):
        completion_date = pd.to_datetime(completion_date).tz_localize(None)
    elif isinstance(completion_date, datetime) and completion_date.tzinfo is None:
        completion_date = completion_date.tz_localize(None)

    status_mapping = project_config.get('status_mapping', {})
    in_progress_statuses = [s.lower() for s in status_mapping.get('in_progress', [])]
    first_start_date = None
    if in_progress_statuses and hasattr(issue.changelog, 'histories'):
        start_dates = []
        for history in issue.changelog.histories:
            for item in history.items:
                if item.field == 'status' and item.toString.lower() in in_progress_statuses:
                    start_dates.append(pd.to_datetime(history.created).tz_localize(None))
        if start_dates:
            first_start_date = min(start_dates)
            
    if first_start_date is None:
        first_start_date = pd.to_datetime(issue.fields.created).tz_localize(None)

    time_delta = completion_date - first_start_date
    return max(0, time_delta.total_seconds() / (24 * 3600))

def calculate_aggregated_metric(df, dimension, measure, agg):
    if not dimension or dimension not in df.columns:
        return pd.DataFrame({'Dimensão': [], 'Medida': []})

    if measure and measure.startswith('Tempo em: '):
        if measure not in df.columns:
            return pd.DataFrame({'Dimensão': [], 'Medida': []})
        agg_df = df.groupby(dimension)[measure].mean().reset_index(name='Medida')

    elif measure == 'Contagem de Issues':
        agg_df = df.groupby(dimension).size().reset_index(name='Medida')

    elif agg == 'Contagem Distinta':
        if measure not in df.columns: return pd.DataFrame({'Dimensão': [], 'Medida': []})
        agg_df = df.groupby(dimension)[measure].nunique().reset_index(name='Medida')

    else:
        if measure not in df.columns: return pd.DataFrame({'Dimensão': [], 'Medida': []})
        numeric_series = pd.to_numeric(df[measure], errors='coerce')
        grouped_data = numeric_series.groupby(df[dimension])
        if agg == 'Soma': agg_df = grouped_data.sum().reset_index(name='Medida')
        elif agg == 'Média': agg_df = grouped_data.mean().reset_index(name='Medida')
        else: agg_df = grouped_data.count().reset_index(name='Medida')

    return agg_df.rename(columns={dimension: 'Dimensão'})

def calculate_kpi(df, kpi_config):
    """
    Calcula o valor de um KPI com base na configuração fornecida.
    Esta versão foi CORRIGIDA para extrair corretamente as configurações.
    """
    if not isinstance(kpi_config, dict):
        return None, "Configuração do KPI inválida."

    # A configuração real está aninhada, vamos extraí-la.
    config = kpi_config

    num_op = config.get('num_op')
    num_field = config.get('num_field')
    use_den = config.get('use_den', False)

    def calculate_value(op, field):
        if op == 'Contagem':
            return len(df)
        if field not in df.columns:
            # Retorna None e uma mensagem de erro se o campo não existir
            return None, f"Campo '{field}' não encontrado no DataFrame."
        if op == 'Soma':
            return df[field].sum()
        if op == 'Média':
            return df[field].mean()
        # Retorna None e uma mensagem de erro se a operação for desconhecida
        return None, f"Operação '{op}' desconhecida."

    # Calcula o numerador
    numerator, error = calculate_value(num_op, num_field)
    if error:
        # Se houver um erro no numerador, retorna-o imediatamente
        return None, error

    denominator = None
    if use_den:
        den_op = config.get('den_op')
        den_field = config.get('den_field')
        # Calcula o denominador
        denominator, error = calculate_value(den_op, den_field)
        if error:
            # Se houver um erro no denominador, retorna-o imediatamente
            return None, error

    if denominator is not None:
        if denominator == 0:
            # Evita divisão por zero
            return "N/A", "O denominador do KPI é zero."
        # Retorna a percentagem
        return (numerator / denominator), None
    else:
        # Retorna apenas o valor do numerador
        return numerator, None

def calculate_pivot_table(df, rows, columns, values, aggfunc='Soma'):
    agg_map = {'Soma': 'sum', 'Média': 'mean', 'Contagem': 'count'}

    if rows in df.columns and columns in df.columns and values in df.columns:
        pivot_df = df.pivot_table(
            index=rows, columns=columns, values=values,
            aggfunc=agg_map.get(aggfunc, 'sum'), fill_value=0
        )
        return pivot_df
    return pd.DataFrame()

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

def filter_ignored_issues(raw_issues_list, project_config={}):
    """
    Função central que recebe uma lista de issues e remove aquelas com status ignorados,
    usando a configuração do projeto ou, como fallback, as configurações globais.
    """
    # Tenta obter o mapeamento do projeto primeiro
    status_mapping = project_config.get('status_mapping', {})
    
    # Se não houver mapeamento no projeto, usa o global
    if not status_mapping:
        global_configs = st.session_state.get('global_configs', {})
        status_mapping = global_configs.get('status_mapping', {})

    ignored_states = [s.lower() for s in status_mapping.get('ignored', [])]

    if not ignored_states:
        return raw_issues_list

    return [
        issue for issue in raw_issues_list
        if issue.fields.status.name.lower() not in ignored_states
    ]

def get_issue_estimation(issue, estimation_config):
    """Retorna a estimativa de uma issue com base na configuração do projeto."""
    if not estimation_config:
        return None
    field_id = estimation_config.get('id')
    if hasattr(issue.fields, field_id) and getattr(issue.fields, field_id) is not None:
        return getattr(issue.fields, field_id)
    return 0

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
    cycle_times = [ct for ct in [calculate_cycle_time(i, find_completion_date(i, project_config), project_config) for i in completed_issues] if ct is not None and ct >= 0]
    if len(cycle_times) > 1:
        avg_cycle_time = np.mean(cycle_times); std_dev_cycle_time = np.std(cycle_times)
        coeff_var = (std_dev_cycle_time / avg_cycle_time) if avg_cycle_time > 0 else 0
        if coeff_var > 0.7: insights.append(f"⚠️ **Fluxo Instável:** O tempo para concluir as tarefas (Cycle Time) variou muito.")
        else: insights.append(f"✅ **Fluxo de Trabalho Estável:** O tempo de conclusão das tarefas foi consistente.")
    return insights

def prepare_burndown_data(client, sprint_obj, estimation_config, project_config):
    """
    Prepara os dados para o gráfico de Burndown de uma sprint.
    """
    from jira_connector import get_sprint_issues
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
        created_date = pd.to_datetime(issue.fields.created).tz_localize(None).normalize()
        transitions.append({'date': created_date, 'status': 'Criado', 'change': 1})
        all_statuses.add('Criado')

        if hasattr(issue.changelog, 'histories'):
            for history in issue.changelog.histories:
                for item in history.items:
                    if item.field == 'status':
                        transition_date = pd.to_datetime(history.created).tz_localize(None).normalize()
                        transitions.append({'date': transition_date, 'status': item.fromString, 'change': -1})
                        transitions.append({'date': transition_date, 'status': item.toString, 'change': 1})
                        all_statuses.add(item.fromString)
                        all_statuses.add(item.toString)

    if not transitions:
        return pd.DataFrame(), {}

    df = pd.DataFrame(transitions)

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
    """Prepara o burnup, com o tipo de data."""
    valid_issues = get_filtered_issues(issues)

    if unit == 'points' and (not estimation_config or not estimation_config.get('id')):
        st.warning("Para análise por pontos/horas, configure um 'Campo de Estimativa' para este projeto.")
        return pd.DataFrame()

    is_time_based = estimation_config.get('source') == 'standard_time'

    data = []
    for issue in valid_issues:
        created_date = pd.to_datetime(issue.fields.created).tz_localize(None).normalize()
        completion_date = find_completion_date(issue, project_config)
        
        value = 0
        if unit == 'count':
            value = 1
        elif unit == 'points':
            raw_value = get_issue_estimation(issue, estimation_config) or 0
            value = (raw_value / 3600) if is_time_based else raw_value
        
        data.append({'created': created_date, 'resolved': completion_date, 'value': value})

    df = pd.DataFrame(data)
    if df.empty or df['created'].dropna().empty: return pd.DataFrame()

    df['resolved'] = pd.to_datetime(df['resolved'])

    start_date = df['created'].min()
    end_date = pd.Timestamp.now(tz=None).normalize()
    date_range = pd.date_range(start=start_date, end=end_date, freq='D')

    scope_over_time = [df[df['created'] <= day]['value'].sum() for day in date_range]
    completed_over_time = [df[(df['resolved'].notna()) & (df['resolved'] <= day)]['value'].sum() for day in date_range]

    return pd.DataFrame({
        'Data': date_range, 
        'Escopo Total': scope_over_time, 
        'Trabalho Concluído': completed_over_time
    }).set_index('Data')

def calculate_trend_and_forecast(burnup_df, trend_weeks):
    """
    Calcula a linha de tendência, a previsão de entrega e as velocidades.
    Retorna a figura do gráfico, a data de previsão e as métricas.
    """
    if burnup_df.empty or 'Trabalho Concluído' not in burnup_df.columns:
        return None, None, 0, 0

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

    end_date = burnup_df.index.max()
    start_date_trend = end_date - pd.Timedelta(weeks=trend_weeks)
    trend_data = burnup_df[burnup_df.index >= start_date_trend]

    trend_weekly_velocity = 0
    if len(trend_data) > 1:
        total_work_increase = trend_data['Trabalho Concluído'].iloc[-1] - trend_data['Trabalho Concluído'].iloc[0]
        days_in_trend = (trend_data.index.max() - trend_data.index.min()).days
        trend_weekly_velocity = (total_work_increase / days_in_trend * 7) if days_in_trend > 0 else 0

    total_scope = burnup_df['Escopo Total'].iloc[-1]
    remaining_work = total_scope - total_completed
    forecast_date = None

    if trend_weekly_velocity > 0 and remaining_work > 0:
        days_to_complete = (remaining_work / trend_weekly_velocity) * 7
        forecast_date = end_date + pd.Timedelta(days=days_to_complete)

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

def calculate_time_in_status(issue, all_statuses, completion_date):
    time_in_status = {status: 0.0 for status in all_statuses}
    status_changes = []
    if hasattr(issue.changelog, 'histories'):
        for history in issue.changelog.histories:
            for item in history.items:
                if item.field.lower() == 'status':
                    change = {
                        'timestamp': pd.to_datetime(history.created).tz_localize(None),
                        'from': item.fromString,
                        'to': item.toString
                    }
                    status_changes.append(change)
    created_date = pd.to_datetime(issue.fields.created).tz_localize(None)
    if not status_changes:
        current_status = issue.fields.status.name
        if current_status in time_in_status:
            end_time = completion_date if completion_date else pd.Timestamp.now(tz=None)
            duration_seconds = (end_time - created_date).total_seconds()
            if duration_seconds > 0:
                time_in_status[current_status] = duration_seconds / 86400
        return time_in_status
    status_changes.sort(key=lambda x: x['timestamp'])
    first_change = status_changes[0]
    initial_status = first_change['from']
    duration = (first_change['timestamp'] - created_date).total_seconds()
    if duration > 0 and initial_status in time_in_status:
        time_in_status[initial_status] += duration / 86400
    for i in range(len(status_changes) - 1):
        current_change = status_changes[i]
        next_change = status_changes[i+1]
        status = current_change['to']
        duration = (next_change['timestamp'] - current_change['timestamp']).total_seconds()
        if duration > 0 and status in time_in_status:
            time_in_status[status] += duration / 86400
    last_change = status_changes[-1]
    last_status = last_change['to']
    if last_status in time_in_status:
        end_time = completion_date if completion_date else pd.Timestamp.now(tz=None)
        last_status_duration = (end_time - last_change['timestamp']).total_seconds()
        if last_status_duration > 0:
            time_in_status[last_status] += last_status_duration / 86400
    return time_in_status

def calculate_flow_efficiency(issue, project_config):
    """Calcula a eficiência do fluxo, garantindo a conversão de tipos de data."""
    completion_date_obj = find_completion_date(issue, project_config)
    if not completion_date_obj:
        return None

    completion_datetime = pd.to_datetime(completion_date_obj)
    cycle_time_days = calculate_cycle_time(issue, completion_datetime, project_config)

    if not cycle_time_days or cycle_time_days <= 0:
        return None

    time_spent_seconds = issue.fields.timespent or 0
    touch_time_days = (time_spent_seconds / 3600) / 8

    if touch_time_days > cycle_time_days:
        return 100.0
        
    return (touch_time_days / cycle_time_days) * 100

def calculate_aggregated_metric(df, dimension, measure, agg):
    if not dimension or dimension not in df.columns:
        return pd.DataFrame({'Dimensão': [], 'Medida': []})

    if measure and measure.startswith('Tempo em: '):
        if measure not in df.columns:
            return pd.DataFrame({'Dimensão': [], 'Medida': []})
        agg_df = df.groupby(dimension)[measure].mean().reset_index(name='Medida')

    elif measure == 'Contagem de Issues':
        agg_df = df.groupby(dimension).size().reset_index(name='Medida')

    elif agg == 'Contagem Distinta':
        if measure not in df.columns: return pd.DataFrame({'Dimensão': [], 'Medida': []})
        agg_df = df.groupby(dimension)[measure].nunique().reset_index(name='Medida')

    else:
        if measure not in df.columns: return pd.DataFrame({'Dimensão': [], 'Medida': []})
        numeric_series = pd.to_numeric(df[measure], errors='coerce')
        grouped_data = numeric_series.groupby(df[dimension])
        if agg == 'Soma': agg_df = grouped_data.sum().reset_index(name='Medida')
        elif agg == 'Média': agg_df = grouped_data.mean().reset_index(name='Medida')
        else: agg_df = grouped_data.count().reset_index(name='Medida')

    return agg_df.rename(columns={dimension: 'Dimensão'})

def get_aging_wip(issues):
    global_configs = st.session_state.get('global_configs', {})
    initial_states = global_configs.get('initial_states', DEFAULT_INITIAL_STATES)
    done_states = global_configs.get('done_states', DEFAULT_DONE_STATES)

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
        last_status_change_date = pd.to_datetime(issue.fields.created).date()
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

def calculate_velocity(sprint_issues, estimation_config):
    if not sprint_issues or not estimation_config.get('id'): return 0
    status_mapping = st.session_state.get('global_configs', {}).get('status_mapping', {})
    done_states = status_mapping.get('done', DEFAULT_DONE_STATES)
    completed_points = 0
    for issue in sprint_issues:
        if issue.fields.status.name.lower() in done_states:
            completed_points += get_issue_estimation(issue, estimation_config)
    return completed_points

def calculate_sprint_defects(sprint_issues):
    """Calcula a quantidade de defeitos (bugs) concluídos na sprint."""
    if not sprint_issues: return 0

    global_configs = st.session_state.get('global_configs', {})
    done_states = global_configs.get('done_states', DEFAULT_DONE_STATES)

    defect_count = 0
    for issue in sprint_issues:
        issue_type_lower = issue.fields.issuetype.name.lower()
        if 'bug' in issue_type_lower or 'defeito' in issue_type_lower:
            if issue.fields.status.name.lower() in [s.lower() for s in done_states]:
                defect_count += 1
    return defect_count

def calculate_sprint_goal_success_rate(sprints, threshold, estimation_config, project_config):
    """Calcula a taxa de sucesso de sprints com base num limiar de previsibilidade."""
    from jira_connector import get_sprint_issues
    if not sprints:
        return 0.0

    successful_sprints = 0
    for sprint in sprints:
        sprint_issues = get_sprint_issues(st.session_state.jira_client, sprint.id)
        predictability = calculate_predictability(sprint_issues, estimation_config, project_config)
        if predictability >= threshold:
            successful_sprints += 1

    return (successful_sprints / len(sprints)) * 100 if sprints else 0.0

def prepare_burndown_data_by_count(client, sprint_obj, project_config):
    """Prepara os dados para o gráfico de Burndown por CONTAGEM DE ISSUES."""
    from jira_connector import get_sprint_issues
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
    from jira_connector import get_sprint_issues
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

def calculate_executive_summary_metrics(issues, project_config):
    """Calcula todas as métricas, agora com a lógica de fuso horário corrigida."""
    if not issues:
        return {'completion_pct': 0, 'deliveries_month': 0, 'avg_deadline_diff': 0, 'schedule_adherence': 0}

    total_issues = len(issues)
    completed_issues_list = [i for i in issues if find_completion_date(i, project_config) is not None]

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
    schedule_adherence = calculate_schedule_adherence(issues, project_config)

    return {
        'completion_pct': completion_pct, 'deliveries_month': deliveries_month,
        'avg_deadline_diff': avg_deadline_diff, 'schedule_adherence': schedule_adherence,
        'total_issues': total_issues, 'completed_issues': len(completed_issues_list)
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

    trend = df.groupby(pd.Grouper(key='completion_date', freq='W-MON')).size().reset_index(name='Entregas')
    trend['Semana'] = trend['completion_date'].dt.strftime('Semana %U')

    return trend[['Semana', 'Entregas']]

def calculate_risk_level(probability, impact):
    level_map = {'Baixa': 1, 'Média': 2, 'Alta': 3}
    prob_score = level_map.get(probability, 1)
    impact_score = level_map.get(impact, 1)

    risk_score = prob_score * impact_score

    if risk_score <= 2: return "Baixo", "#28a745"
    elif risk_score <= 4: return "Moderado", "#ffc107"
    elif risk_score <= 6: return "Alto", "#fd7e14"
    else: return "Crítico", "#dc3545"

def calculate_time_to_first_response(issue, first_response_field_id):
    """Calcula o tempo em horas entre a criação e o primeiro atendimento."""
    if not hasattr(issue.fields, first_response_field_id) or not getattr(issue.fields, first_response_field_id):
        return None

    creation_date = pd.to_datetime(issue.fields.created)
    response_date = pd.to_datetime(getattr(issue.fields, first_response_field_id))

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
    Calcula a soma do estimado vs. realizado para uma lista de issues concluídas,
    convertendo corretamente os valores de segundos para horas.
    """
    total_estimated_hours = 0
    total_actual_hours = 0

    if not completed_issues:
        return {'total_estimated': 0, 'total_actual': 0, 'accuracy_ratio': 100}

    is_time_based_estimation = estimation_config.get('source') == 'standard_time'

    for issue in completed_issues:
        estimated_value = get_issue_estimation(issue, estimation_config) or 0
        time_spent_seconds = issue.fields.timespent if hasattr(issue.fields, 'timespent') and issue.fields.timespent is not None else 0

        if estimated_value > 0:
            actual_hours = time_spent_seconds / 3600
            total_actual_hours += actual_hours
            if is_time_based_estimation:
                estimated_hours = estimated_value / 3600
                total_estimated_hours += estimated_hours
            else:
                total_estimated_hours += estimated_value
    
    accuracy_ratio = (total_actual_hours / total_estimated_hours) * 100 if total_estimated_hours > 0 else 100

    return {
        'total_estimated': total_estimated_hours,
        'total_actual': total_actual_hours,
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
        return 0.0

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

def get_applicable_sla_policy(issue, policies):
    """Encontra a primeira política de SLA que se aplica a uma issue."""
    issue_type_name = issue.fields.issuetype.name.lower()
    priority_name = issue.fields.priority.name.lower() if issue.fields.priority else ""

    for policy in policies:
        policy_issue_types = [t.lower() for t in policy['issue_types']]
        policy_priorities = [p.lower() for p in policy['priorities']]

        types_match = not policy_issue_types or issue_type_name in policy_issue_types
        priorities_match = not policy_priorities or priority_name in policy_priorities

        if types_match and priorities_match:
            return policy
    return None

def calculate_business_hours(start_time, end_time):
    """Calcula as horas úteis entre duas datas (simplificado, 8h/dia, seg-sex)."""
    if not start_time or not end_time:
        return 0

    if isinstance(start_time, str): start_time = pd.to_datetime(start_time)
    if isinstance(end_time, str): end_time = pd.to_datetime(end_time)

    start_time = start_time.tz_localize(None)
    end_time = end_time.tz_localize(None)

    business_days = np.busday_count(start_time.date(), end_time.date())

    return business_days * 8

def calculate_sla_metrics_for_issues(issues, global_configs):
    """Calcula as métricas de SLA para uma lista de issues."""
    policies = global_configs.get('sla_policies', [])
    if not policies:
        return {}

    total_sla_issues = 0
    violated_resolution_sla = 0
    met_resolution_sla = 0
    first_response_times = []

    for issue in issues:
        policy = get_applicable_sla_policy(issue, policies)
        if not policy:
            continue

        total_sla_issues += 1

        start_time, stop_time, first_response_time = None, None, None

        start_statuses = [s.lower() for s in policy['start_statuses']]
        stop_statuses = [s.lower() for s in policy['stop_statuses']]

        for history in issue.changelog.histories:
            history_time = pd.to_datetime(history.created).tz_localize(None)
            for item in history.items:
                if item.field == 'status':
                    status_name = item.toString.lower()
                    if status_name in start_statuses and not start_time:
                        start_time = history_time
                    if status_name in stop_statuses:
                        stop_time = history_time

            if not first_response_time and hasattr(issue.fields, 'comment') and issue.fields.comment.comments:
                for comment in issue.fields.comment.comments:
                    comment_author = comment.author.displayName
                    issue_creator = issue.fields.creator.displayName
                    if comment_author != issue_creator:
                        first_response_time = pd.to_datetime(comment.created).tz_localize(None)
                        break

        if start_time and stop_time:
            resolution_hours = calculate_business_hours(start_time, stop_time)
            if resolution_hours > policy['resolution_hours']:
                violated_resolution_sla += 1
            else:
                met_resolution_sla += 1

        if start_time and first_response_time and first_response_time > start_time:
            response_hours = calculate_business_hours(start_time, first_response_time)
            first_response_times.append(response_hours)

    return {
        'sla_resolution_met_pct': (met_resolution_sla / total_sla_issues * 100) if total_sla_issues > 0 else 0,
        'sla_resolution_violated_pct': (violated_resolution_sla / total_sla_issues * 100) if total_sla_issues > 0 else 0,
        'avg_first_response_hours': sum(first_response_times) / len(first_response_times) if first_response_times else 0,
    }

def apply_status_category_mapping(df, project_config):
    """
    Aplica o mapeamento de categoria de status a um DataFrame, de forma robusta e insensível a maiúsculas/minúsculas e espaços.
    """
    if 'Status' not in df.columns:
        return df

    status_mapping = project_config.get('status_mapping', {})
    
    # Inverte o mapeamento para {status: categoria}, limpando e normalizando os dados
    category_map = {}
    for category, statuses in status_mapping.items():
        if isinstance(statuses, list):
            for status in statuses:
                # Normaliza o status (minúsculas e sem espaços extra)
                normalized_status = status.strip().lower()
                category_map[normalized_status] = category

    # Cria a nova coluna aplicando o mapa aos status também normalizados
    # Garante que a coluna 'Status' seja do tipo string antes de aplicar as operações
    df['Categoria de Status'] = df['Status'].astype(str).str.strip().str.lower().map(category_map)
    
    # Preenche com um valor padrão os status que não foram mapeados
    df['Categoria de Status'].fillna('Não Categorizado', inplace=True)
    
    return df
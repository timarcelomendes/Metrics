# metrics_calculator.py (VERSÃO FINAL COM CORREÇÃO DE CYCLE TIME)

import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from jira_connector import get_sprint_issues
from utils import *
from config import STATUS_MAPPING_FILE, DEFAULT_INITIAL_STATES, DEFAULT_DONE_STATES
from utils import load_config 
from datetime import datetime, timedelta


# --- Listas Configuráveis ---
INITIAL_STATES = ['to do', 'a fazer', 'backlog', 'aberto', 'novo']
DONE_STATES = ['done', 'concluído', 'pronto', 'finalizado', 'resolvido']

# --- Funções Auxiliares de Data ---
def find_completion_date(issue):
    """Função auxiliar para encontrar a data de conclusão de uma issue."""
    status_mapping = st.session_state.get('global_configs', {}).get('status_mapping', {})
    done_states = status_mapping.get('done', DEFAULT_DONE_STATES)
    
    if hasattr(issue.fields, 'resolutiondate') and issue.fields.resolutiondate:
        return pd.to_datetime(issue.fields.resolutiondate).tz_localize(None).normalize()
    if issue.fields.status.name.lower() in done_states:
        for history in sorted(issue.changelog.histories, key=lambda h: h.created, reverse=True):
            for item in history.items:
                if item.field == 'status' and item.toString.lower() in done_states:
                    return pd.to_datetime(history.created).tz_localize(None).normalize()
        return pd.to_datetime(issue.fields.updated).tz_localize(None).normalize()
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

def calculate_lead_time(issue):
    created_date = pd.to_datetime(issue.fields.created).tz_localize(None).normalize()
    completion_date = find_completion_date(issue)
    if completion_date and created_date and completion_date >= created_date:
        return (completion_date - created_date).days
    return None

def calculate_cycle_time(issue):
    start_date = find_start_date(issue)
    completion_date = find_completion_date(issue)
    if start_date and completion_date and completion_date >= start_date:
        return (completion_date - start_date).days
    return None

def calculate_throughput(issues):
    return len([i for i in issues if find_completion_date(i) is not None])

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

def calculate_predictability(sprint_issues, estimation_field_id):
    if not sprint_issues or not estimation_field_id: return 0.0
    story_points_field = estimation_field_id; total_points_planned = 0; total_points_completed = 0
    for issue in sprint_issues:
        points = getattr(issue.fields, story_points_field, 0) or 0
        total_points_planned += points
        if find_completion_date(issue) is not None:
            completed_points_value = getattr(issue.fields, story_points_field, 0) or 0
            total_points_completed += completed_points_value
    if total_points_planned == 0: return 100.0
    return (total_points_completed / total_points_planned) * 100

def generate_sprint_health_summary(issues, predictability):
    insights = []
    if predictability >= 95: insights.append(f"✅ **Previsibilidade Excelente ({predictability:.0f}%):** O time demonstrou um domínio notável do seu planejamento.")
    elif 80 <= predictability < 95: insights.append(f"✅ **Previsibilidade Saudável ({predictability:.0f}%):** O time é bastante confiável em suas previsões.")
    elif 60 <= predictability < 80: insights.append(f"⚠️ **Previsibilidade em Desenvolvimento ({predictability:.0f}%):** Há espaço para melhorar a precisão do planejamento ou a gestão de interrupções.")
    else: insights.append(f"🚨 **Alerta de Previsibilidade ({predictability:.0f}%):** Forte indicação de que o planejamento não está conectado à entrega.")
    completed_issues = [i for i in issues if find_completion_date(i) is not None]
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

def prepare_burndown_data(client, sprint_obj, estimation_config):
    """
    Prepara os dados para o gráfico de Burndown de uma sprint.
    Agora recebe o objeto sprint completo e a configuração de estimativa.
    """
    estimation_field_id = estimation_config.get('id')
    if not estimation_field_id:
        st.warning("Burndown não pode ser calculado sem um campo de estimativa configurado para o projeto.")
        return pd.DataFrame()

    try:
        # Extrai as datas do objeto sprint
        start_date = pd.to_datetime(sprint_obj.startDate).tz_localize(None).normalize()
        end_date = pd.to_datetime(sprint_obj.endDate).tz_localize(None).normalize()
        sprint_id = sprint_obj.id
    except AttributeError:
        # Se o objeto sprint não tiver as datas, retorna um dataframe vazio
        return pd.DataFrame()

    issues = get_sprint_issues(client, sprint_id)
    if not issues:
        return pd.DataFrame()
        
    total_points_planned = sum(get_issue_estimation(i, estimation_config) for i in issues)
    
    date_range = pd.date_range(start=start_date, end=end_date, freq='D')
    points_completed_per_day = {day: 0 for day in date_range}
    
    for issue in issues:
        completion_date = find_completion_date(issue)
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
    """Prepara o CFD, agora ignorando issues canceladas."""
    
    # Filtra as issues no início
    valid_issues = get_filtered_issues(issues)
    """Prepara os dados para o Diagrama de Fluxo Cumulativo (CFD) para um dado período."""
    transitions = []
    
    # Garante que as datas de entrada sejam do tipo date, não datetime
    start_date = start_date if isinstance(start_date, pd.Timestamp) else datetime.combine(start_date, datetime.min.time())
    end_date = end_date if isinstance(end_date, pd.Timestamp) else datetime.combine(end_date, datetime.max.time())
    
    start_date = pd.to_datetime(start_date).tz_localize(None)
    end_date = pd.to_datetime(end_date).tz_localize(None)

    for issue in issues:
        # Adiciona o estado inicial na data de criação
        created_date = pd.to_datetime(issue.fields.created).tz_localize(None)
        if created_date <= end_date:
             transitions.append({'date': created_date, 'from': None, 'to': 'Criado'})
        
        # Percorre o histórico de mudanças de status
        for history in issue.changelog.histories:
            history_date = pd.to_datetime(history.created).tz_localize(None)
            if start_date <= history_date <= end_date:
                for item in history.items:
                    if item.field == 'status':
                        transitions.append({'date': history_date, 'from': item.fromString, 'to': item.toString})

    if not transitions:
        return pd.DataFrame(), pd.DataFrame()

    df = pd.DataFrame(transitions)
    df['date'] = df['date'].dt.normalize()

    # Conta as entradas e saídas de cada status por dia
    cfd_in = df.groupby(['date', 'to']).size().unstack(fill_value=0)
    cfd_out = df.groupby(['date', 'from']).size().unstack(fill_value=0)
    
    # Combina e calcula a mudança líquida
    cfd_net = cfd_in.subtract(cfd_out, fill_value=0)
    
    # Garante que todas as colunas de status existam
    all_statuses = sorted(list(set(df['from'].dropna().unique()) | set(df['to'].dropna().unique())))
    for status in all_statuses:
        if status not in cfd_net:
            cfd_net[status] = 0
            
    # Cria um índice de datas completo e preenche os dias sem mudanças
    full_date_range = pd.date_range(start=df['date'].min(), end=df['date'].max(), freq='D')
    cfd_resampled = cfd_net.reindex(full_date_range).fillna(0)
    
    # Calcula a soma cumulativa para criar as bandas do CFD
    cfd_cumulative = cfd_resampled.cumsum()
    
    # Lógica para WIP (Trabalho em Progresso)
    initial, done = load_config(STATUS_MAPPING_FILE, {}).get('initial', DEFAULT_INITIAL_STATES), load_config(STATUS_MAPPING_FILE, {}).get('done', DEFAULT_DONE_STATES)
    wip_statuses = [s for s in cfd_cumulative.columns if s.lower() not in initial and s.lower() not in done]
    wip_df = pd.DataFrame({'Data': cfd_cumulative.index, 'WIP': cfd_cumulative[wip_statuses].sum(axis=1)})

    return cfd_cumulative, wip_df

def prepare_project_burnup_data(issues, unit, estimation_config):
    """Prepara o burnup, agora ignorando issues canceladas."""
    
    # Filtra as issues no início
    valid_issues = get_filtered_issues(issues)

    # Se a unidade for 'points', mas não houver campo configurado, retorna vazio.
    if unit == 'points' and (not estimation_config or not estimation_config.get('id')):
        st.warning("Para análise por pontos, por favor, configure um 'Campo de Estimativa' para este projeto nas Configurações.")
        return pd.DataFrame()
    
    data = []
    for issue in issues:
        created_date = pd.to_datetime(issue.fields.created).tz_localize(None).normalize()
        completion_date = find_completion_date(issue)
        # Usa a função get_issue_estimation para obter o valor correto
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
    Calcula a linha de tendência, a previsão de entrega e as velocidades (tendência e média).
    """
    if burnup_df.empty or 'Trabalho Concluído' not in burnup_df.columns:
        return None, None, 0, 0

    # --- NOVO CÁLCULO CORRETO PARA VELOCIDADE MÉDIA ---
    total_completed = burnup_df['Trabalho Concluído'].iloc[-1]
    
    # Encontra a primeira data com trabalho para calcular a duração real
    first_work_day = burnup_df[burnup_df['Trabalho Concluído'] > 0].index.min()
    last_day = burnup_df.index.max()
    
    avg_weekly_velocity = 0
    if pd.notna(first_work_day):
        duration_days = (last_day - first_work_day).days
        if duration_days > 0:
            avg_daily_velocity = total_completed / duration_days
            avg_weekly_velocity = avg_daily_velocity * 7
        elif total_completed > 0: # Se tudo foi feito em menos de um dia
            avg_weekly_velocity = total_completed * 7

    # --- Cálculo da Velocidade de Tendência (últimas N semanas) - sem alterações ---
    end_date = burnup_df.index.max()
    start_date_trend = end_date - pd.Timedelta(weeks=trend_weeks)
    trend_data = burnup_df[start_date_trend:]
    
    if len(trend_data) < 2:
        return None, None, 0, avg_weekly_velocity

    total_work_increase = trend_data['Trabalho Concluído'].iloc[-1] - trend_data['Trabalho Concluído'].iloc[0]
    days_in_trend = (trend_data.index.max() - trend_data.index.min()).days
    
    trend_weekly_velocity = (total_work_increase / days_in_trend * 7) if days_in_trend > 0 else 0

    # --- Cálculo do Forecast (sem alterações) ---
    total_scope = burnup_df['Escopo Total'].iloc[-1]
    remaining_work = total_scope - total_completed
    forecast_date = None
    df_trend = None
    
    if trend_weekly_velocity > 0 and remaining_work > 0:
        days_to_complete = remaining_work / (trend_weekly_velocity / 7)
        forecast_date = end_date + pd.Timedelta(days=days_to_complete)
        
        x_trend = np.array([(d - trend_data.index.min()).days for d in trend_data.index]).reshape(-1, 1)
        y_trend = trend_data['Trabalho Concluído'].values
        model = LinearRegression().fit(x_trend, y_trend)
        
        future_dates = pd.to_datetime(np.arange(trend_data.index.min(), forecast_date, dtype='datetime64[D]'))
        x_future = np.array([(d - trend_data.index.min()).days for d in future_dates]).reshape(-1, 1)
        
        predicted_completion = model.predict(x_future)
        df_trend = pd.DataFrame(predicted_completion, index=future_dates, columns=['Tendência'])

    return df_trend, forecast_date, trend_weekly_velocity, avg_weekly_velocity

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
    """Retorna um DataFrame com os itens em andamento e há quantos dias estão nesse estado."""
    # 1. Busca TODAS as configurações de status
    global_configs = st.session_state.get('global_configs', {})
    status_mapping = global_configs.get('status_mapping', {})
    initial_states = status_mapping.get('initial', DEFAULT_INITIAL_STATES)
    done_states = status_mapping.get('done', DEFAULT_DONE_STATES)
    ignored_states = status_mapping.get('ignored', []) # <-- Busca a lista de ignorados
    
    wip_issues = []
    
    for issue in issues:
        current_status = issue.fields.status.name.lower()
        
        # --- LÓGICA CORRIGIDA ---
        # Um item só é WIP se não for inicial, não for final E NÃO for ignorado.
        if current_status not in initial_states and current_status not in done_states and current_status not in ignored_states:
            
            # Encontra quando a issue entrou no status atual para calcular a idade
            last_status_change_date = pd.to_datetime(issue.fields.created).tz_localize(None)
            for history in sorted(issue.changelog.histories, key=lambda h: h.created):
                for item in history.items:
                    if item.field == 'status':
                        last_status_change_date = pd.to_datetime(history.created).tz_localize(None)

            age = (datetime.now(last_status_change_date.tz) - last_status_change_date).days
            wip_issues.append({
                'Issue': issue.key, 
                'Status Atual': issue.fields.status.name, 
                'Dias no Status': age
            })
            
    return pd.DataFrame(wip_issues).sort_values(by='Dias no Status', ascending=False)

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
    done_statuses = load_config(STATUS_MAPPING_FILE, {}).get('done', DEFAULT_DONE_STATES)
    defect_count = 0
    for issue in sprint_issues:
        issue_type_lower = issue.fields.issuetype.name.lower()
        if 'bug' in issue_type_lower or 'defeito' in issue_type_lower:
            if issue.fields.status.name.lower() in done_statuses:
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

def prepare_burndown_data_by_count(client, sprint_obj):
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
        completion_date = find_completion_date(issue)
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

def prepare_burndown_data_by_estimation(client, sprint_obj, estimation_config):
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
        completion_date = find_completion_date(issue)
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

def calculate_executive_summary_metrics(project_issues):
    """
    Calcula as métricas quantitativas para o resumo executivo, agora retornando
    também a contagem de issues totais e concluídas.
    """
    if not project_issues:
        return {
            'completion_pct': 0, 'deliveries_month': 0, 'avg_deadline_diff': 0,
            'total_issues': 0, 'completed_issues': 0
        }

    total_issues = len(project_issues)
    completed_issues_list = [i for i in project_issues if find_completion_date(i) is not None]
    
    # 1. % Concluído
    completion_pct = (len(completed_issues_list) / total_issues) * 100 if total_issues > 0 else 0

    # 2. Entregas no Mês Atual
    current_month = datetime.now().month
    current_year = datetime.now().year
    deliveries_month = len([
        i for i in completed_issues_list 
        if (cd := find_completion_date(i)) and cd.month == current_month and cd.year == current_year
    ])

    # 3. Prazo Médio
    deadline_diffs = []
    for i in completed_issues_list:
        if hasattr(i.fields, 'duedate') and i.fields.duedate:
            due_date = pd.to_datetime(i.fields.duedate).normalize()
            completion_date = find_completion_date(i)
            if completion_date:
                deadline_diffs.append((completion_date - due_date).days)
    
    avg_deadline_diff = np.mean(deadline_diffs) if deadline_diffs else 0
    
    # --- CORREÇÃO AQUI: Retorna as contagens ---
    return {
        'completion_pct': completion_pct,
        'deliveries_month': deliveries_month,
        'avg_deadline_diff': avg_deadline_diff,
        'total_issues': total_issues,
        'completed_issues': len(completed_issues_list)
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
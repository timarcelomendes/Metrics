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
    if issue.fields.resolutiondate:
        return pd.to_datetime(issue.fields.resolutiondate).tz_localize(None).normalize()
    if issue.fields.status.name.lower() in DONE_STATES:
        for history in sorted(issue.changelog.histories, key=lambda h: h.created, reverse=True):
            for item in history.items:
                if item.field == 'status' and item.toString.lower() in DONE_STATES:
                    return pd.to_datetime(history.created).tz_localize(None).normalize()
        return pd.to_datetime(issue.fields.updated).tz_localize(None).normalize()
    return None

def find_start_date(issue):
    """
    Função auxiliar robusta para encontrar a data de início do ciclo de trabalho.
    Define o início como a primeira transição para um estado que não seja inicial.
    """
    try:
        # Itera sobre o histórico em ordem cronológica
        for history in sorted(issue.changelog.histories, key=lambda h: h.created):
            for item in history.items:
                if item.field == 'status':
                    # A primeira vez que a issue é movida PARA um status NÃO inicial, marca o início do ciclo.
                    if item.toString.lower() not in INITIAL_STATES:
                        return pd.to_datetime(history.created).tz_localize(None).normalize()
    except Exception as e:
        print(f"Erro ao calcular Start Date para {issue.key}: {e}")
    
    # Fallback: se não encontrar transições (ex: criada e concluída no mesmo status ativo), retorna a data de criação
    created_date = pd.to_datetime(issue.fields.created).tz_localize(None).normalize()
    if issue.fields.status.name.lower() not in INITIAL_STATES:
        return created_date
        
    return None

# --- Funções de Cálculo de Métricas ---
def calculate_lead_time(issue):
    """Calcula o Lead Time (Criação -> Conclusão)."""
    created_date = pd.to_datetime(issue.fields.created).tz_localize(None).normalize()
    completion_date = find_completion_date(issue)
    if completion_date and created_date:
        if completion_date < created_date: return None
        return (completion_date - created_date).days
    return None

def calculate_cycle_time(issue):
    """Calcula o Cycle Time (Início do Trabalho -> Conclusão)."""
    start_date = find_start_date(issue)
    completion_date = find_completion_date(issue)
    if start_date and completion_date:
        if start_date > completion_date: return None
        return (completion_date - start_date).days
    return None

# --- O resto do arquivo permanece o mesmo ---
def calculate_throughput(issues):
    return len([i for i in issues if find_completion_date(i) is not None])

def calculate_velocity(issues):
    total_points = 0; story_points_field = 'customfield_10016'
    for issue in issues:
        if find_completion_date(issue) is not None:
            points = getattr(issue.fields, story_points_field, None)
            if points is not None: total_points += float(points)
    return total_points

def calculate_predictability(issues):
    story_points_field = 'customfield_10016'; total_points_planned = 0; total_points_completed = 0
    for issue in issues:
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

def prepare_burndown_data(jira_client, sprint_id):
    sprint = jira_client.sprint(sprint_id)
    start_date = pd.to_datetime(sprint.startDate).tz_localize(None).normalize(); end_date = pd.to_datetime(sprint.endDate).tz_localize(None).normalize()
    issues = get_sprint_issues(jira_client, sprint_id); story_points_field = 'customfield_10016'
    total_points_planned = sum(getattr(i.fields, story_points_field, 0) or 0 for i in issues)
    date_range = pd.date_range(start=start_date, end=end_date); burndown_data = {d: total_points_planned for d in date_range}
    points_completed_per_day = {}
    for issue in issues:
        completion_date = find_completion_date(issue)
        if completion_date:
            points = getattr(issue.fields, story_points_field, 0) or 0
            points_completed_per_day.setdefault(completion_date, 0); points_completed_per_day[completion_date] += points
    remaining_points = total_points_planned
    for day in sorted(burndown_data.keys()):
        burndown_data[day] = remaining_points
        if day in points_completed_per_day: remaining_points -= points_completed_per_day[day]
    ideal_line = np.linspace(total_points_planned, 0, len(date_range)) if date_range.size > 0 else []
    return pd.DataFrame({'Data': list(burndown_data.keys()), 'Pontos Restantes (Real)': list(burndown_data.values()), 'Linha Ideal': ideal_line}).set_index('Data')

def prepare_cfd_data(issues, start_date, end_date):
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

def prepare_project_burnup_data(issues, unit='points'):
    story_points_field = 'customfield_10016'; burnup_data = []
    if not issues: return pd.DataFrame()
    for issue in issues:
        created_date = pd.to_datetime(issue.fields.created).tz_localize(None).normalize(); completion_date = find_completion_date(issue)
        value = (getattr(issue.fields, story_points_field, 0) or 0) if unit == 'points' else 1
        burnup_data.append({'created': created_date, 'resolved': completion_date, 'value': value})
    df = pd.DataFrame(burnup_data)
    if df['created'].dropna().empty: return pd.DataFrame()
    start_date = df['created'].min(); end_date = pd.Timestamp.now(tz=None).normalize(); date_range = pd.date_range(start=start_date, end=end_date)
    scope_over_time = [df[df['created'] <= day]['value'].sum() for day in date_range]
    completed_over_time = [df[(df['resolved'].notna()) & (df['resolved'] <= day)]['value'].sum() for day in date_range]
    return pd.DataFrame({'Data': date_range, 'Escopo Total': scope_over_time, 'Trabalho Concluído': completed_over_time}).set_index('Data')

def calculate_trend_and_forecast(burnup_df, trend_weeks):
    """
    Calcula a linha de tendência, a previsão de entrega e retorna DUAS velocidades:
    a de tendência (recente) e a média (geral).
    """
    # 1. Cálculo da Velocidade Média (histórico completo)
    if not burnup_df.empty and 'Trabalho Concluído' in burnup_df.columns:
        daily_throughput = burnup_df['Trabalho Concluído'].diff().fillna(0)
        avg_daily_velocity = daily_throughput[daily_throughput > 0].mean()
        avg_weekly_velocity = (avg_daily_velocity * 7) if pd.notna(avg_daily_velocity) else 0
    else:
        avg_weekly_velocity = 0

    # 2. Cálculo da Velocidade de Tendência (últimas N semanas)
    end_date = burnup_df.index.max()
    start_date_trend = end_date - pd.Timedelta(weeks=trend_weeks)
    trend_data = burnup_df[start_date_trend:]
    
    if len(trend_data) < 2:
        return None, None, 0, avg_weekly_velocity

    total_work_increase = trend_data['Trabalho Concluído'].iloc[-1] - trend_data['Trabalho Concluído'].iloc[0]
    days_in_trend = (trend_data.index.max() - trend_data.index.min()).days
    
    trend_weekly_velocity = (total_work_increase / days_in_trend * 7) if days_in_trend > 0 else 0

    # 3. Cálculo do Forecast
    total_scope = burnup_df['Escopo Total'].iloc[-1]
    current_completed = burnup_df['Trabalho Concluído'].iloc[-1]
    remaining_work = total_scope - current_completed
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
    # Carrega as configurações de status
    status_config = load_config(STATUS_MAPPING_FILE, {})
    initial_states = status_config.get('initial', DEFAULT_INITIAL_STATES)
    done_states = status_config.get('done', DEFAULT_DONE_STATES)
    
    wip_issues = []
    
    for issue in issues:
        current_status = issue.fields.status.name.lower()
        if current_status not in initial_states and current_status not in done_states:
            # Lógica para calcular a idade do WIP
            last_status_change_date = pd.to_datetime(issue.fields.created).tz_localize(None)
            for history in sorted(issue.changelog.histories, key=lambda h: h.created):
                for item in history.items:
                    if item.field == 'status':
                        last_status_change_date = pd.to_datetime(history.created).tz_localize(None)

            age = (datetime.now() - last_status_change_date).days
            wip_issues.append({'Issue': issue.key, 'Status Atual': issue.fields.status.name, 'Dias no Status': age})
            
    return pd.DataFrame(wip_issues).sort_values(by='Dias no Status', ascending=False)

def calculate_velocity(sprint_issues):
    """Calcula a velocidade da sprint (soma de story points de itens concluídos)."""
    if not sprint_issues: return 0
    # Assume que a configuração global para o ID do Story Point está na sessão
    story_points_field = st.session_state.get('global_configs', {}).get('story_points_field_id', 'customfield_10016')
    done_statuses = load_config(STATUS_MAPPING_FILE, {}).get('done', DEFAULT_DONE_STATES)
    
    completed_points = 0
    for issue in sprint_issues:
        if issue.fields.status.name.lower() in done_statuses:
            points = getattr(issue.fields, story_points_field, 0)
            if points:
                completed_points += points
    return completed_points

def calculate_predictability(sprint_issues):
    """Calcula a previsibilidade (pontos concluídos / pontos comprometidos)."""
    if not sprint_issues: return 0.0
    story_points_field = st.session_state.get('global_configs', {}).get('story_points_field_id', 'customfield_10016')
    done_statuses = load_config(STATUS_MAPPING_FILE, {}).get('done', DEFAULT_DONE_STATES)

    total_committed_points = 0
    total_completed_points = 0
    
    for issue in sprint_issues:
        points = getattr(issue.fields, story_points_field, 0) or 0
        total_committed_points += points
        if issue.fields.status.name.lower() in done_statuses:
            total_completed_points += points
            
    return (total_completed_points / total_committed_points) * 100 if total_committed_points > 0 else 0.0

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

def calculate_sprint_goal_success_rate(sprints, threshold):
    """Calcula a taxa de sucesso de sprints com base num limiar de previsibilidade."""
    if not sprints:
        return 0.0
    
    successful_sprints = 0
    for sprint in sprints:
        # Reutiliza a função de previsibilidade que já temos
        predictability = calculate_predictability(get_sprint_issues(st.session_state.jira_client, sprint.id))
        if predictability >= threshold:
            successful_sprints += 1
            
    return (successful_sprints / len(sprints)) * 100 if sprints else 0.0
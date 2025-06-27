# metrics_calculator.py (VERSÃO FINAL COM CORREÇÃO DE CYCLE TIME)

import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from jira_connector import get_sprint_issues

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

def prepare_cfd_data(issues):
    cfd_data = []; status_categories = ['To Do', 'In Progress', 'In Review', 'Done']
    if not issues: return pd.DataFrame(), pd.DataFrame()
    for issue in issues:
        created_date = pd.to_datetime(issue.fields.created).tz_localize(None).normalize(); transitions = {created_date: 'To Do'}
        for history in sorted(issue.changelog.histories, key=lambda h: h.created):
            for item in history.items:
                if item.field == 'status': transitions[pd.to_datetime(history.created).tz_localize(None).normalize()] = item.toString
        sorted_transitions = sorted(transitions.items()); last_date, last_status = sorted_transitions[-1]
        completion_date = find_completion_date(issue) or pd.Timestamp.now(tz=None).normalize()
        for day in pd.date_range(last_date, completion_date): cfd_data.append({'date': day.normalize(), 'key': issue.key, 'status': last_status})
        for i in range(len(sorted_transitions) - 1):
            start_d, status = sorted_transitions[i]; end_d, _ = sorted_transitions[i+1]
            for day in pd.date_range(start_d, end_d - pd.Timedelta(days=1)): cfd_data.append({'date': day.normalize(), 'key': issue.key, 'status': status})
    if not cfd_data: return pd.DataFrame(), pd.DataFrame()
    df = pd.DataFrame(cfd_data).drop_duplicates(['date', 'key'], keep='last')
    def map_status(status):
        s_lower = status.lower()
        if 'in progress' in s_lower or 'desenvolvimento' in s_lower: return 'In Progress'
        if 'review' in s_lower or 'revisão' in s_lower or 'qa' in s_lower: return 'In Review'
        if status.lower() in DONE_STATES: return 'Done'
        return 'To Do'
    df['category'] = df['status'].apply(map_status)
    cfd = df.groupby(['date', 'category'])['key'].count().unstack().fillna(0)
    if not cfd.empty:
        full_date_range = pd.date_range(start=cfd.index.min(), end=cfd.index.max()); cfd = cfd.reindex(full_date_range, fill_value=0).cumsum()
    for cat in status_categories:
        if cat not in cfd.columns: cfd[cat] = 0
    wip_statuses = ['In Progress', 'In Review']; wip_cols_exist = [col for col in wip_statuses if col in cfd.columns]
    df_wip = cfd[wip_cols_exist].sum(axis=1).reset_index() if wip_cols_exist else pd.DataFrame(columns=['index', '0'])
    df_wip.columns = ['Data', 'WIP']
    return cfd[status_categories], df_wip

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

def calculate_trend_and_forecast(df_burnup, trend_weeks=4):
    if df_burnup.empty or 'Trabalho Concluído' not in df_burnup.columns: return None, None, 0
    today = pd.Timestamp.now(tz=None).normalize(); start_trend_date = today - pd.Timedelta(weeks=trend_weeks)
    trend_data = df_burnup[df_burnup.index >= start_trend_date]['Trabalho Concluído'].dropna()
    if len(trend_data) < 2: return None, None, 0
    X = np.array([(d.toordinal() - trend_data.index.min().toordinal()) for d in trend_data.index]).reshape(-1, 1); y = trend_data.values
    model = LinearRegression(); model.fit(X, y)
    daily_velocity = model.coef_[0]
    if daily_velocity <= 0.001: return None, None, 0
    current_scope = df_burnup['Escopo Total'].iloc[-1]
    work_base_for_trend = trend_data.iloc[0]; date_base_for_trend = trend_data.index[0]
    remaining_work = current_scope - work_base_for_trend
    if remaining_work < 0: remaining_work = 0
    days_to_complete = remaining_work / daily_velocity
    forecast_date = date_base_for_trend + pd.to_timedelta(days_to_complete, unit='d')
    if forecast_date > date_base_for_trend:
        trend_dates = pd.date_range(start=date_base_for_trend, end=forecast_date)
        trend_X = np.array([(d.toordinal() - date_base_for_trend.toordinal()) for d in trend_dates]).reshape(-1, 1)
        X_base_recalc = np.array([(d.toordinal() - date_base_for_trend.toordinal()) for d in trend_data.index]).reshape(-1, 1)
        model_recalc = LinearRegression(); model_recalc.fit(X_base_recalc, y)
        trend_line = model_recalc.predict(trend_X)
        df_trend = pd.DataFrame(trend_line, index=trend_dates, columns=['Tendência'])
    else: df_trend = None
    return df_trend, forecast_date.normalize(), daily_velocity * 7
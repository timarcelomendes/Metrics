# jira_connector.py

import streamlit as st
from jira import JIRA, Issue
from functools import lru_cache
import pandas as pd
import requests
from requests.auth import HTTPBasicAuth
import json
from datetime import datetime, timezone
from collections import defaultdict
from security import find_user, get_global_configs, get_project_config, save_global_configs
from utils import get_start_end_states, find_date_for_status

@lru_cache(maxsize=32)
def connect_to_jira(server, user_email, api_token):
    """Conecta-se à instância do Jira Cloud usando um token de API."""
    try:
        jira_options = {'server': server}
        jira_client = JIRA(options=jira_options, basic_auth=(user_email, api_token))
        return jira_client
    except Exception as e:
        print(f"Erro ao conectar ao Jira: {e}")
        return None

@lru_cache(maxsize=32)
def get_projects(jira_client):
    """Busca todos os projetos acessíveis pela conta."""
    try:
        projects = jira_client.projects()
        return {p.name: p.key for p in projects}
    except Exception as e:
        print(f"Erro ao buscar projetos: {e}")
        return {}

@lru_cache(maxsize=32)
def get_project_details(jira_client, project_key):
    """Busca os detalhes de um projeto, incluindo seu tipo."""
    try:
        project = jira_client.project(project_key)
        return project
    except Exception as e:
        print(f"Erro ao buscar detalhes do projeto {project_key}: {e}")
        return None

@lru_cache(maxsize=32)
def get_boards(jira_client, project_key):
    """Busca todos os quadros (boards) associados a um projeto."""
    try:
        boards = jira_client.boards(projectKeyOrID=project_key)
        return [{'id': board.id, 'name': board.name, 'type': board.type} for board in boards]
    except Exception as e:
        print(f"Erro ao buscar quadros para o projeto {project_key}: {e}")
        return []

@lru_cache(maxsize=32)
def get_sprint_issues(jira_client, sprint_id):
    """Busca todas as issues de um sprint específico."""
    try:
        return jira_client.search_issues(f'sprint = {sprint_id}', maxResults=False, fields="*all")
    except Exception as e:
        st.error(f"Erro ao buscar issues do sprint {sprint_id}: {e}")
        return []

def get_issues_by_date_range(jira_client, project_key, start_date=None, end_date=None):
    """Busca issues ATUALIZADAS dentro de um intervalo de datas."""
    try:
        jql_query = f'project = "{project_key}"'
        if start_date and end_date:
            start_date_str = start_date.strftime('%Y-%m-%d')
            end_date_str = end_date.strftime('%Y-%m-%d')
            jql_query += f' AND updated >= "{start_date_str}" AND updated <= "{end_date_str}"'
        jql_query += " ORDER BY updated DESC"
        return jira_client.search_issues(jql_query, expand='changelog', maxResults=False)
    except Exception as e:
        print(f"Erro ao buscar issues por data para o projeto {project_key}: {e}")
        return []

def get_all_project_issues(jira_client, project_key):
    """Busca TODAS as issues de um projeto, sem filtros de data."""
    try:
        jql_query = f'project = "{project_key}" ORDER BY created DESC'
        return jira_client.search_issues(jql_query, expand='changelog', maxResults=False)
    except Exception as e:
        print(f"Erro ao buscar todas as issues do projeto {project_key}: {e}")
        return []
    
@lru_cache(maxsize=32)
def get_fix_versions(jira_client, project_key):
    """Busca TODAS as 'Fix Versions' de um projeto."""
    try:
        return jira_client.project_versions(project_key)
    except Exception as e:
        print(f"Erro ao buscar versões para o projeto {project_key}: {e}")
        return []

def get_issues_by_fix_version(jira_client, project_key, version_id):
    """Busca todas as issues associadas a uma 'Fix Version' específica."""
    try:
        jql_query = f'project = "{project_key}" AND fixVersion = {version_id}'
        return jira_client.search_issues(jql_query, expand='changelog', maxResults=False)
    except Exception as e:
        print(f"Erro ao buscar issues para a versão {version_id}: {e}")
        return []

def get_sprints_in_range(client: JIRA, project_key: str, start_date, end_date):
    """Busca sprints ativas e concluídas num período, buscando apenas em quadros Scrum."""
    try:
        boards = client.boards(projectKeyOrID=project_key)
        all_sprints = []
        added_sprint_ids = set()

        for board in boards:
            # --- CORREÇÃO AQUI: Verifica se o quadro é do tipo Scrum ---
            if board.type == 'scrum':
                try:
                    sprints = client.sprints(board_id=board.id, state='closed,active')
                    for sprint in sprints:
                        if sprint.id not in added_sprint_ids:
                            # Filtra as sprints fechadas pelo período de datas
                            if sprint.state == 'closed' and hasattr(sprint, 'completeDate'):
                                complete_date = pd.to_datetime(sprint.completeDate).date()
                                if start_date <= complete_date <= end_date:
                                    all_sprints.append(sprint)
                                    added_sprint_ids.add(sprint.id)
                            # Adiciona todas as sprints ativas
                            elif sprint.state == 'active':
                                all_sprints.append(sprint)
                                added_sprint_ids.add(sprint.id)
                except Exception:
                    # Se houver um erro específico ao buscar sprints de um quadro, ignora e continua
                    continue
                        
        return sorted(all_sprints, key=lambda s: (getattr(s, 'completeDate', '9999-12-31'), s.name), reverse=True)
    except Exception as e:
        st.error(f"Erro ao buscar quadros (boards) do projeto: {e}")
        return []
    
def get_jql_issue_count(client: JIRA, jql_string: str):
    """
    Executa uma consulta JQL e retorna apenas o número total de issues correspondentes.
    É muito eficiente pois usa maxResults=0.
    """
    if not jql_string:
        return 0
    try:
        # maxResults=0 é um truque para pedir ao Jira apenas o total, sem os dados das issues
        search_result = client.search_issues(jql_string, maxResults=0)
        return search_result.total
    except Exception as e:
        st.error(f"Erro ao executar a consulta JQL: {e}")
        return 0

@st.cache_data(show_spinner="A validar campo no Jira...")
def validate_jira_field(_client: JIRA, field_id: str):
    """
    Verifica se um field_id (padrão ou personalizado) é válido na instância do Jira.
    Usa cache para não repetir a busca de todos os campos a cada validação.
    """
    try:
        all_fields = _client.fields()
        for field in all_fields:
            if field['id'] == field_id:
                return True
        return False
    except Exception as e:
        st.error(f"Não foi possível validar o campo no Jira: {e}")
        return False
    
def search_issues_jql(jira_client, jql, max_results=2000):
    """
    Busca issues usando uma query JQL com uma paginação robusta que faz
    chamadas diretas à API com o método POST para máxima compatibilidade.
    """
    all_issues = []
    start_at = 0
    chunk_size = 100 # O máximo por página para a API de busca

    server_url = jira_client._options['server']
    # Acessa as credenciais como uma tupla (índice 0 e 1)
    auth = HTTPBasicAuth(jira_client._session.auth[0], jira_client._session.auth[1])
    headers = {
      "Accept": "application/json",
      "Content-Type": "application/json"
    }
    
    url = f"{server_url}/rest/api/2/search"

    while True:
        try:
            payload = json.dumps({
                "jql": jql,
                "startAt": start_at,
                "maxResults": chunk_size,
                "expand": ["changelog"]
            })
            
            response = requests.request("POST", url, data=payload, headers=headers, auth=auth)
            response.raise_for_status()
            
            data = response.json()
            issues_data = data.get('issues', [])
            
            # Reconstrói os objetos de Issue a partir dos dados JSON
            chunk = [Issue(options={'server': server_url}, session=jira_client._session, raw=raw_issue_data) for raw_issue_data in issues_data]
            all_issues.extend(chunk)
            
            # Condição de paragem robusta: para se a API retornar menos do que pedimos
            if len(chunk) < chunk_size:
                break
            
            start_at += len(chunk)
            
            if start_at >= max_results:
                break

        except Exception as e:
            print(f"ERRO CRÍTICO na chamada direta à API de busca: {e}")
            st.error("Não foi possível buscar as issues do Jira.")
            return []
            
    return all_issues

def get_project_boards(jira_client, project_key):
    """Busca todos os quadros (boards) associados a um projeto específico."""
    try:
        return jira_client.boards(projectKeyOrID=project_key)
    except Exception as e:
        print(f"ERRO ao buscar quadros para o projeto {project_key}: {e}")
        return []

def get_issues_by_board(jira_client, board_id):
    """
    Busca todas as issues de um quadro específico fazendo uma chamada GET direta à API,
    para máxima compatibilidade.
    """
    all_issues = []
    start_at = 0
    max_results_per_page = 50
    
    server_url = jira_client._options['server']
    # Acessa as credenciais como uma tupla (índice 0 e 1)
    auth = HTTPBasicAuth(jira_client._session.auth[0], jira_client._session.auth[1])
    headers = { "Accept": "application/json" }
    
    url = f"{server_url}/rest/agile/1.0/board/{board_id}/issue"

    while True:
        try:
            params = {
                'startAt': start_at,
                'maxResults': max_results_per_page,
                'expand': 'changelog'
            }
            
            response = requests.request("GET", url, headers=headers, params=params, auth=auth)
            response.raise_for_status()
            
            data = response.json()
            issues_data = data.get('issues', [])
            
            # Reconstrói os objetos de Issue a partir dos dados JSON
            chunk = [Issue(options={'server': server_url}, session=jira_client._session, raw=raw_issue_data) for raw_issue_data in issues_data]
            all_issues.extend(chunk)
            
            if data.get('isLast', True) or not issues_data:
                break
            start_at += len(chunk)

        except Exception as e:
            print(f"ERRO CRÍTICO na chamada direta à API para o quadro {board_id}: {e}")
            st.error("Não foi possível buscar as issues para este quadro.")
            return []
            
    return all_issues

@lru_cache(maxsize=128)
def get_project_issue_types(jira_client, project_key):
    """Busca os tipos de issues disponíveis para um projeto, excluindo sub-tarefas."""
    try:
        project_details = jira_client.project(project_key)
        # Retorna apenas os tipos de issue que não são sub-tarefas para evitar erros
        return [i.name for i in project_details.issueTypes if not i.subtask]
    except Exception as e:
        print(f"Erro ao buscar tipos de issues para o projeto {project_key}: {e}")
        return []
    
def get_issue(jira_client, issue_key):
    """
    Busca uma única issue no Jira pela sua chave.
    """
    try:
        issue = jira_client.issue(issue_key)
        return issue
    except Exception as e:
        # Adiciona um tratamento de erro mais detalhado
        print(f"Erro ao buscar a issue '{issue_key}': {e}")
        raise e
    
def get_issue_as_dict(jira_client, issue_key):
    """
    Busca uma única issue no Jira e converte todos os seus campos num
    dicionário de texto simples para ser usado pela IA.
    Esta versão é mais robusta e não depende da chave '_schema'.
    """
    try:
        # Passo 1: Obter um mapa de todos os campos disponíveis (ID -> Nome)
        all_fields = jira_client.fields()
        field_map = {field['id']: field['name'] for field in all_fields}

        # Passo 2: Buscar a issue
        issue = jira_client.issue(issue_key)
        
        # Dicionário para armazenar os dados limpos
        issue_data = {}
        
        # Passo 3: Percorrer os campos da issue e usar o mapa para "traduzir" os nomes
        for field_id in issue.raw['fields']:
            field_value = getattr(issue.fields, field_id, None)
            
            if field_value is None:
                continue
            
            cleaned_value = ""
            if isinstance(field_value, str):
                cleaned_value = field_value
            elif isinstance(field_value, list):
                str_values = []
                for item in field_value:
                    if hasattr(item, 'name'): str_values.append(item.name)
                    elif hasattr(item, 'value'): str_values.append(item.value)
                    elif isinstance(item, str): str_values.append(item)
                cleaned_value = ", ".join(str_values)
            elif hasattr(field_value, 'name'):
                cleaned_value = field_value.name
            elif hasattr(field_value, 'displayName'):
                cleaned_value = field_value.displayName
            else:
                cleaned_value = str(field_value)

            # Usa o mapa para obter o nome amigável do campo
            friendly_name = field_map.get(field_id, field_id)
            issue_data[friendly_name] = cleaned_value

        return issue_data
        
    except Exception as e:
        print(f"Erro ao buscar ou processar a issue '{issue_key}': {e}")
        raise e

@lru_cache(maxsize=1)
def get_statuses(jira_client):
    """Busca todos os status disponíveis na instância do Jira."""
    try:
        return jira_client.statuses()
    except Exception as e:
        print(f"Erro ao buscar todos os status: {e}")
        return []

@lru_cache(maxsize=1)
def get_issue_types(jira_client):
    """Busca todos os tipos de issue disponíveis na instância do Jira."""
    try:
        return jira_client.issue_types()
    except Exception as e:
        print(f"Erro ao buscar todos os tipos de issue: {e}")
        return []

@lru_cache(maxsize=1)
def get_priorities(jira_client):
    """Busca todas as prioridades disponíveis na instância do Jira."""
    try:
        return jira_client.priorities()
    except Exception as e:
        print(f"Erro ao buscar todas as prioridades: {e}")
        return []
    
def get_all_jira_fields(jira_client):
    """
    Busca todos os campos do Jira e os classifica como padrão ou personalizados,
    incluindo o tipo de dado mapeado para a aplicação.
    """
    try:
        all_fields = jira_client.fields()
        
        type_mapping = {
            'string': 'Texto', 'number': 'Numérico', 'date': 'Data', 
            'datetime': 'Data', 'user': 'Texto', 'project': 'Texto',
            'issuetype': 'Texto', 'priority': 'Texto', 'status': 'Texto',
            'option': 'Texto', 'array': 'Texto'
        }
        
        classified_fields = []
        for field in all_fields:
            schema_type = field.get('schema', {}).get('type', 'string')
            app_type = type_mapping.get(schema_type, 'Texto')
            
            classified_fields.append({
                "id": field['id'],
                "name": field['name'],
                "custom": field['custom'],
                "type": app_type
            })
        return classified_fields
    except Exception as e:
        st.error(f"Não foi possível buscar os campos do Jira: {e}")
        return []
    
@st.cache_data(ttl=3600, show_spinner="A carregar e processar os dados do Jira para o projeto...")
def load_and_process_project_data(_jira_client, project_key):
    if 'email' not in st.session_state:
        st.error("Sessão inválida. Por favor, faça login novamente.")
        return pd.DataFrame()

    user_data = find_user(st.session_state['email'])
    global_configs = get_global_configs()
    project_config = get_project_config(project_key) or {}

    user_standard_fields = user_data.get('standard_fields', [])
    user_custom_fields = user_data.get('enabled_custom_fields', [])
    all_available_standard = global_configs.get('available_standard_fields', {})
    all_available_custom = global_configs.get('custom_fields', [])
    estimation_field_config = project_config.get('estimation_field', {})

    fields_to_fetch = ["summary", "issuetype", "status", "assignee", "reporter", "priority", "created", "updated", "resolutiondate", "labels", "project", "parent", "fixVersions", "components", "statuscategorychangedate"]

    for field_name in user_standard_fields:
        field_id = all_available_standard.get(field_name, {}).get('id')
        if field_id: fields_to_fetch.append(field_id)
    for custom_field_name in user_custom_fields:
        field_details = next((f for f in all_available_custom if f.get('name') == custom_field_name), None)
        if field_details and field_details.get('id'): fields_to_fetch.append(field_details['id'])
    if estimation_field_config and estimation_field_config.get('id'):
        fields_to_fetch.append(estimation_field_config['id'])
    fields_to_fetch = list(set(fields_to_fetch))

    jql_query = f'project = "{project_key}"'
    issues_list, start_at, max_results = [], 0, 100
    initial_search = _jira_client.search_issues(jql_query, startAt=0, maxResults=0)
    total_issues = initial_search.total

    if total_issues == 0:
        st.warning("Nenhuma issue encontrada para este projeto.")
        return pd.DataFrame()

    progress_bar = st.progress(0, text=f"Buscando {total_issues} issues do projeto {project_key}...")
    while start_at < total_issues:
        issues_chunk = _jira_client.search_issues(jql_query, startAt=start_at, maxResults=max_results, fields=fields_to_fetch, expand='changelog')
        issues_list.extend(issues_chunk)
        start_at += len(issues_chunk)
        progress_bar.progress(min(start_at / total_issues, 1.0), text=f"Buscando {total_issues} issues... ({start_at}/{total_issues})")
    progress_bar.empty()

    all_fields_map = {field['id']: field['name'] for field in _jira_client.fields()}
    
    processed_data = []
    for issue in issues_list:
        issue_data = {'Issue': issue.key}
        for field_id in fields_to_fetch:
            field_name = all_fields_map.get(field_id, field_id)
            field_value = getattr(issue.fields, field_id, None)
            if field_value is not None:
                if hasattr(field_value, 'displayName'): issue_data[field_name] = field_value.displayName
                elif hasattr(field_value, 'value'): issue_data[field_name] = field_value.value
                elif isinstance(field_value, list) and all(hasattr(item, 'name') for item in field_value): issue_data[field_name] = ', '.join(item.name for item in field_value)
                else: issue_data[field_name] = str(field_value)
        
        status_times = defaultdict(float)
        last_change_date = pd.to_datetime(issue.fields.created).replace(tzinfo=None)
        
        initial_status = None
        for history in sorted(issue.changelog.histories, key=lambda h: h.created):
            for item in history.items:
                if item.field == 'status':
                    initial_status = item.fromString
                    break
            if initial_status: break
        
        current_status = initial_status or (issue.fields.status.name if hasattr(issue.fields.status, 'name') else None)

        if current_status:
            for history in sorted(issue.changelog.histories, key=lambda h: h.created):
                for item in history.items:
                    if item.field == 'status':
                        change_date = pd.to_datetime(history.created).replace(tzinfo=None)
                        time_spent = (change_date - last_change_date).total_seconds() / 86400
                        status_times[current_status] += time_spent
                        current_status = item.toString
                        last_change_date = change_date
            
            end_date = pd.to_datetime(issue.fields.resolutiondate).replace(tzinfo=None) if issue.fields.resolutiondate else pd.to_datetime(datetime.now())
            time_spent = (end_date - last_change_date).total_seconds() / 86400
            if current_status:
                status_times[current_status] += time_spent
        issue_data['status_times_days'] = dict(status_times)

        initial_state, done_state = get_start_end_states(project_key)
        created_date = pd.to_datetime(issue.fields.created).replace(tzinfo=None)
        resolution_date = pd.to_datetime(issue.fields.resolutiondate).replace(tzinfo=None) if issue.fields.resolutiondate else None
        start_date = find_date_for_status(issue.changelog, initial_state, default=created_date)
        
        issue_data.update({'Data de Criação': created_date, 'Data de Início': start_date, 'Data de Conclusão': resolution_date})
        if resolution_date:
            issue_data['Lead Time (dias)'] = (resolution_date - created_date).days
            if start_date: issue_data['Cycle Time (dias)'] = (resolution_date - start_date).days
        if hasattr(issue.fields, 'status') and hasattr(issue.fields.status, 'statusCategory'):
            issue_data['Categoria de Status'] = issue.fields.status.statusCategory.name
        processed_data.append(issue_data)
        
    df = pd.DataFrame(processed_data)
    
    if 'status_times_days' in df.columns:
        status_df = df['status_times_days'].apply(pd.Series).fillna(0)
        status_df = status_df.add_prefix('Tempo em: ')
        df = pd.concat([df.drop(columns=['status_times_days']), status_df], axis=1)

    final_field_names = {**{conf.get('id'): name for name, conf in all_available_standard.items()}, **{field.get('id'): field.get('name') for field in all_available_custom}}
    if estimation_field_config.get('id'):
        final_field_names[estimation_field_config['id']] = estimation_field_config.get('name')
    df.rename(columns=final_field_names, inplace=True)
    return df
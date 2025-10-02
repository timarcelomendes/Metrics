# jira_connector.py

import streamlit as st
from jira import JIRA, Issue
from functools import lru_cache
import pandas as pd
import requests
from stqdm import stqdm
from requests.auth import HTTPBasicAuth
import json
from datetime import datetime, timezone
from collections import defaultdict
from security import find_user, get_global_configs, get_project_config, save_global_configs
from utils import get_start_end_states, find_date_for_status

@lru_cache(maxsize=32)
def connect_to_jira(server, user_email, api_token):
    try:
        return JIRA(options={'server': server}, basic_auth=(user_email, api_token))
    except Exception as e:
        st.error(f"Erro ao conectar ao Jira: {e}")
        return None
    
@st.cache_data(ttl=3600, show_spinner="A obter os projetos do Jira...")
def get_jira_projects(_jira_client):
    try:
        return {p.name: p.key for p in _jira_client.projects()}
    except Exception as e:
        st.error(f"Não foi possível obter os projetos do Jira: {e}")
        return {}

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

@st.cache_data(ttl=3600, show_spinner="A buscar os dados da sprint...")
def get_sprint_issues(_jira_client, sprint_id, expand='changelog'):
    try:
        return _jira_client.search_issues(f'sprint = {sprint_id}', maxResults=False, expand=expand)
    except Exception as e:
        st.error(f"Erro ao buscar issues da sprint {sprint_id}: {e}")
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
    
def get_jql_issue_count(client, jql_query):
    if not jql_query: return 0
    try:
        issues = client.search_issues(jql_query, maxResults=0)
        return issues.total
    except Exception:
        return "Erro na consulta JQL"

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
    
def search_issues_jql(jira_client, jql, fields=None, max_results=5000):
    all_issues = []
    start_at = 0
    chunk_size = 100
    server_url = jira_client._options['server']
    auth = HTTPBasicAuth(jira_client._session.auth[0], jira_client._session.auth[1])
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    
    # --- CORREÇÃO FINAL: Usando o endpoint exato da mensagem de erro do Jira ---
    url = f"{server_url}/rest/api/3/search" # Mantido o /search pois o método é POST

    while True:
        try:
            payload_dict = {
                "jql": jql,
                "startAt": start_at,
                "maxResults": chunk_size,
                "expand": ["changelog"],
                "fields": fields or ["*navigable"]
            }
            response = requests.post(url, data=json.dumps(payload_dict), headers=headers, auth=auth, timeout=30)
            response.raise_for_status()
            data = response.json()
            issues_data = data.get('issues', [])
            
            if not issues_data: break

            all_issues.extend([Issue(options={'server': server_url}, session=jira_client._session, raw=raw) for raw in issues_data])
            
            # Condição de paragem mais robusta
            if len(all_issues) >= data.get('total', 0): break
            start_at += len(issues_data)
            if len(all_issues) >= max_results: break
        
        except requests.exceptions.HTTPError as e:
            # Fornece uma mensagem de erro mais clara na interface
            st.error(f"Erro de comunicação com o Jira (Código: {e.response.status_code}). Verifique se a sua conexão tem permissões para ler issues neste projeto. Detalhes no terminal.")
            print(f"Detalhes do Erro do Jira: {e.response.text}")
            return []
        except Exception as e:
            st.error(f"Ocorreu um erro inesperado ao buscar issues: {e}")
            return []
            
    return all_issues

def get_project_boards(jira_client, project_key):
    """Busca todos os quadros (boards) associados a um projeto específico."""
    try:
        return jira_client.boards(projectKeyOrID=project_key)
    except Exception as e:
        print(f"ERRO ao buscar quadros para o projeto {project_key}: {e}")
        return []
    
@st.cache_data(ttl=3600, show_spinner="A buscar as issues do projeto... Isso pode demorar.")
def get_project_issues(_jira_client, project_key, expand='changelog'):
    """
    CORREÇÃO FINAL: Busca todas as issues de um projeto usando o método moderno
    que funciona com a biblioteca jira-python atualizada.
    """
    try:
        # maxResults=False é o método correto para obter todos os resultados.
        # Isto só funciona corretamente com uma versão recente da biblioteca.
        all_issues = _jira_client.search_issues(
            f'project = "{project_key}" ORDER BY created DESC',
            maxResults=False,
            expand=expand
        )
        return all_issues
    except Exception as e:
        st.error(f"Erro ao buscar issues do projeto '{project_key}': {e}")
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

@st.cache_data(ttl=3600, show_spinner="A obter os status do Jira...")
def get_statuses(_jira_client):
    try:
        return _jira_client.statuses()
    except Exception as e:
        st.error(f"Erro ao buscar os status: {e}")
        return []

@st.cache_data(ttl=3600, show_spinner="A obter os tipos de issue do Jira...")
def get_issue_types(_jira_client):
    try:
        return _jira_client.issue_types()
    except Exception as e:
        st.error(f"Erro ao buscar os tipos de issue: {e}")
        return []

@st.cache_data(ttl=3600, show_spinner="A obter as prioridades do Jira...")
def get_priorities(_jira_client):
    try:
        return _jira_client.priorities()
    except Exception as e:
        st.error(f"Erro ao buscar as prioridades: {e}")
        return []
    
@st.cache_data(ttl=3600, show_spinner="A carregar todos os campos do Jira...")
def get_all_jira_fields(_jira_client):
    try:
        all_fields = _jira_client.fields()
        return [
            {
                'id': field['id'],
                'name': field['name'],
                'custom': field['custom'],
                'type': field.get('schema', {}).get('type', 'Desconhecido')
            }
            for field in all_fields
        ]
    except Exception as e:
        st.error(f"Não foi possível carregar os campos do Jira: {e}")
        return []

@st.cache_data(ttl=3600, show_spinner="A carregar e processar os dados do projeto do Jira...")
def load_and_process_project_data(_jira_client, project_key):
    """
    Carrega e processa todos os dados de um projeto, aplicando métricas
    e configurações de forma centralizada.
    """
    from metrics_calculator import (
        calculate_lead_time, calculate_cycle_time,
        get_issue_estimation, calculate_time_in_status,
        find_completion_date
    )
    from security import get_project_config, find_user

    project_config = get_project_config(project_key) or {}
    estimation_config = project_config.get('estimation_field', {})
    should_calculate = project_config.get('calculate_time_in_status', False)

    all_statuses = [s.name for s in get_statuses(_jira_client)]
    issues = get_project_issues(_jira_client, project_key)

    if not issues:
        st.warning("Nenhuma issue encontrada para este projeto.")
        return pd.DataFrame()

    data = []
    for issue in stqdm(issues, desc=f"A processar {len(issues)} issues..."):
        completion_date = find_completion_date(issue, project_config)
        issue_data = {
            'Issue': issue.key,
            'Tipo de Issue': issue.fields.issuetype.name,
            'Status': issue.fields.status.name,
            'Categoria de Status': issue.fields.status.statusCategory.name,
            'Responsável': issue.fields.assignee.displayName if issue.fields.assignee else 'Não atribuído',
            'Prioridade': issue.fields.priority.name if issue.fields.priority else 'N/A',
            'Data de Criação': pd.to_datetime(issue.fields.created).tz_localize(None).normalize(),
            'Data de Conclusão': completion_date,
            'Lead Time (dias)': calculate_lead_time(issue, completion_date),
            'Cycle Time (dias)': calculate_cycle_time(issue, completion_date, project_config),
            estimation_config.get('name', 'Estimativa'): get_issue_estimation(issue, estimation_config) if estimation_config else None,
        }
        if should_calculate:
            time_in_each_status = calculate_time_in_status(issue, all_statuses, completion_date)
            for status_name, time_days in time_in_each_status.items():
                if time_days and time_days > 0:
                    issue_data[f'Tempo em: {status_name}'] = time_days
        data.append(issue_data)

    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    user_data = find_user(st.session_state['email'])
    enabled_custom_fields = user_data.get('enabled_custom_fields', [])
    all_custom_fields_map = {f['name']: f['id'] for f in st.session_state.get('global_configs', {}).get('custom_fields', [])}
    for field_name in enabled_custom_fields:
        field_id = all_custom_fields_map.get(field_name)
        if field_id:
            df[field_name] = [getattr(issue.fields, field_id, None) for issue in issues]
    return df
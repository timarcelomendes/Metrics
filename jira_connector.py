# jira_connector.py

import streamlit as st
import os
from jira import JIRA, Issue
from functools import lru_cache
import pandas as pd
import requests
from requests.auth import HTTPBasicAuth
import json

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
def get_sprints(client: JIRA, board_id: int, state='active,closed'):
    """Busca sprints de um quadro, por padrão ativas e fechadas."""
    try:
        return client.sprints(board_id, state=state)
    except Exception as e:
        # Não mostra erro na interface, apenas retorna lista vazia
        return []

def get_sprint_issues(jira_client, sprint_id):
    """Busca todas as issues de uma sprint específica."""
    try:
        return jira_client.search_issues(f'Sprint = {sprint_id}', expand='changelog', maxResults=False)
    except Exception as e:
        print(f"Erro ao buscar issues da sprint {sprint_id}: {e}")
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
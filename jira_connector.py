# jira_connector.py

import os
from jira import JIRA
from functools import lru_cache
import pandas as pd

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
def get_sprints(jira_client, board_id):
    """Busca todas as sprints de um quadro específico."""
    try:
        sprints = jira_client.sprints(board_id, state='closed,active')
        return {s.name: s.id for s in sprints}
    except Exception as e:
        print(f"Erro ao buscar sprints para o quadro ID {board_id}: {e}")
        return {}

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
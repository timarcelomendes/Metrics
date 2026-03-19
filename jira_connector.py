# jira_connector.py

import streamlit as st
from jira import JIRA, Issue, JIRAError
from functools import lru_cache
import pandas as pd
import requests
from stqdm import stqdm
from requests.auth import HTTPBasicAuth
import json
from datetime import datetime, timezone
from collections import defaultdict
from security import get_project_config
from metrics_calculator import find_completion_date, calculate_lead_time, calculate_cycle_time
from pathlib import Path

STANDARD_FIELD_API_MAP = {
    'AffectedVersions': 'versions',
    'aggregatetimeoriginalestimate': 'aggregatetimeoriginalestimate',
    'aggregatetimeestimate': 'aggregatetimeestimate',
    'aggregatetimespent': 'aggregatetimespent',
    'aggregateprogress': 'aggregateprogress',
    'Assignee': 'assignee',
    'Attachments': 'attachment',
    'Category': 'category',
    'Comment': 'comment',
    'Components': 'components',
    'Created': 'created',
    'Creator': 'creator',
    'Description': 'description',
    'DueDate': 'duedate',
    'Environment': 'environment',
    'FixVersions': 'fixVersions',
    'IssueType': 'issuetype',
    'issuelinks': 'issuelinks',
    'Labels': 'labels',
    'LastViewed': 'lastViewed',
    'LinkedIssues': 'issuelinks',
    'Parent': 'parent',
    'Priority': 'priority',
    'Project': 'project',
    'progress': 'progress',
    'Reporter': 'reporter',
    'Resolution': 'resolution',
    'resolutiondate': 'resolutiondate',
    'Resolved': 'resolutiondate',
    'SecurityLevel': 'security',
    'Status': 'status',
    'StatusCategory': 'statuscategory',
    'subtasks': 'subtasks',
    'Summary': 'summary',
    'thumbnail': 'thumbnail',
    'TimeTracking': 'timetracking',
    'timespent': 'timespent',
    'timeoriginalestimate': 'timeoriginalestimate',
    'timeestimate': 'timeestimate',
    'Updated': 'updated',
    'Votes': 'votes',
    'Watchers': 'watches',
    'workratio': 'workratio',
}


def normalize_standard_fields_for_api(standard_fields):
    """Converte IDs amigáveis/camel case da app para os nomes esperados pela API do Jira."""
    normalized_fields = []
    for field in standard_fields or []:
        normalized_field = STANDARD_FIELD_API_MAP.get(field, field)
        if normalized_field not in normalized_fields:
            normalized_fields.append(normalized_field)
    return normalized_fields


@lru_cache(maxsize=32)
def connect_to_jira(server, user_email, api_token):
    try:
        return JIRA(
            options={'server': server}, 
            basic_auth=(user_email, api_token),
            timeout=30 
        )
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
    """
    Busca todos os projetos visíveis para o cliente Jira e os retorna
    como um dicionário {nome_do_projeto: chave_do_projeto}.
    Inclui tratamento de erro robusto.
    """
    try:
        # A API retorna uma lista de objetos de projeto
        all_projects = jira_client.projects()
        
        # Verifica se a lista não está vazia antes de processar
        if not all_projects:
            return {} # Retorna um dicionário vazio se nenhum projeto for encontrado
            
        # Converte a lista de objetos num dicionário no formato {nome: chave}
        projects_dict = {project.name: project.key for project in all_projects}
        return projects_dict

    except JIRAError as e:
        # Fornece feedback específico em caso de erro de permissão ou outro
        st.error(
            f"Ocorreu um erro ao buscar os projetos do Jira (Status: {e.status_code}). "
            f"Mensagem: {e.text}"
        )
        return {} # Retorna um dicionário vazio em caso de erro
    except Exception as e:
        st.error(f"Ocorreu um erro inesperado ao processar os projetos: {e}")
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

@st.cache_data(ttl=3600, show_spinner="A buscar issues da sprint...")
def get_sprint_issues(_client, sprint_id):
    """Busca todas as issues de uma sprint específica."""
    try:
        jql = f"'Sprint' = {sprint_id}"
        return _client.search_issues(jql, maxResults=False, expand="changelog")
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

@st.cache_data(ttl=300)
def get_all_project_issues(_jira_client: JIRA, project_key: str, extra_fields: list = None):
    jql = f"project = '{project_key}'"
    
    fields = [
        'summary', 'status', 'issuetype', 'created', 
        'resolutiondate', 'assignee', 'reporter', 'priority', 
        'components', 'labels', 'project'
    ]
    
    if extra_fields:
        for field in extra_fields:
            if field not in fields:
                fields.append(field)
                
    return _jira_client.search_issues(
        jql, 
        fields=fields, 
        maxResults=False, 
        expand="changelog"
    )
    
@lru_cache(maxsize=32)
def get_fix_versions(jira_client, project_key):
    """Busca TODAS as 'Fix Versions' de um projeto."""
    try:
        return jira_client.project_versions(project_key)
    except Exception as e:
        print(f"Erro ao buscar versões para o projeto {project_key}: {e}")
        return []

def get_issues_by_fix_version(jira_client: JIRA, project_key: str, version_id: str, extra_fields: list = None):
    jql = f"project = '{project_key}' AND fixVersion = {version_id}"
    
    fields = [
        'summary', 'status', 'issuetype', 'created', 
        'resolutiondate', 'assignee', 'reporter', 'priority', 
        'components', 'labels', 'project'
    ]
    
    if extra_fields:
        for field in extra_fields:
            if field not in fields:
                fields.append(field)
                
    return jira_client.search_issues(
        jql, 
        fields=fields, 
        maxResults=False, 
        expand="changelog" 
    )

@st.cache_data(ttl=3600)
def get_sprints_in_range(_client, project_key, start_date, end_date):
    """Busca sprints (ativas ou fechadas) de um projeto que se sobrepõem ao intervalo de datas."""
    try:
        boards = _client.boards(projectKeyOrID=project_key)
        all_sprints = []
        for board in boards:
            try:
                sprints = _client.sprints(board.id, state='closed,active')
                for sprint in sprints:
                    sprint_start = pd.to_datetime(sprint.startDate).date() if hasattr(sprint, 'startDate') else None
                    sprint_end = pd.to_datetime(sprint.endDate).date() if hasattr(sprint, 'endDate') else None
                    
                    if sprint_start and sprint_end:
                        if max(start_date, sprint_start) <= min(end_date, sprint_end):
                            all_sprints.append(sprint)
            except Exception:
                continue
        return all_sprints
    except Exception as e:
        st.error(f"Erro ao buscar sprints: {e}")
        return []

@st.cache_data(show_spinner="A validar campo no Jira...")
def validate_jira_field(_client: JIRA, field_id: str):
    """Verifica se um field_id (padrão ou personalizado) é válido na instância do Jira."""
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
    url = f"{server_url}/rest/api/3/search"

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
            
            if len(all_issues) >= data.get('total', 0): break
            start_at += len(issues_data)
            if len(all_issues) >= max_results: break
        
        except requests.exceptions.HTTPError as e:
            st.error(f"Erro de comunicação com o Jira (Código: {e.response.status_code}). Verifique se a sua conexão tem permissões para ler issues neste projeto.")
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
    
@st.cache_data(ttl=3600, show_spinner="A buscar issues do projeto no Jira...")
def get_project_issues(_client, project_key, jql_filter="", standard_fields=None, custom_fields=None): # <-- PARÂMETROS MODIFICADOS
    """
    Busca todas as issues de um projeto específico, com opção de filtro JQL adicional
    e agora com seleção de campos.
    """
    if not _client or not project_key:
        return []
    
    try:
        jql = f"project = '{project_key}'"

        if jql_filter:
            jql += f" AND {jql_filter}"
        
        # --- INÍCIO DA CORREÇÃO E ATUALIZAÇÃO PARA SLA ---
        # Lista de campos padrão que a aplicação SEMPRE precisa
        default_fields = [
            'summary', 'status', 'issuetype', 'created', 
            'resolutiondate', 'assignee', 'reporter', 'priority', 
            'components', 'labels', 'project', 'statuscategory', 'parent',
            'timespent', # Adicionado para a correção do erro anterior e análise de Performance
            'comment' # Adicionado para análise de SLA (Tempo de Primeiro Atendimento)
        ]
        
        # Adiciona os campos padrão habilitados pelo usuário
        if standard_fields:
            default_fields.extend(normalize_standard_fields_for_api(standard_fields))
        
        # Adiciona os campos customizados habilitados pelo usuário
        if custom_fields:
            default_fields.extend(custom_fields)
        
        # Remove duplicados
        final_fields_list = list(set(default_fields))
        # --- FIM DA CORREÇÃO E ATUALIZAÇÃO PARA SLA ---
        
        issues = _client.search_issues(
            jql, 
            fields=final_fields_list, # <-- PASSA A LISTA DE CAMPOS
            maxResults=False, 
            expand="changelog"
        )
        return issues
        
    except Exception as e:
        st.error(f"Erro ao buscar issues do Jira para o projeto '{project_key}': {e}")
        return []

def get_issues_by_board(jira_client: JIRA, board_id: str, extra_fields: list = None):
    jql = ""
    
    # --- INÍCIO DA CORREÇÃO DEFINITIVA ---
    try:
        # 1. Construir a URL correta manualmente para evitar o erro "/api/2/"
        # A API Agile fica em /rest/agile/1.0/... e não dentro de /api/2
        base_url = jira_client._options['server'].rstrip('/')
        url = f"{base_url}/rest/agile/1.0/board/{board_id}/configuration"
        
        # 2. Fazer a requisição direta usando a sessão já autenticada do cliente
        # Isso evita que a biblioteca altere a URL
        response = jira_client._session.get(url)
        
        # Verifica se a requisição funcionou
        if response.status_code == 200:
            data = response.json()
            
            # 3. Extrair o ID do filtro da configuração
            if 'filter' in data and 'id' in data['filter']:
                filter_id = data['filter']['id']
                
                # 4. Buscar a JQL do filtro (aqui podemos usar o método padrão)
                filter_obj = jira_client.filter(filter_id)
                jql = filter_obj.jql
                
                # (Boa prática) Garantir ordenação
                if "order by" not in jql.lower():
                    jql += " ORDER BY created DESC"
            else:
                # Se não tiver filtro (raro), usa fallback
                print(f"Aviso: Quadro {board_id} sem filtro configurado.")
                jql = f"board = {board_id}"
        else:
            # Se a API Agile falhar (ex: permissão), usa fallback
            print(f"Aviso: Falha na API Agile (Status {response.status_code}). Usando fallback.")
            jql = f"board = {board_id}"
            
    except Exception as e:
        # Em último caso, usa a JQL simples
        st.warning(f"Não foi possível obter o filtro avançado do quadro. Usando método simplificado. Erro: {e}")
        jql = f"board = {board_id}"
    # --- FIM DA CORREÇÃO ---

    fields = [
        'summary', 'status', 'issuetype', 'created', 
        'resolutiondate', 'assignee', 'reporter', 'priority', 
        'components', 'labels', 'project'
    ]
    
    if extra_fields:
        for field in extra_fields:
            if field not in fields:
                fields.append(field)
                
    try:
        return jira_client.search_issues(
            jql, 
            fields=fields, 
            maxResults=False, 
            expand="changelog" 
        )
    except JIRAError as e:
        st.error(f"Erro ao executar a busca de issues: {e.text}")
        return []
        
@st.cache_data(ttl=3600)
def get_project_issue_types(_jira_client, project_key):
    """Busca os objetos de tipos de issues disponíveis para um projeto, excluindo sub-tarefas."""
    try:
        project_details = _jira_client.project(project_key)
        # Retorna a lista de OBJETOS, e não apenas os nomes
        return [it for it in project_details.issueTypes if not it.subtask]
    except Exception as e:
        st.error(f"Erro ao buscar tipos de issue para o projeto {project_key}: {e}")
        return []
    
@st.cache_data(ttl=600)
def get_jira_statuses(_jira_client: JIRA, project_key: str):
    """
    Busca TODOS os status disponíveis na instância Jira
    que o cliente (API token) pode ver.
    """
    try:
        # Esta é a chamada de API padrão e mais robusta.
        # Ela busca todos os status, incluindo os globais e os específicos
        # de projetos (como "Done" / "Concluído" do MOJI).
        all_statuses = _jira_client.statuses()
        
        return all_statuses
        
    except Exception as e:
        st.error(f"Erro fatal ao buscar a lista de status do Jira: {e}")
        return []
    
def get_issue(jira_client, issue_key):
    """Busca uma única issue no Jira pela sua chave."""
    try:
        issue = jira_client.issue(issue_key)
        return issue
    except Exception as e:
        print(f"Erro ao buscar a issue '{issue_key}': {e}")
        raise e
    
def get_issue_as_dict(jira_client, issue_key):
    """Busca uma única issue no Jira e converte todos os seus campos num dicionário."""
    try:
        all_fields = jira_client.fields()
        field_map = {field['id']: field['name'] for field in all_fields}
        issue = jira_client.issue(issue_key)
        issue_data = {}
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

def get_priorities(_jira_client):
    """Busca todas as prioridades disponíveis na instância Jira, com tratamento de erro aprimorado."""
    try:
        return _jira_client.priorities()
    except JIRAError as e:
        # Verifica se o erro é especificamente de autenticação (401)
        if e.status_code == 401:
            st.error(
                "Falha na autenticação com o Jira (Erro 401). "
                "Por favor, verifique se a sua Conexão Jira ativa está correta (URL, e-mail e token) e tente novamente.",
                icon="🚫"
            )
        else:
            # Para outros erros relacionados ao Jira (ex: permissão negada, projeto não encontrado)
            st.error(
                f"Ocorreu um erro ao comunicar com o Jira (Erro {e.status_code}). "
                "Verifique sua conexão e as configurações do projeto.",
                icon="🔥"
            )
        return [] # Retorna uma lista vazia para a aplicação continuar a funcionar
    except Exception as e:
        # Captura qualquer outro erro inesperado
        st.error(f"Ocorreu um erro inesperado ao buscar as prioridades: {e}")
        return []
    
@st.cache_data(ttl=3600, show_spinner="A carregar todos os campos do Jira...")
def get_all_jira_fields(_jira_client):
    try:
        all_fields = _jira_client.fields()
        return [
            {'id': field['id'], 'name': field['name'], 'custom': field['custom'],
             'type': field.get('schema', {}).get('type', 'Desconhecido')}
            for field in all_fields
        ]
    except Exception as e:
        st.error(f"Não foi possível carregar os campos do Jira: {e}")
        return []

@st.cache_resource(ttl=3600)
def get_jira_client(server, user, api_token):
    """Cria e armazena em cache um cliente JIRA."""
    try:
        return JIRA(server=server, basic_auth=(user, api_token))
    except Exception as e:
        st.error(f"Falha ao conectar ao Jira: {e}")
        return None

def get_issue_count(jira_client, jql):
    """Retorna o número de issues para uma consulta JQL."""
    try:
        return len(jira_client.search_issues(jql, maxResults=0, fields="key"))
    except Exception as e:
        return str(e)

@st.cache_data(ttl=86400, show_spinner="A carregar metadados dos campos do Jira...")
def get_jira_fields(_client):
    """Retorna uma lista de todos os campos (padrão e customizados) do Jira."""
    try:
        return _client.fields()
    except Exception as e:
        st.error(f"Não foi possível carregar os campos do Jira: {e}")
        return []

def get_jql_issue_count(_client, jql):
    """Executa uma consulta JQL e retorna apenas a contagem de resultados."""
    if not jql:
        return 0
    try:
        search_result = _client.search_issues(jql, maxResults=0)
        return search_result.total
    except Exception as e:
        return f"Erro na JQL: {e}"
    
def validate_jira_connection(jira_client):
    """
    Tenta validar a conexão com o Jira.
    Retorna (True, "Sucesso") se válida, ou (False, "Mensagem de Erro") caso contrário.
    """
    if not jira_client:
        return False, "O cliente Jira não pôde ser inicializado."
    try:
        # A chamada .server_info() é ideal para um teste de conexão
        jira_client.server_info()
        return True, "Conexão validada com sucesso."
    except JIRAError as e:
        if e.status_code == 401:
            return False, "Falha na autenticação (Erro 401). Verifique seu e-mail e token de API."
        if e.status_code == 404:
            return False, "Não foi possível encontrar a URL do Jira (Erro 404). Verifique se o endereço está correto."
        return False, f"Erro do Jira: {e.text} (Status: {e.status_code})"
    except Exception as e:
        # Captura outros erros de conexão (ex: falha de rede)
        return False, f"Erro de conexão. Verifique sua rede e a URL do Jira. Detalhes: {e}"

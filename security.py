# security.py

import streamlit as st
from pymongo import MongoClient
from cryptography.fernet import Fernet
from passlib.context import CryptContext
from bson.objectid import ObjectId
from config import *

# --- Configuração de Hashing de Senha ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    """Verifica uma senha em texto plano contra uma senha com hash."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    """Gera o hash de uma senha."""
    return pwd_context.hash(password)

# --- Funções de Criptografia de Token ---
@st.cache_resource
def get_cipher():
    """Obtém a instância do cifrador a partir dos secrets."""
    key = st.secrets["ENCRYPTION_KEY"]
    return Fernet(key.encode())

def encrypt_token(token: str):
    """Encripta um token."""
    return get_cipher().encrypt(token.encode()).decode()

def decrypt_token(encrypted_token: str):
    """Desencripta um token."""
    return get_cipher().decrypt(encrypted_token.encode()).decode()

# --- Funções de Conexão e Acesso às Coleções do MongoDB ---
@st.cache_resource
def get_db_client():
    """Retorna uma instância do cliente MongoDB, em cache para performance."""
    return MongoClient(st.secrets["MONGO_CONNECTION_STRING"])

def get_db():
    """Retorna a instância da base de dados."""
    return get_db_client().get_database("dashboard_metrics")

def get_users_collection():
    """Retorna a coleção de utilizadores."""
    return get_db().get_collection("users")

def get_connections_collection():
    """Retorna a coleção de conexões Jira."""
    return get_db().get_collection("jira_connections")

def get_dashboards_collection():
    """Retorna a coleção de dashboards dos utilizadores."""
    return get_db().get_collection("user_dashboards")

def get_app_configs_collection():
    """Retorna a coleção de configurações globais da aplicação."""
    return get_db().get_collection("app_configs")

def get_project_configs_collection():
    """Retorna a coleção de configurações por projeto."""
    return get_db().get_collection("project_configs")

# --- Funções de Gestão de Utilizadores ---
def find_user(email):
    """Encontra um utilizador pelo email."""
    return get_users_collection().find_one({'email': email})

def create_user(email, hashed_password):
    """Cria um novo utilizador na base de dados."""
    get_users_collection().insert_one({'email': email, 'hashed_password': hashed_password})

# --- Funções de Gestão de Conexões Jira ---
def add_jira_connection(user_email, conn_name, url, api_email, encrypted_token):
    """Adiciona uma nova conexão Jira para um utilizador."""
    get_connections_collection().insert_one({
        "user_email": user_email, "connection_name": conn_name,
        "jira_url": url, "jira_email": api_email,
        "encrypted_token": encrypted_token
    })

def get_user_connections(user_email):
    """Busca todas as conexões Jira de um utilizador."""
    return list(get_connections_collection().find({"user_email": user_email}))

def delete_jira_connection(connection_id):
    """Remove uma conexão Jira pelo seu ID."""
    get_connections_collection().delete_one({"_id": ObjectId(connection_id)})

# --- Funções de Gestão de Dashboards ---
def get_user_dashboard(user_email, project_key):
    """Busca o layout do dashboard de um utilizador para um projeto específico."""
    return get_dashboards_collection().find_one({"user_email": user_email, "project_key": project_key})

def save_user_dashboard(user_email, project_key, layout):
    """Guarda ou atualiza o layout do dashboard de um utilizador para um projeto."""
    get_dashboards_collection().update_one(
        {"user_email": user_email, "project_key": project_key},
        {"$set": {"layout": layout}},
        upsert=True
    )

# --- Funções de Gestão de Configurações ---
def get_project_config(project_key):
    """Busca a configuração para um projeto específico."""
    if not project_key: return None
    return get_project_configs_collection().find_one({'_id': project_key})

def save_project_config(project_key, config_data):
    """Guarda a configuração para um projeto específico."""
    get_project_configs_collection().update_one(
        {'_id': project_key},
        {'$set': config_data},
        upsert=True
    )

def save_global_configs(new_configs):
    """Guarda o documento de configurações globais inteiro."""
    get_app_configs_collection().update_one(
        {'_id': 'global_settings'},
        {'$set': new_configs},
        upsert=True
    )

def get_global_configs():
    """Busca as configs globais, as cria, ou as corrige se estiverem em formato antigo."""
    collection = get_app_configs_collection()
    configs = collection.find_one({'_id': 'global_settings'})
    if configs is None:
        configs = {
            '_id': 'global_settings',
            'available_standard_fields': AVAILABLE_STANDARD_FIELDS,
            'status_mapping': { 'initial': DEFAULT_INITIAL_STATES, 'done': DEFAULT_DONE_STATES },
            'custom_fields': [],
            'sprint_goal_threshold': 90
        }
        collection.insert_one(configs)
        return configs
    
    needs_update = False
    if 'available_standard_fields' in configs:
        for name, details in list(configs['available_standard_fields'].items()):
            if isinstance(details, str):
                configs['available_standard_fields'][name] = {'id': details, 'type': 'Texto'}
                needs_update = True
    if 'custom_fields' in configs:
        for field in configs['custom_fields']:
            if 'type' not in field:
                field['type'] = 'Texto'
                needs_update = True
    if 'sprint_goal_threshold' not in configs:
        configs['sprint_goal_threshold'] = 90
        needs_update = True
        
    if needs_update:
        save_global_configs(configs)
        st.toast("Estrutura de configuração antiga atualizada automaticamente!", icon="✅")

    return configs
    
def save_last_project(email, project_key):
    """Guarda a chave do último projeto selecionado pelo utilizador na base de dados."""
    get_users_collection().update_one(
        {'email': email},
        {'$set': {'last_project_key': project_key}}
    )
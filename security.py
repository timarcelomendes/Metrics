# security.py

import streamlit as st
from pymongo import MongoClient
from cryptography.fernet import Fernet
from passlib.context import CryptContext
from config import *

# --- Configuração de Hashing ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

# --- Funções de Criptografia de Token ---
@st.cache_resource
def get_cipher():
    key = st.secrets["ENCRYPTION_KEY"]
    return Fernet(key.encode())

def encrypt_token(token: str):
    return get_cipher().encrypt(token.encode()).decode()

def decrypt_token(encrypted_token: str):
    return get_cipher().decrypt(encrypted_token.encode()).decode()

# --- Funções da Base de Dados ---
@st.cache_resource(show_spinner="Aguarde, a estabelecer conexão segura...")
def get_db_client():
    """Retorna uma instância do cliente MongoDB."""
    return MongoClient(st.secrets["MONGO_CONNECTION_STRING"])

def get_users_collection():
    client = get_db_client()
    db = client.get_database("dashboard_metrics")
    return db.get_collection("users")

def get_app_configs_collection():
    """Retorna a coleção de configurações globais da aplicação."""
    client = get_db_client()
    db = client.get_database("dashboard_metrics")
    return db.get_collection("app_configs")

def save_global_configs(new_configs):
    """Guarda o documento de configurações globais inteiro."""
    collection = get_app_configs_collection()
    collection.update_one(
        {'_id': 'global_settings'},
        {'$set': new_configs},
        upsert=True
    )

def get_global_configs():
    """
    Busca as configs globais, as cria, ou as corrige se estiverem em formato antigo.
    """
    collection = get_app_configs_collection()
    configs = collection.find_one({'_id': 'global_settings'})

    # Cenário 1: Primeira execução, nada existe na BD.
    if configs is None:
        configs = {
            '_id': 'global_settings',
            'available_standard_fields': AVAILABLE_STANDARD_FIELDS,
            'status_mapping': { 
                'initial': DEFAULT_INITIAL_STATES,
                'done': DEFAULT_DONE_STATES 
            },
            'custom_fields': [],
            'sprint_goal_threshold': 90 # Valor padrão para o novo parâmetro
        }
        collection.insert_one(configs)
        return configs

    # --- Lógica de Autocorreção para dados antigos ---
    needs_update = False
    
    # Verifica e corrige a estrutura de 'available_standard_fields'
    if 'available_standard_fields' in configs:
        for name, details in configs['available_standard_fields'].items():
            if isinstance(details, str):
                configs['available_standard_fields'][name] = {'id': details, 'type': 'Texto'}
                needs_update = True
    
    # Verifica e corrige a estrutura de 'custom_fields'
    if 'custom_fields' in configs:
        for field in configs['custom_fields']:
            if 'type' not in field:
                field['type'] = 'Texto'
                needs_update = True
    
    # --- NOVO: Verifica e adiciona a chave de threshold se estiver em falta ---
    if 'sprint_goal_threshold' not in configs:
        configs['sprint_goal_threshold'] = 90 # Adiciona o valor padrão
        needs_update = True
    
    # Se alguma correção foi feita, guarda a nova estrutura na base de dados
    if needs_update:
        save_global_configs(configs)
        st.toast("Estrutura de configuração atualizada automaticamente!", icon="✅")

    return configs

def find_user(email):
    """Encontra um utilizador pelo email."""
    collection = get_users_collection()
    return collection.find_one({'email': email})

def create_user(email, hashed_password):
    """Cria um novo utilizador na base de dados."""
    get_users_collection().insert_one({'email': email, 'hashed_password': hashed_password})

def save_jira_credentials(email, url, api_email, encrypted_token):
    """Guarda as credenciais do Jira para um utilizador."""
    get_users_collection().update_one(
        {'email': email},
        {'$set': {
            'jira_url': url,
            'jira_email': api_email,
            'encrypted_token': encrypted_token
        }}
    )

def save_last_project(email, project_key):
    """Guarda a chave do último projeto selecionado pelo utilizador na base de dados."""
    get_users_collection().update_one(
        {'email': email},
        {'$set': {'last_project_key': project_key}}
    )

def save_user_dashboard(email, dashboard_layout):
    """Guarda ou atualiza a lista completa de itens do dashboard para um utilizador."""
    get_users_collection().update_one(
        {'email': email},
        {'$set': {'dashboard_layout': dashboard_layout}}
    )

def save_user_custom_fields(email, custom_fields):
    """Guarda a lista de campos personalizados de um utilizador."""
    get_users_collection().update_one(
        {'email': email}, 
        {'$set': {'custom_fields': custom_fields}})

def save_user_standard_fields(email, standard_fields):
    """Guarda a lista de campos padrão selecionados por um utilizador."""
    get_users_collection().update_one(
        {'email': email}, 
        {'$set': {'standard_fields': standard_fields}})
    
@st.cache_resource
def get_project_configs_collection():
    """Retorna a coleção de configurações por projeto."""
    client = get_db_client()
    db = client.get_database("dashboard_metrics")
    return db.get_collection("project_configs")

def get_project_config(project_key):
    """Busca a configuração para um projeto específico."""
    if not project_key: return None
    collection = get_project_configs_collection()
    return collection.find_one({'_id': project_key})

def save_project_config(project_key, config_data):
    """Guarda a configuração para um projeto específico."""
    collection = get_project_configs_collection()
    collection.update_one(
        {'_id': project_key},
        {'$set': config_data},
        upsert=True
    )
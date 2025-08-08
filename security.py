# security.py

import streamlit as st
from pymongo import MongoClient
from cryptography.fernet import Fernet
from passlib.context import CryptContext
from bson.objectid import ObjectId
from config import *
import string
import secrets
import random
import string

# --- Configuração de Hashing de Senha ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
cipher_suite = Fernet(st.secrets["SECRET_KEY"].encode())

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

# --- Funções de Criptografia de Token ---
@st.cache_resource
def get_cipher():
    """Obtém a instância do cifrador a partir dos secrets."""
    key = st.secrets["ENCRYPTION_KEY"]
    return Fernet(key.encode())

def encrypt_token(token):
    return cipher_suite.encrypt(token.encode()).decode()

def decrypt_token(encrypted_token):
    return cipher_suite.decrypt(encrypted_token.encode()).decode()


# --- Funções de Conexão e Acesso às Coleções do MongoDB ---
@st.cache_resource(show_spinner='Carregando os dados')
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
    """
    Busca um utilizador e migra o seu layout de dashboard se estiver no formato antigo.
    Esta é a versão final e corrigida.
    """
    user = get_users_collection().find_one({'email': email})
    
    if user and 'dashboard_layout' in user:
        needs_update = False
        for project_key, layout in user['dashboard_layout'].items():
            # --- CORREÇÃO AQUI ---
            # Verifica se o layout é uma lista (o formato antigo)
            if isinstance(layout, list):
                needs_update = True
                # Converte a lista de gráficos antiga para a nova estrutura com abas
                new_layout_structure = {
                    "active_dashboard_id": "main_dashboard",
                    "dashboards": {
                        "main_dashboard": {
                            "id": "main_dashboard",
                            "name": "Dashboard Principal",
                            "tabs": {"Geral": layout} # A lista antiga vai para a aba "Geral"
                        }
                    }
                }
                user['dashboard_layout'][project_key] = new_layout_structure
        
        if needs_update:
            save_user_dashboard(email, user['dashboard_layout'])
            
    return user

def create_user(email, password):
    """Cria um novo utilizador, garantindo que a senha seja hashed."""
    hashed_password = get_password_hash(password)
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
    """Busca o layout de um utilizador para um projeto específico."""
    user_data = find_user(user_email)
    if user_data:
        all_dashboards = user_data.get('dashboard_layout', {})
        return all_dashboards.get(project_key, [])
    return []

def save_user_dashboard(email, all_dashboard_layouts):
    """Guarda o objeto completo de dashboards (todos os projetos) para um utilizador."""
    get_users_collection().update_one(
        {'email': email},
        {'$set': {'dashboard_layout': all_dashboard_layouts}}
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

@st.cache_resource (show_spinner="Carregando dados")
def get_global_configs():
    """Busca as configs globais ou cria com valores padrão se não existirem."""
    collection = get_app_configs_collection()
    configs = collection.find_one({'_id': 'global_settings'})
    
    if configs is None:
        configs = {
            '_id': 'global_settings',
            'available_standard_fields': AVAILABLE_STANDARD_FIELDS,
            'status_mapping': { 
                'initial': DEFAULT_INITIAL_STATES, 
                'done': DEFAULT_DONE_STATES,
                'ignored': ['cancelado', 'cancelled'] # NOVO PADRÃO
            },
            'custom_fields': [], 'sprint_goal_threshold': 90
        }
        collection.insert_one(configs)
        return configs
    
    # Garante que a chave exista para configurações antigas
    if 'status_mapping' in configs and 'ignored' not in configs['status_mapping']:
        configs['status_mapping']['ignored'] = ['cancelado', 'cancelled']
        save_global_configs(configs)

    return configs

def save_global_configs(new_configs):
    get_app_configs_collection().update_one({'_id': 'global_settings'}, {'$set': new_configs}, upsert=True)
    
def save_last_project(email, project_key):
    """Guarda a chave do último projeto selecionado pelo utilizador na base de dados."""
    get_users_collection().update_one(
        {'email': email},
        {'$set': {'last_project_key': project_key}}
    )

def save_user_standard_fields(email, standard_fields_list):
    """Guarda a lista de campos padrão selecionados por um utilizador."""
    get_users_collection().update_one(
        {'email': email},
        {'$set': {'standard_fields': standard_fields_list}}
    )

def save_user_custom_fields(email, custom_fields_list):
    """Guarda a lista de campos personalizados selecionados por um utilizador."""
    get_users_collection().update_one(
        {'email': email},
        {'$set': {'enabled_custom_fields': custom_fields_list}}
    )

def save_dashboard_column_preference(project_key, num_columns):
    """Guarda a preferência de número de colunas do dashboard para um projeto."""
    if not project_key:
        return
    # Padrão "Ler-Modificar-Escrever" para garantir a integridade dos dados
    project_config = get_project_config(project_key) or {}
    project_config['dashboard_columns'] = num_columns
    save_project_config(project_key, project_config)

def save_last_active_connection(user_email, connection_id):
    """Guarda o ID da última conexão Jira ativada pelo utilizador."""
    # Garante que o ID seja um ObjectId válido antes de guardar
    get_users_collection().update_one(
        {'email': user_email},
        {'$set': {'last_active_connection_id': ObjectId(connection_id)}}
    )

def get_connection_by_id(connection_id):
    """Busca os detalhes de uma conexão específica pelo seu ID."""
    # Garante que estamos a procurar por um ObjectId
    return get_connections_collection().find_one({"_id": ObjectId(connection_id)})

def delete_user(email):
    """Remove um utilizador e todas as suas configurações associadas."""
    if find_user(email):
        get_users_collection().delete_one({'email': email})
        get_connections_collection().delete_many({'user_email': email})
        get_dashboards_collection().delete_many({'user_email': email})
        return True
    return False

def generate_temporary_password(length=12):
    """Gera uma senha aleatória e segura."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    password = ''.join(secrets.choice(alphabet) for i in range(length))
    return password

def update_user_password(email, new_hashed_password):
    get_users_collection().update_one({'email': email}, {'$set': {'hashed_password': new_hashed_password}})


def save_user_tabs(email, tabs_list):
    """Guarda a lista de abas personalizadas de um utilizador."""
    get_users_collection().update_one(
        {'email': email},
        {'$set': {'user_defined_tabs': tabs_list}}
    )

def save_user_gemini_key(email, encrypted_gemini_key):
    """Guarda a chave de API do Gemini encriptada para um utilizador específico."""
    get_users_collection().update_one(
        {'email': email},
        {'$set': {'encrypted_gemini_key': encrypted_gemini_key}}
    )

def save_user_openai_key(email, encrypted_openai_key):
    """Guarda a chave de API da OpenAI encriptada para um utilizador."""
    get_users_collection().update_one(
        {'email': email},
        {'$set': {'encrypted_openai_key': encrypted_openai_key}}
    )

def save_user_ai_provider_preference(email, provider_name):
    """Guarda o provedor de IA preferido de um utilizador (Gemini ou OpenAI)."""
    get_users_collection().update_one(
        {'email': email},
        {'$set': {'ai_provider_preference': provider_name}}
    )

def save_user_ai_model_preference(email, model_name):
    """Guarda o modelo de IA preferido de um utilizador."""
    get_users_collection().update_one(
        {'email': email},
        {'$set': {'ai_model_preference': model_name}}
    )

def remove_user_gemini_key(email):
    """Remove o campo da chave de API do Gemini do documento de um utilizador."""
    get_users_collection().update_one(
        {'email': email},
        {'$unset': {'encrypted_gemini_key': ""}}
    )

def remove_user_openai_key(email):
    """Remove o campo da chave de API da OpenAI do documento de um utilizador."""
    get_users_collection().update_one(
        {'email': email},
        {'$unset': {'encrypted_openai_key': ""}}
    )

def reset_user_password_with_temporary(email):
    """
    Gera uma senha temporária, atualiza-a na base de dados (hashed)
    e retorna a senha em texto plano para ser enviada por e-mail.
    """
    # Gera uma senha aleatória de 10 caracteres
    temp_password = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
    
    # Guarda a versão hashed da nova senha
    new_hashed_password = get_password_hash(temp_password)
    update_user_password(email, new_hashed_password)
    
    # Retorna a senha em texto plano para o envio do e-mail
    return temp_password

def get_all_users(exclude_email=None):
    """Retorna uma lista de todos os e-mails de utilizadores, opcionalmente excluindo um."""
    query = {}
    if exclude_email:
        query = {'email': {'$ne': exclude_email}}
    users = get_users_collection().find(query, {'email': 1})
    return [user['email'] for user in users]

def share_specific_dashboard(source_email, target_emails, project_key, dashboard_id):
    """Copia um layout de dashboard específico de um utilizador para outros."""
    users_collection = get_users_collection()
    
    # 1. Busca o layout do utilizador de origem
    source_user = find_user(source_email)
    source_layout = source_user.get('dashboard_layout', {}).get(project_key, {})
    dashboard_to_share = source_layout.get('dashboards', {}).get(dashboard_id)

    if not dashboard_to_share:
        return False, "Dashboard de origem não encontrado."
        
    # 2. Atualiza o layout para todos os utilizadores de destino
    for target_email in target_emails:
        # Usa a notação de ponto para atualizar/criar o dashboard específico
        users_collection.update_one(
            {'email': target_email},
            {'$set': {f'dashboard_layout.{project_key}.dashboards.{dashboard_id}': dashboard_to_share}}
        )
    
    return True, "Dashboard partilhado com sucesso!"
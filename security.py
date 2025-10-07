# security.py (Versão Completa e Corrigida para o Erro Bcrypt)

import streamlit as st
import pandas as pd
from pymongo import MongoClient
from cryptography.fernet import Fernet
from passlib.context import CryptContext
from bson.objectid import ObjectId
from config import *
import string
import secrets
import random
import os
import json
from cryptography.fernet import Fernet, InvalidToken
import smtplib
import sendgrid
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
from datetime import datetime, timedelta
import bcrypt
import secrets
from datetime import datetime, timedelta

# --- CONSTANTES PADRÃO ---
AVAILABLE_STANDARD_FIELDS = {
    'Tipo de Issue': {'id': 'issuetype', 'type': 'Texto'},
    'Responsável': {'id': 'assignee', 'type': 'Texto'},
    'Status': {'id': 'status', 'type': 'Texto'},
    'Prioridade': {'id': 'priority', 'type': 'Texto'}
}
DEFAULT_INITIAL_STATES = ['a fazer', 'to do', 'backlog']
DEFAULT_DONE_STATES = ['concluído', 'done', 'resolvido', 'closed']
DEFAULT_COLORS = {
    'status_colors': {'A Fazer': '#808080', 'Em Andamento': '#007bff', 'Concluído': '#28a745'},
    'type_colors': {'Bug': '#d73a49', 'Melhoria': '#28a745', 'Tarefa': '#007bff'}
}
DEFAULT_PLAYBOOKS = {
    "Geral (Manifesto)": "### Nosso Manifesto de Produto\nEste playbook é o guia oficial...",
    "Discovery": "### O Processo de Discovery\nFazer um bom Product Discovery é a etapa mais crucial..."
}

def check_session_timeout():
    """Verifica se a sessão expirou por inatividade."""
    if 'last_activity_time' in st.session_state:

        timeout_duration = timedelta(minutes=SESSION_TIMEOUT_MINUTES)

        if datetime.now() - st.session_state.last_activity_time > timeout_duration:
            for key in list(st.session_state.keys()):
                if key != 'remember_email':
                    del st.session_state[key]
            return True
    st.session_state['last_activity_time'] = datetime.now()
    return False

def load_config(file_path, default_value):
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            try: return json.load(f)
            except (json.JSONDecodeError, UnicodeDecodeError): return default_value
    return default_value

def save_config(data, file_path):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

# --- Configuração de Hashing e Criptografia ---
# Utiliza as chaves definidas nos seus secrets do Streamlit
cipher_suite = Fernet(st.secrets["SECRET_KEY"].encode())

def verify_password(plain_password, hashed_password):
    """Verifica uma senha usando bcrypt."""
    password_bytes = plain_password.encode('utf-8')
    hashed_password_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hashed_password_bytes)

def get_password_hash(password):
    """Cria um hash de uma senha usando bcrypt."""
    password_bytes = password.encode('utf-8')
    truncated_bytes = password_bytes[:72]
    salt = bcrypt.gensalt()
    hashed_bytes = bcrypt.hashpw(truncated_bytes, salt)
    return hashed_bytes.decode('utf-8')

def encrypt_token(token):
    """Encripta um token/senha de API."""
    return cipher_suite.encrypt(token.encode()).decode()

def decrypt_token(encrypted_token):
    """Desencripta um token/senha de API."""
    if not encrypted_token:
        return ""
    return cipher_suite.decrypt(encrypted_token.encode()).decode()

# --- Funções de Conexão e Acesso às Coleções do MongoDB ---
@st.cache_resource(show_spinner='Carregando os dados')
def get_db_client():
    return MongoClient(st.secrets["MONGO_CONNECTION_STRING"])

def get_db():
    return get_db_client().get_database("dashboard_metrics")

def get_users_collection():
    return get_db().get_collection("users")

def get_connections_collection():
    return get_db().get_collection("jira_connections")

def get_dashboards_collection():
    return get_db().get_collection("user_dashboards")

def get_app_configs_collection():
    return get_db().get_collection("app_configs")

def get_project_configs_collection():
    return get_db().get_collection("project_configs")

def get_tokens_collection():
    """Retorna a coleção para os tokens de avaliação."""
    return get_db().get_collection("assessment_tokens")


# --- Funções de Gestão de Utilizadores (Preservadas) ---
def find_user(email):
    # (Sua função find_user original, com a lógica de migração, permanece aqui)
    user = get_users_collection().find_one({'email': email})
    if user and 'dashboard_layout' in user:
        needs_update = False
        for project_key, layout in user['dashboard_layout'].items():
            if isinstance(layout, list):
                needs_update = True
                new_layout_structure = {
                    "active_dashboard_id": "main_dashboard",
                    "dashboards": {
                        "main_dashboard": {
                            "id": "main_dashboard",
                            "name": "Dashboard Principal",
                            "tabs": {"Geral": layout}
                        }
                    }
                }
                user['dashboard_layout'][project_key] = new_layout_structure
        if needs_update:
            save_user_dashboard(email, user['dashboard_layout'])
    return user

def create_user(email, password):
    hashed_password = get_password_hash(password)
    get_users_collection().insert_one({'email': email, 'hashed_password': hashed_password})

def update_user_configs(email, updates_dict):
    """Atualiza um ou mais campos de configuração para um utilizador específico."""
    get_users_collection().update_one(
        {'email': email},
        {'$set': updates_dict},
        upsert=True
    )

# --- Funções de Gestão de Conexões Jira ---
def add_jira_connection(user_email, conn_name, url, api_email, encrypted_token):
    get_connections_collection().insert_one({
        "user_email": user_email, "connection_name": conn_name,
        "jira_url": url, "jira_email": api_email,
        "encrypted_token": encrypted_token
    })

def get_user_connections(user_email):
    return list(get_connections_collection().find({"user_email": user_email}))

def delete_jira_connection(connection_id):
    get_connections_collection().delete_one({"_id": ObjectId(connection_id)})

# --- Funções de Gestão de Dashboards ---
def get_user_dashboard(user_email, project_key):
    user_data = find_user(user_email)
    if user_data:
        all_dashboards = user_data.get('dashboard_layout', {})
        return all_dashboards.get(project_key, [])
    return []

def save_user_dashboard(email, all_dashboard_layouts):
    get_users_collection().update_one(
        {'email': email},
        {'$set': {'dashboard_layout': all_dashboard_layouts}}
    )

# --- Funções de Gestão de Configurações ---
@st.cache_data
def get_project_config(project_key):
    return get_project_configs_collection().find_one({'_id': project_key})

def save_project_config(project_key, config_data):
    if '_id' in config_data: del config_data['_id']
    get_project_configs_collection().update_one({'_id': project_key}, {'$set': config_data}, upsert=True)
    get_project_config.clear()

def save_last_project(email, project_key):
    get_users_collection().update_one(
        {'email': email},
        {'$set': {'last_project_key': project_key}}
    )

@st.cache_data
def get_global_configs():
    """Obtém as configurações globais, com lógica de fallback e migração."""
    collection = get_app_configs_collection()
    configs = collection.find_one({'_id': 'global_settings'})
    
    if configs is None:
        configs = {
            '_id': 'global_settings',
            'playbooks': DEFAULT_PLAYBOOKS,
            'admin_emails': [],
        }
        collection.insert_one(configs)
    
    if 'playbooks' not in configs:
        configs['playbooks'] = DEFAULT_PLAYBOOKS

    return configs

def save_global_configs(config_data):
    """Guarda ou atualiza as configurações globais e limpa o cache da função de leitura."""
    get_app_configs_collection().update_one(
        {"_id": "global_settings"}, # Usa o mesmo ID da função de leitura
        {"$set": config_data},
        upsert=True
    )
    get_global_configs.clear()
    
    if 'global_configs' in st.session_state:
        st.session_state['global_configs'] = config_data

# --- Funções de Gestão de Dados do Product Hub (Simplificadas) ---
def get_user_product_hub_data(user_email):
    user = find_user(user_email)
    if not user: return {}
    hub_data = user.get('product_hub_data', {})
    if 'membros' in hub_data and isinstance(hub_data['membros'], list):
        hub_data['membros'] = pd.DataFrame(hub_data['membros'])
    else:
        hub_data['membros'] = pd.DataFrame(columns=["Nome", "Papel"])
    return hub_data

def save_user_product_hub_data(user_email, hub_data):
    data_to_save = hub_data.copy()
    if 'membros' in data_to_save and isinstance(data_to_save['membros'], pd.DataFrame):
        data_to_save['membros'] = data_to_save['membros'].to_dict('records')
    get_users_collection().update_one(
        {'email': user_email},
        {'$set': {'product_hub_data': data_to_save}},
        upsert=True
    )

def save_user_standard_fields(email, standard_fields_list):
    get_users_collection().update_one(
        {'email': email},
        {'$set': {'standard_fields': standard_fields_list}}
    )

def save_user_custom_fields(email, custom_fields_list):
    get_users_collection().update_one(
        {'email': email},
        {'$set': {'enabled_custom_fields': custom_fields_list}}
    )

def save_dashboard_column_preference(project_key, num_columns):
    if not project_key:
        return
    project_config = get_project_config(project_key) or {}
    project_config['dashboard_columns'] = num_columns
    save_project_config(project_key, project_config)

def save_last_active_connection(user_email, connection_id):
    get_users_collection().update_one(
        {'email': user_email},
        {'$set': {'last_active_connection_id': ObjectId(connection_id)}}
    )

def get_connection_by_id(connection_id):
    return get_connections_collection().find_one({"_id": ObjectId(connection_id)})

def delete_user(email):
    if find_user(email):
        get_users_collection().delete_one({'email': email})
        get_connections_collection().delete_many({'user_email': email})
        get_dashboards_collection().delete_many({'user_email': email})
        return True
    return False

def generate_temporary_password(length=12):
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    password = ''.join(secrets.choice(alphabet) for i in range(length))
    return password

def update_user_password(email, new_hashed_password):
    get_users_collection().update_one({'email': email}, {'$set': {'hashed_password': new_hashed_password}})


def save_user_tabs(email, tabs_list):
    get_users_collection().update_one(
        {'email': email},
        {'$set': {'user_defined_tabs': tabs_list}}
    )

def save_user_gemini_key(email, encrypted_gemini_key):
    get_users_collection().update_one(
        {'email': email},
        {'$set': {'encrypted_gemini_key': encrypted_gemini_key}}
    )

def save_user_openai_key(email, encrypted_openai_key):
    get_users_collection().update_one(
        {'email': email},
        {'$set': {'encrypted_openai_key': encrypted_openai_key}}
    )

def save_user_ai_provider_preference(email, provider_name):
    get_users_collection().update_one(
        {'email': email},
        {'$set': {'ai_provider_preference': provider_name}}
    )

def save_user_ai_model_preference(email, model_name):
    get_users_collection().update_one(
        {'email': email},
        {'$set': {'ai_model_preference': model_name}}
    )

def remove_user_gemini_key(email):
    get_users_collection().update_one(
        {'email': email},
        {'$unset': {'encrypted_gemini_key': ""}}
    )

def remove_user_openai_key(email):
    get_users_collection().update_one(
        {'email': email},
        {'$unset': {'encrypted_openai_key': ""}}
    )

def reset_user_password_with_temporary(email):
    temp_password = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
    new_hashed_password = get_password_hash(temp_password)
    update_user_password(email, new_hashed_password)
    return temp_password

def get_all_users(exclude_email=None):
    query = {}
    if exclude_email:
        query = {'email': {'$ne': exclude_email}}
    users = get_users_collection().find(query, {'email': 1})
    return [user['email'] for user in users]

def share_specific_dashboard(source_email, target_emails, project_key, dashboard_id):
    users_collection = get_users_collection()
    source_user = find_user(source_email)
    source_layout = source_user.get('dashboard_layout', {}).get(project_key, {})
    dashboard_to_share = source_layout.get('dashboards', {}).get(dashboard_id)

    if not dashboard_to_share:
        return False, "Dashboard de origem não encontrado."
        
    for target_email in target_emails:
        users_collection.update_one(
            {'email': target_email},
            {'$set': {f'dashboard_layout.{project_key}.dashboards.{dashboard_id}': dashboard_to_share}}
        )
    
    return True, "Dashboard partilhado com sucesso!"

def get_app_configs():
    configs_collection = get_app_configs_collection()
    configs = configs_collection.find_one()
    
    if configs is None:
        default_configs = {
            'initial_states': DEFAULT_INITIAL_STATES,
            'done_states': DEFAULT_DONE_STATES,
            'status_colors': DEFAULT_COLORS['status_colors'],
            'type_colors': DEFAULT_COLORS['type_colors']
        }
        configs_collection.insert_one(default_configs)
        return default_configs
        
    return configs

def save_app_configs(configs_data):
    configs_collection = get_app_configs_collection()
    configs_collection.update_one({}, {'$set': configs_data}, upsert=True)

# ===== NOVAS FUNÇÕES PARA GESTÃO DE CREDENCIAIS DE E-MAIL =====
def get_smtp_configs():
    user_email = st.session_state.get('email')
    if not user_email: return {}
    
    user_data = get_users_collection().find_one({'email': user_email})
    encrypted_configs = user_data.get('smtp_configs', {})
    decrypted_configs = encrypted_configs.copy()

    if 'app_password' in encrypted_configs and encrypted_configs['app_password']:
        try:
            decrypted_configs['app_password'] = decrypt_token(encrypted_configs['app_password'])
        except InvalidToken:
            decrypted_configs['app_password'] = ""
    
    if 'api_key' in encrypted_configs and encrypted_configs['api_key']:
        try:
            decrypted_configs['api_key'] = decrypt_token(encrypted_configs['api_key'])
        except InvalidToken:
            decrypted_configs['api_key'] = ""
            
    return decrypted_configs

def save_smtp_configs(smtp_configs):
    user_email = st.session_state.get('email')
    if not user_email: return False

    if 'app_password' in smtp_configs and smtp_configs['app_password']:
        smtp_configs['app_password'] = encrypt_token(smtp_configs['app_password'])
    if 'api_key' in smtp_configs and smtp_configs['api_key']:
        smtp_configs['api_key'] = encrypt_token(smtp_configs['api_key'])

    get_users_collection().update_one(
        {'email': user_email},
        {'$set': {'smtp_configs': smtp_configs}},
        upsert=True
    )
    return True

def decrypt_smtp_password(encrypted_password):
    try:
        return decrypt_token(encrypted_password)
    except Exception:
        return None
    
def save_user_figma_token(user_email, figma_token):
    if not figma_token:
        get_users_collection().update_one(
            {'email': user_email},
            {'$unset': {'figma_token': ""}}
        )
        return
        
    encrypted_token = encrypt_token(figma_token)
    get_users_collection().update_one(
        {'email': user_email},
        {'$set': {'figma_token': encrypted_token}},
        upsert=True
    )

def get_user_figma_token(user_email):
    user = find_user(user_email)
    encrypted_token = user.get('figma_token')
    
    if not encrypted_token:
        return None
        
    try:
        return decrypt_token(encrypted_token)
    except InvalidToken:
        st.error("O seu token do Figma parece estar corrompido. Por favor, guarde-o novamente.")
        return None
    
def get_user_product_hub_data(user_email):
    user = find_user(user_email)
    hub_data = user.get('product_hub_data', {})
    
    if 'membros' in hub_data and isinstance(hub_data['membros'], list):
        hub_data['membros'] = pd.DataFrame(hub_data['membros'])
    else:
        hub_data['membros'] = pd.DataFrame(columns=["Nome", "Papel"])
        
    return hub_data

def save_user_product_hub_data(user_email, hub_data):
    data_to_save = hub_data.copy()
    
    if 'membros' in data_to_save and isinstance(data_to_save['membros'], pd.DataFrame):
        data_to_save['membros'] = data_to_save['membros'].to_dict('records')
        
    get_users_collection().update_one(
        {'email': user_email},
        {'$set': {'product_hub_data': data_to_save}},
        upsert=True
    )

def get_global_smtp_configs():
    try:
        configs = get_global_configs()
        return configs.get("smtp_configs")
    except Exception as e:
        print(f"Erro ao buscar configurações globais de SMTP: {e}")
        return None
    
def save_global_smtp_configs(smtp_data):
    configs = get_global_configs()
    configs['smtp_configs'] = smtp_data
    save_global_configs(configs)
    get_global_configs.clear()

def get_global_smtp_configs():
    configs = get_global_configs()
    return configs.get("smtp_configs")

def validate_smtp_connection(provider, from_email, credential):
    if provider == 'SendGrid':
        try:
            sg = sendgrid.SendGridAPIClient(credential)
            response = sg.client.user.email.get()
            if response.status_code == 200:
                return True, "Credenciais do SendGrid validadas com sucesso!"
            else:
                return False, f"Falha na validação do SendGrid. (Status: {response.status_code})"
        except Exception as e:
            return False, f"Erro ao conectar ao SendGrid: A chave de API parece ser inválida. ({e})"

    elif provider == 'Gmail (SMTP)':
        try:
            smtp_server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
            smtp_server.login(from_email, credential)
            smtp_server.quit()
            return True, "Credenciais do Gmail validadas com sucesso!"
        except smtplib.SMTPAuthenticationError:
            return False, "Falha na autenticação com o Gmail. Verifique o e-mail e a senha de aplicação."
        except Exception as e:
            return False, f"Erro ao conectar ao SMTP do Gmail: {e}"
            
    return False, "Provedor desconhecido."

def generate_assessment_token(hub_owner_email, evaluated_email, valid_for_hours=72):
    token = secrets.token_urlsafe(32)
    expiration_date = datetime.utcnow() + timedelta(hours=valid_for_hours)
    get_tokens_collection().insert_one({
        "token": token,
        "hub_owner_email": hub_owner_email,
        "evaluated_email": evaluated_email,
        "expires_at": expiration_date,
        "used": False
    })
    return token

def validate_assessment_token(token):
    """Verifica se um token é válido, não foi usado e não expirou."""
    token_data = get_tokens_collection().find_one({"token": token})
    
    if not token_data or token_data.get("used") or token_data["expires_at"] < datetime.utcnow():
        return None
        
    return {
        "hub_owner_email": token_data["hub_owner_email"],
        "evaluated_email": token_data["evaluated_email"]
    }

def save_assessment_response(hub_owner_email, evaluated_email, assessment_data):
    """
    Guarda as respostas da avaliação (incluindo metadados) no registo do dono do hub.
    'assessment_data' é agora um dicionário que contém o nome do respondente e os dados da avaliação.
    """
    # Acessa a coleção de utilizadores
    users_collection = get_users_collection()
    
    # Procura pelo dono do hub para garantir que ele existe
    hub_owner = users_collection.find_one({"email": hub_owner_email})
    if not hub_owner:
        return False

    # O caminho para a avaliação na base de dados
    path_to_assessment = f"product_hub_data.avaliacoes.{evaluated_email}"

    # Executa a atualização na base de dados
    result = users_collection.update_one(
        {"email": hub_owner_email},
        {"$set": {path_to_assessment: assessment_data}}
    )
    
    # Retorna True se a operação modificou algum documento
    return result.modified_count > 0

def mark_token_as_used(token):
    """Marca um token como utilizado após a submissão da avaliação."""
    get_tokens_collection().update_one({"token": token}, {"$set": {"used": True}})
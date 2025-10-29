# security.py

import streamlit as st
import pandas as pd
from pymongo import MongoClient
from cryptography.fernet import Fernet, InvalidToken
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
import mailersend
import sib_api_v3_sdk
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
from datetime import datetime, timedelta
import bcrypt
import secrets
from datetime import datetime, timedelta
from sendgrid.helpers.mail import Mail, To, From, Content
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import MASTER_USERS
GLOBAL_CONFIG_PATH = Path("global_app_configs.json")
import traceback

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
print("-" * 20)
print("INICIANDO LEITURA DE SEGREDOS em security.py")
secret_key_value = None
cipher_suite = None

try:
    # Tenta ler a chave diretamente
    secret_key_value = st.secrets.get("app_settings", {}).get("SECRET_KEY")
    print(f"SECRET_KEY lida diretamente: {'SIM' if secret_key_value else 'NÃO'}")

    # Tenta inicializar o Fernet
    if secret_key_value:
        try:
            cipher_suite = Fernet(secret_key_value.encode())
            print("Cipher suite inicializado COM SUCESSO.")
        except Exception as e:
            st.error(f"Erro ao inicializar o cifrador com SECRET_KEY: {e}")
            print(f"ERRO ao criar Fernet: {traceback.format_exc()}") # Imprime traceback completo
            cipher_suite = None # Garante que está None em caso de falha
    else:
        # Mensagem se a chave não foi encontrada diretamente
        st.error("Chave de criptografia (SECRET_KEY) não encontrada diretamente em st.secrets.")
        print("ERRO: SECRET_KEY não encontrada diretamente.")

except KeyError:
    # Captura o erro específico se a chave não existir no nível raiz
    st.error("Falha ao ler SECRET_KEY: Chave não encontrada no nível raiz de secrets.toml.")
    print("ERRO: KeyError ao aceder st.secrets['SECRET_KEY']. Verifique secrets.toml.")
    cipher_suite = None # Garante que está None
except Exception as e:
    # Captura outros erros durante a leitura dos segredos
    st.error(f"Erro inesperado ao ler SECRET_KEY: {e}")
    print(f"ERRO inesperado ao ler st.secrets['SECRET_KEY']: {traceback.format_exc()}")
    cipher_suite = None # Garante que está None

print(f"Status final do cipher_suite: {'Inicializado' if cipher_suite else 'NÃO Inicializado'}")
print("-" * 20)

# As funções encrypt_token e decrypt_token DEVEM incluir a verificação 'if not cipher_suite:'
def encrypt_token(token):
    if not cipher_suite:
        # A mensagem de erro já deve ter sido mostrada na inicialização
        print("Erro: Tentativa de encriptar sem cipher_suite inicializado.")
        return None
    if not token:
        return None
    try:
        return cipher_suite.encrypt(token.encode()).decode()
    except Exception as e:
        st.error(f"Erro ao encriptar token: {e}")
        return None

def decrypt_token(encrypted_token):
    """Desencripta um token/senha de API."""
    if not cipher_suite:
        # A mensagem de erro na interface virá da inicialização falhada
        print("Erro: Tentativa de decriptar sem cipher_suite inicializado.")
        st.error("Criptografia não inicializada. Verifique a configuração da SECRET_KEY.") # Mensagem mais direta
        return None
    if not encrypted_token:
        return None
    try:
        encrypted_bytes = encrypted_token.encode() if isinstance(encrypted_token, str) else encrypted_token
        decrypted_bytes = cipher_suite.decrypt(encrypted_bytes)
        return decrypted_bytes.decode()
    except InvalidToken:
        st.warning("Token inválido ou chave de criptografia incorreta ao tentar decriptar.")
        print("AVISO: InvalidToken durante a decriptografia.")
        return None
    except Exception as e:
        st.error(f"Erro inesperado ao decriptar token: {e}")
        print(f"ERRO: Falha inesperada ao decriptar: {e}")
        return None

def verify_password(plain_password, hashed_password):
    """Verifica uma senha usando bcrypt."""
    password_bytes = plain_password.encode('utf-8')
    truncated_bytes = password_bytes[:72] 
    hashed_password_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(truncated_bytes, hashed_password_bytes)

def get_password_hash(password):
    """Cria um hash de uma senha usando bcrypt."""
    password_bytes = password.encode('utf-8')
    truncated_bytes = password_bytes[:72]
    salt = bcrypt.gensalt()
    hashed_bytes = bcrypt.hashpw(truncated_bytes, salt)
    return hashed_bytes.decode('utf-8')

# --- Funções de Conexão e Acesso às Coleções do MongoDB ---
@st.cache_resource(show_spinner='Carregando os dados')
def get_db_client():
    return MongoClient(MONGO_URI)

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

def delete_jira_connection(connection_id):
    """Apaga uma conexão pelo seu ID de string (UUID)."""
    get_connections_collection().delete_one({"id": connection_id})

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

GLOBAL_CONFIG_PATH = Path("global_app_configs.json")

@st.cache_data
def get_global_configs():
    """
    Lê o ficheiro de configuração global...
    """
    print(f"--- DEBUG: Tentando ler o ficheiro em: {GLOBAL_CONFIG_PATH.resolve()} ---") # ADICIONE ESTE PRINT

    configs = {}
    if GLOBAL_CONFIG_PATH.is_file():
        try:
            with open(GLOBAL_CONFIG_PATH, 'r', encoding='utf-8') as f:
                configs = json.load(f)
                print(f"--- DEBUG: Ficheiro lido com sucesso. Conteúdo parcial: {str(configs)[:200]} ...") # ADICIONE ESTE PRINT
        except (json.JSONDecodeError, IOError) as e:
            print(f"Erro ao ler o ficheiro de configuração global: {e}")
            configs = {} # Mantém o fallback
    else:
        print(f"--- DEBUG: Ficheiro NÃO encontrado em {GLOBAL_CONFIG_PATH.resolve()} ---") # ADICIONE ESTE PRINT

    st.session_state['global_configs'] = configs
    return configs

def save_global_configs(configs):
    """
    Salva o dicionário de configurações globais no ficheiro JSON.
    """
    try:
        with open(GLOBAL_CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(configs, f, indent=4)
        st.session_state['global_configs'] = configs # Atualiza a sessão imediatamente
        return True
    except IOError as e:
        print(f"Erro ao salvar o ficheiro de configuração global: {e}")
        return False
    
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
    """
    Guarda o ID da última conexão ativa do utilizador (como uma string).
    """
    get_users_collection().update_one(
        {'email': user_email},
        {'$set': {'last_active_connection_id': connection_id}}
    )

def get_connection_by_id(connection_id):
    """Procura uma conexão pelo seu ID de string (UUID)."""
    return get_connections_collection().find_one({"id": connection_id})

def deactivate_active_connection(user_email):
    """
    Desativa a conexão Jira ativa para um utilizador, definindo o campo como None.
    """
    get_users_collection().update_one(
        {'email': user_email},
        {'$set': {'last_active_connection_id': None}}
    )

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

# ===== FUNÇÕES PARA GESTÃO DE CREDENCIAIS DE E-MAIL =====
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
    
def get_global_smtp_configs():
    try:
        configs = get_global_configs()
        return configs.get("smtp_settings") # <-- Correção
    except Exception as e:
        print(f"Erro ao buscar configurações globais de SMTP: {e}")
        return None
    
def save_global_smtp_configs(smtp_data):
    configs = get_global_configs()
    configs['smtp_configs'] = smtp_data
    save_global_configs(configs)
    get_global_configs.clear()

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
            
    elif provider == 'Mailersend':
        try:
            from mailersend import Mailersend
            ms = Mailersend(credential) 
            response_dict, status_code = ms.domains.list() 
            
            if 200 <= status_code < 300:
                return True, "Credenciais do Mailersend validadas com sucesso!"
            elif status_code == 401:
                return False, "Falha na autenticação com o Mailersend. A chave de API parece ser inválida."
            else:
                 error_msg = response_dict.get('message', 'Erro desconhecido')
                 return False, f"Erro do Mailersend (Status: {status_code}): {error_msg}"

        except ImportError:
            return False, "A biblioteca 'mailersend' não está instalada. Adicione-a ao requirements.txt."
        except Exception as e:
            return False, f"Erro ao conectar ao Mailersend: {e}"

    # --- ALTERAÇÃO: Adicionar bloco de validação do Brevo ---
    elif provider == 'Brevo':
        try:
            import sib_api_v3_sdk
            from sib_api_v3_sdk.rest import ApiException

            # Configurar a API
            config = sib_api_v3_sdk.Configuration()
            config.api_key['api-key'] = credential
            
            # Tentar uma chamada de API leve (get_account)
            api_client = sib_api_v3_sdk.ApiClient(config)
            account_api = sib_api_v3_sdk.AccountApi(api_client)
            
            # Se esta chamada for bem-sucedida, a chave é válida
            account_api.get_account() 
            
            return True, "Credenciais do Brevo validadas com sucesso!"

        except ImportError:
             return False, "A biblioteca 'sib-api-v3-sdk' não está instalada. Adicione-a ao requirements.txt."
        except ApiException as e:
            if e.status == 401:
                return False, "Falha na autenticação com o Brevo. A chave de API parece ser inválida."
            else:
                return False, f"Erro ao conectar ao Brevo (API Exception): {e.reason}"
        except Exception as e:
            return False, f"Erro inesperado ao conectar ao Brevo: {e}"

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

def verify_assessment_token(token):
    token_data = get_tokens_collection().find_one({"token": token})
    if not token_data or token_data.get("used") or token_data["expires_at"] < datetime.utcnow():
        return None
    return {"hub_owner_email": token_data["hub_owner_email"], "evaluated_email": token_data["evaluated_email"]}

def mark_token_as_used(token):
    get_tokens_collection().update_one({"token": token}, {"$set": {"used": True}})

def send_assessment_email(recipient_email, recipient_name, sender_name, assessment_url, smtp_configs):
    provider = smtp_configs.get('provider')
    from_email = smtp_configs.get('from_email')
    if not from_email:
        st.error("O 'E-mail de Origem' não está configurado.")
        return False, "E-mail de origem não configurado."

    html_body = f"""
    <html>
    <body>
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 20px; border: 1px solid #ddd; border-radius: 10px;">
            <h2 style="color: #262730; text-align: center;">🚀 Avaliação de Competências</h2>
            <p>Olá, {recipient_name},</p>
            <p><strong>{sender_name}</strong> convidou você para preencher a sua autoavaliação de competências.</p>
            <p>A sua perspetiva é muito importante para o nosso crescimento conjunto.</p>
            <p style="text-align: center;">
                <a href="{assessment_url}" style="background-color: #007bff; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; display: inline-block;">Iniciar Autoavaliação</a>
            </p>
            <p>Se o botão não funcionar, copie e cole o seguinte link no seu navegador:</p>
            <p><a href="{assessment_url}">{assessment_url}</a></p>
            <p>Obrigado pela sua colaboração!</p>
        </div>
    </body>
    </html>
    """
    subject = f"🚀 Convite para Avaliação de Competências de {sender_name}"

    try:
        if provider == 'SendGrid':
            # A função get_smtp_configs() já desencripta, então usamos a chave diretamente
            api_key = smtp_configs.get('api_key', '')
            if not api_key:
                return False, "API Key do SendGrid não encontrada."
            sg = sendgrid.SendGridAPIClient(api_key=api_key)
            from_sg = From(email=from_email, name=sender_name)
            to_sg = To(email=recipient_email)
            message = Mail(from_email=from_sg, to_emails=to_sg, subject=subject, html_content=html_body)
            response = sg.client.mail.send.post(request_body=message.get())
            if 200 <= response.status_code < 300:
                return True, "E-mail enviado com sucesso via SendGrid."
            else:
                return False, f"Falha no envio pelo SendGrid (Status: {response.status_code})."
        elif provider == 'Gmail (SMTP)':
            # A função get_smtp_configs() já desencripta, então usamos a chave diretamente
            app_password = smtp_configs.get('app_password', '')
            if not app_password:
                return False, "Senha de aplicação do Gmail não encontrada."
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{sender_name} <{from_email}>"
            msg['To'] = recipient_email
            msg.attach(MIMEText(html_body, 'html'))
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(from_email, app_password)
                server.sendmail(from_email, recipient_email, msg.as_string())
            return True, "E-mail enviado com sucesso via Gmail."
        else:
            return False, f"Provedor de e-mail desconhecido: '{provider}'"
    except Exception as e:
        return False, f"Ocorreu um erro ao enviar o e-mail: {e}"
    
def save_user_connections(email, connections):
    """
    Atualiza o campo 'jira_connections' para um utilizador específico no MongoDB.
    """
    get_users_collection().update_one(
        {'email': email},
        {'$set': {'jira_connections': connections}}
    )

def update_user_data(email, new_data):
    """Atualiza o documento de um utilizador na coleção."""
    users_collection = get_users_collection()
    # Usa $set para atualizar os campos sem apagar o documento inteiro
    users_collection.update_one({'email': email}, {'$set': new_data})

def is_admin(email):
    # 1. Verifica se o e-mail está na lista de MASTER_USERS do secrets.toml
    if email in MASTER_USERS:
        return True
    
    # 2. Se não for um master, verifica a flag 'is_admin' no banco de dados
    user = find_user(email)
    return user and user.get('is_admin', False)

def set_admin_status(email, is_admin_bool):
    # Esta verificação impede que um admin remova as permissões de um master
    if email in MASTER_USERS:
        st.warning("Não é possível alterar as permissões de um utilizador master.")
        return
    update_user_configs(email, {'is_admin': is_admin_bool})

@st.cache_data(show_spinner=False)
def load_standard_fields_map():
    """
    Carrega o mapa de campos padrão do JSON.
    Usa cache para evitar leituras repetidas do disco.
    """
    try:
        # __file__ aqui aponta para Metrics/security.py
        # O JSON está no mesmo diretório (Metrics/)
        fields_path = Path(__file__).parent / "jira_standard_fields.json"
        with open(fields_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        # Este erro só deve acontecer uma vez se o ficheiro for movido
        st.error("Ficheiro crítico 'jira_standard_fields.json' não encontrado no diretório Metrics/.")
        return {}
    except Exception as e:
        st.error(f"Erro ao carregar 'jira_standard_fields.json': {e}")
        return {}
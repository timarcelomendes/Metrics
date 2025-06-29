# security.py

import streamlit as st
from pymongo import MongoClient
from cryptography.fernet import Fernet
import pandas as pd

# --- Funções de Criptografia ---
def get_cipher():
    """Cria o objeto de cifra usando a chave dos secrets."""
    key = st.secrets["ENCRYPTION_KEY"]
    return Fernet(key.encode())

def encrypt_token(token):
    """Criptografa um token."""
    cipher = get_cipher()
    return cipher.encrypt(token.encode()).decode()

def decrypt_token(encrypted_token):
    """Descriptografa um token."""
    cipher = get_cipher()
    return cipher.decrypt(encrypted_token.encode()).decode()

# --- Funções da Base de Dados ---
@st.cache_resource
def get_db_collection():
    """Conecta-se ao MongoDB e retorna a coleção de credenciais."""
    connection_string = st.secrets["MONGO_CONNECTION_STRING"]
    client = MongoClient(connection_string)
    db = client.get_database("dashboard_metrics") # Nome da base de dados
    return db.get_collection("user_credentials") # Nome da coleção

def save_user_credentials(profile_name, url, email, encrypted_token):
    """Guarda ou atualiza as credenciais de um perfil."""
    collection = get_db_collection()
    collection.update_one(
        {'profile_name': profile_name},
        {'$set': {
            'jira_url': url,
            'jira_email': email,
            'encrypted_token': encrypted_token
        }},
        upsert=True # Cria o documento se ele não existir
    )

def get_user_credentials(profile_name):
    """Busca as credenciais de um perfil."""
    collection = get_db_collection()
    return collection.find_one({'profile_name': profile_name})

def get_all_profiles():
    """Retorna o nome de todos os perfis guardados."""
    collection = get_db_collection()
    profiles = collection.find({}, {'profile_name': 1, '_id': 0})
    return [p['profile_name'] for p in profiles]

def delete_profile(profile_name):
    """Apaga um perfil da base de dados."""
    collection = get_db_collection()
    collection.delete_one({'profile_name': profile_name})
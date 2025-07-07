# security.py

import streamlit as st
from pymongo import MongoClient
from cryptography.fernet import Fernet
from passlib.context import CryptContext

# --- Configuração de Hashing ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

# --- Funções de Criptografia de Token ---
def get_cipher():
    key = st.secrets["ENCRYPTION_KEY"]
    return Fernet(key.encode())

def encrypt_token(token: str):
    return get_cipher().encrypt(token.encode()).decode()

def decrypt_token(encrypted_token: str):
    return get_cipher().decrypt(encrypted_token.encode()).decode()

# --- Funções da Base de Dados ---
@st.cache_resource
def get_users_collection():
    """Conecta-se ao MongoDB e retorna a coleção de utilizadores."""
    connection_string = st.secrets["MONGO_CONNECTION_STRING"]
    client = MongoClient(connection_string)
    db = client.get_database("dashboard_metrics")
    return db.get_collection("users")

def find_user(email):
    """Encontra um utilizador pelo email."""
    collection = get_users_collection()
    return collection.find_one({'email': email})

def create_user(email, hashed_password):
    """Cria um novo utilizador na base de dados."""
    collection = get_users_collection()
    collection.insert_one({'email': email, 'hashed_password': hashed_password})

def save_jira_credentials(email, url, api_email, encrypted_token):
    """Guarda as credenciais do Jira para um utilizador."""
    collection = get_users_collection()
    collection.update_one(
        {'email': email},
        {'$set': {
            'jira_url': url,
            'jira_email': api_email,
            'encrypted_token': encrypted_token
        }},
        upsert=True
    )
# security.py

import streamlit as st
from pymongo import MongoClient
from cryptography.fernet import Fernet

# --- Funções de Criptografia ---
def get_cipher():
    key = st.secrets["ENCRYPTION_KEY"]
    return Fernet(key.encode())

def encrypt_token(token: str):
    return get_cipher().encrypt(token.encode()).decode()

def decrypt_token(encrypted_token: str):
    return get_cipher().decrypt(encrypted_token.encode()).decode()

# --- Funções da Base de Dados ---
@st.cache_resource
def get_db_collection():
    connection_string = st.secrets["MONGO_CONNECTION_STRING"]
    client = MongoClient(connection_string)
    db = client.get_database("dashboard_metrics")
    return db.get_collection("user_credentials")

def save_user_credentials(profile_name, url, email, encrypted_token):
    collection = get_db_collection()
    collection.update_one(
        {'profile_name': profile_name},
        {'$set': {'jira_url': url, 'jira_email': email, 'encrypted_token': encrypted_token}},
        upsert=True
    )

def get_user_credentials(profile_name):
    collection = get_db_collection()
    return collection.find_one({'profile_name': profile_name})

def get_all_profiles():
    collection = get_db_collection()
    profiles = collection.find({}, {'profile_name': 1, '_id': 0})
    return [p['profile_name'] for p in profiles]

def delete_profile(profile_name):
    collection = get_db_collection()
    collection.delete_one({'profile_name': profile_name})
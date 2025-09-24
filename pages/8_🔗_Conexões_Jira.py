# pages/2_🔗_Conexões_Jira.py

import streamlit as st
from security import *
from bson.objectid import ObjectId
from pathlib import Path
import os
from utils import is_valid_url, is_valid_email
from jira_connector import connect_to_jira, get_projects

st.set_page_config(page_title="Conexões Jira", page_icon="🔗", layout="wide")

st.header("🔗 Gerir Conexões Jira", divider='rainbow')

if 'email' not in st.session_state:
    st.warning("⚠️ Por favor, faça login para acessar."); st.page_link("1_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑"); st.stop()

email = st.session_state['email']

# --- Adicionar Nova Conexão ---
with st.expander("➕ Adicionar Nova Conexão ao Jira", expanded=False):
    with st.form("new_connection_form", clear_on_submit=False):
        st.markdown("**Preencha os dados da sua conta Jira:**")
        col1, col2 = st.columns(2)
        
        conn_name = col1.text_input("Nome da Conexão*", placeholder="Ex: Jira da Empresa X")
        jira_url = col2.text_input("URL do Servidor Jira*", placeholder="https://seu-nome.atlassian.net")
        jira_email = col1.text_input("Email da Conta Jira*")
        
        with col2:
            api_token = st.text_input("Token da API Jira*", type="password")
            st.caption("Não sabe como criar um token? [Clique aqui para gerar um novo](https://id.atlassian.com/manage-profile/security/api-tokens)")

        if st.form_submit_button("Adicionar e Testar Conexão", type="primary", use_container_width=True):
            if all([conn_name, jira_url, jira_email, api_token]) and is_valid_url(jira_url) and is_valid_email(jira_email):
                with st.spinner("A guardar a conexão..."):
                    encrypted_token = encrypt_token(api_token)
                    add_jira_connection(email, conn_name, jira_url, jira_email, encrypted_token)
                    st.success(f"Conexão '{conn_name}' adicionada com sucesso!")
                    # Limpa o estado da sessão para forçar a limpeza do formulário APENAS em caso de sucesso
                    for key in list(st.session_state.keys()):
                        if key.startswith("FormSubmitter"): # Limpa o estado do formulário
                            del st.session_state[key]
                    st.rerun()
            else:
                st.error("Por favor, preencha todos os campos corretamente.")

st.divider()

# --- Listar Conexões Existentes ---
st.subheader("Suas Conexões Guardadas")
connections = get_user_connections(email)

if not connections:
    st.info("Nenhuma conexão Jira encontrada. Adicione uma acima para começar.")
else:
    for conn in connections:
        with st.container(border=True):
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                st.markdown(f"**{conn['connection_name']}**")
                st.caption(f"URL: {conn['jira_url']}")
            with col2:
                # Verifica se esta é a conexão atualmente ativa
                is_active = st.session_state.get('active_connection', {}).get('_id') == conn['_id']
                
                # Desabilita o botão se a conexão já estiver ativa
                if st.button("Ativar Conexão", key=f"activate_{conn['_id']}", use_container_width=True, type="primary", disabled=is_active):
                    with st.spinner("A testar e ativar a conexão..."):
                        token = decrypt_token(conn['encrypted_token'])
                        client = connect_to_jira(conn['jira_url'], conn['jira_email'], token)
                        
                        if client:
                            st.session_state.active_connection = conn
                            st.session_state.jira_client = client
                            st.session_state.projects = get_projects(client)
                            
                            # Guarda esta conexão como a última ativa para o utilizador
                            save_last_active_connection(st.session_state['email'], conn['_id'])
                            
                            st.success(f"Conexão '{conn['connection_name']}' ativada com sucesso!")
                            st.rerun()
                        else:
                            st.error("Falha na conexão. Verifique os detalhes e o token de API.")
            
            with col3:
                if st.button("Remover", key=f"delete_{conn['_id']}", use_container_width=True):
                    delete_jira_connection(conn['_id'])
                    if st.session_state.get('active_connection', {}).get('_id') == conn['_id']:
                        for key in ['active_connection', 'jira_client', 'projects', 'project_key', 'project_name', 'dynamic_df']:
                            if key in st.session_state: del st.session_state[key]
                    st.rerun()

# --- Status da Conexão na Sidebar ---
with st.sidebar:
    project_root = Path(__file__).parent.parent
    logo_path = project_root / "images" / "gauge-logo.svg"
    try:
        st.logo(
            logo_path, 
            size="large")
    except FileNotFoundError:
        st.write("Gauge Metrics") 
    
    if st.session_state.get("email"):
        st.markdown(f"🔐 Logado como: **{st.session_state['email']}**")
    else:
        st.info("⚠️ Usuário não conectado!")
        
    if st.button("Logout", use_container_width=True, type='secondary'):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.switch_page("1_🔑_Autenticação.py")

    st.divider()
    
    if 'active_connection' in st.session_state:
        active_conn_name = st.session_state.active_connection['connection_name']
        st.sidebar.success(f"Conexão Ativa: **{active_conn_name}**")
    else:
        st.sidebar.warning("Nenhuma conexão ativa nesta sessão.")
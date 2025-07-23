# pages/2_🔗_Conexões_Jira.py

import streamlit as st
from security import *
from jira_connector import connect_to_jira, get_projects
from bson.objectid import ObjectId
from pathlib import Path
import os

st.set_page_config(page_title="Conexões Jira", page_icon="🔗", layout="wide")

st.header("🔗 Gerir Conexões Jira", divider='rainbow')

if 'email' not in st.session_state:
    st.warning("⚠️ Por favor, faça login para aceder a esta página."); st.page_link("1_🔑_Login.py", label="Ir para Login", icon="🔑"); st.stop()

email = st.session_state['email']

# --- Adicionar Nova Conexão ---
with st.expander("➕ Adicionar Nova Conexão ao Jira"):
    with st.form("new_connection_form", clear_on_submit=True):
        st.markdown("**Preencha os dados da sua conta Jira:**")
        col1, col2 = st.columns(2)
        conn_name = col1.text_input("Nome da Conexão (ex: Jira da Empresa X)")
        jira_url = col2.text_input("URL do Servidor Jira (ex: https://seu-nome.atlassian.net)")
        jira_email = col1.text_input("Email da Conta Jira")
        api_token = col2.text_input("Token da API Jira", type="password")
        
        if st.form_submit_button("Adicionar e Testar Conexão", type="primary", use_container_width=True):
            if all([conn_name, jira_url, jira_email, api_token]):
                encrypted_token = encrypt_token(api_token)
                add_jira_connection(email, conn_name, jira_url, jira_email, encrypted_token)
                st.success(f"Conexão '{conn_name}' adicionada com sucesso!"); st.rerun()
            else:
                st.error("Por favor, preencha todos os campos.")

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
                # Lógica para desativar o botão se a conexão já estiver ativa
                is_active = st.session_state.get('active_connection', {}).get('_id') == conn['_id']
                
                if st.button("Ativar para esta Sessão", key=f"activate_{conn['_id']}", use_container_width=True, type="primary", disabled=is_active):
                    with st.spinner("A ativar conexão e a buscar projetos..."):
                        token = decrypt_token(conn['encrypted_token'])
                        client = connect_to_jira(conn['jira_url'], conn['jira_email'], token)
                        if client:
                            # --- LÓGICA DE LIMPEZA DE ESTADO ---
                            # Limpa todos os dados da sessão anterior antes de definir a nova
                            keys_to_clear = [
                                'active_connection', 'jira_client', 'projects',
                                'project_key', 'project_name', 'dynamic_df',
                                'loaded_project_key', 'issues_data_fluxo', 'raw_issues_for_fluxo',
                                'selected_scope', 'view_to_show', 'chart_to_edit'
                            ]
                            for key in keys_to_clear:
                                if key in st.session_state:
                                    del st.session_state[key]

                            # Agora, define o novo estado
                            st.session_state.active_connection = conn
                            st.session_state.jira_client = client
                            st.session_state.projects = get_projects(client)
                            st.success(f"Conexão '{conn['connection_name']}' ativada!")
                            st.rerun()
                        else:
                            st.error("Falha ao ativar esta conexão. Verifique as credenciais.")
            
            with col3:
                if st.button("Remover", key=f"delete_{conn['_id']}", use_container_width=True):
                    delete_jira_connection(conn['_id'])
                    
                    if st.session_state.get('active_connection', {}).get('_id') == conn['_id']:
                        for key in ['active_connection', 'jira_client', 'projects', 'project_key', 'project_name', 'dynamic_df']:
                            if key in st.session_state: del st.session_state[key]
                    st.rerun()

# --- Status da Conexão na Sidebar ---
with st.sidebar:
    logo_path = os.path.join(os.path.dirname(__file__), "..", "images", "gauge-logo.svg")
    try: st.image(str(logo_path), width=150)
    except: pass
    st.divider()
    
    if 'active_connection' in st.session_state:
        active_conn_name = st.session_state.active_connection['connection_name']
        st.sidebar.success(f"Conexão Ativa: **{active_conn_name}**")
    else:
        st.sidebar.warning("Nenhuma conexão ativa nesta sessão.")
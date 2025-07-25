# 1_🔑_Login.py

import streamlit as st
import os
from security import *
from pathlib import Path
from jira_connector import *

st.set_page_config(page_title="Gauge Metrics - Login", page_icon="🔑", layout="wide")

# --- CSS para o design comercial ---
st.markdown("""
<style>
/* Remove o padding extra do topo da página */
.main .block-container {
    padding-top: 2rem;
}
/* Estilo para o container do formulário */
div[data-testid="stVerticalBlock"] div[data-testid="stVerticalBlock"] {
    background-color: #f8f9fa;
    border: 1px solid #dee2e6;
    border-radius: 10px;
    padding: 2em;
    box-shadow: 0 4px 12px 0 rgba(0,0,0,0.05);
}
/* Remove a borda do formulário interno para um look mais limpo */
div[data-testid="stForm"] {
    border: none;
    padding: 0;
}
</style>
""", unsafe_allow_html=True)

# Define o logo que aparecerá no topo da sidebar em TODAS as páginas.
with st.sidebar:
    project_root = Path(__file__).parent
    logo_path = project_root / "images" / "gauge-logo.svg"
    try:
        st.logo(
            logo_path, 
            size="large")
    except FileNotFoundError:
        st.write("Gauge Metrics") 
    
    if st.session_state == True:
        st.markdown(f"Logado como: **{st.session_state.get('email', '')}**")
    else:
        st.info("Usuário não conectado!")

# --- LÓGICA DA PÁGINA ---
if 'email' in st.session_state:
    # Se o utilizador já está logado, mostra uma mensagem de boas-vindas
    st.header(f"Bem-vindo de volta!", divider='rainbow')
    st.markdown(f"Você já está logado como **{st.session_state['email']}**.")
    st.info("Pode agora navegar para as páginas de análise na barra lateral esquerda.")
    if st.button("Logout", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
else:
    # --- Layout da Página de Login ---
    col1, col2 = st.columns([1, 1], gap="large")

    with col1:
        st.subheader("Decisões Guiadas por Dados, Sem Complicações.")
        st.markdown(
            """
            Transforme os dados do seu Jira em insights acionáveis. Com o **Gauge Metrics**, você pode:
            - 📊 Criar dashboards personalizados com um clique.
            - 📈 Prever datas de entrega com base na performance real da sua equipe.
            - 🔬 Analisar o fluxo de trabalho para identificar e remover gargalos.
            
            **Faça login ou registre-se para começar!**
            """
        )

    with col2:
        tab_login, tab_register = st.tabs(["**Login**", "**Registrar-se**"])

    with tab_login:
        with st.form("login_form"):
            st.markdown("##### Aceda à sua conta")
            email = st.text_input("Email", placeholder="o.seu.email@exemplo.com")
            password = st.text_input("Senha", type="password", placeholder="Digite a sua senha")
            if st.form_submit_button("Entrar", use_container_width=True, type="primary"):
                if email and password:
                    user = find_user(email)
                    if user and verify_password(password, user['hashed_password']):
                        st.session_state['email'] = user['email']
                        st.session_state['user_data'] = user
                        
                        # --- NOVA LÓGICA DE AUTO-ATIVAÇÃO ---
                        last_conn_id = user.get('last_active_connection_id')
                        if last_conn_id:
                            with st.spinner("A reconectar à sua última sessão Jira..."):
                                conn_details = get_connection_by_id(last_conn_id)
                                if conn_details:
                                    token = decrypt_token(conn_details['encrypted_token'])
                                    client = connect_to_jira(conn_details['jira_url'], conn_details['jira_email'], token)
                                    if client:
                                        st.session_state.active_connection = conn_details
                                        st.session_state.jira_client = client
                                        st.session_state.projects = get_projects(client)
                        
                        st.session_state['global_configs'] = get_global_configs()
                        if user.get('last_project_key'):
                            st.session_state['last_project_key'] = user.get('last_project_key')
                        
                        st.success("Login bem-sucedido! A carregar...")
                        st.switch_page("pages/2_🏠_Meu_Dashboard.py")
                    else:
                        st.error("Email ou senha inválidos.")
                else:
                    st.warning("Por favor, preencha todos os campos.")

        with tab_register:
            with st.form("register_form", clear_on_submit=True):
                st.markdown("##### Crie a sua conta gratuita")
                new_email = st.text_input("Seu melhor Email", key="reg_email")
                new_password = st.text_input("Crie uma Senha", type="password", key="reg_pass")
                confirm_password = st.text_input("Confirme a Senha", type="password", key="reg_confirm")
                if st.form_submit_button("Registrar", use_container_width=True, type='primary'):
                    if new_email and new_password and confirm_password:
                        if new_password == confirm_password:
                            if find_user(new_email):
                                st.error("Este email já está registrado. Por favor, faça login.")
                            else:
                                hashed_password = get_password_hash(new_password)
                                create_user(new_email, hashed_password)
                                st.success("Registro bem-sucedido! Agora pode fazer login na aba ao lado.")
                        else: st.error("As senhas não coincidem.")
                    else: st.warning("Por favor, preencha todos os campos.")
# 1_🔑_Autenticação.py

import streamlit as st
import os
from security import *
from pathlib import Path
from jira_connector import *

st.set_page_config(page_title="Gauge Metrics - Login", page_icon="🔑", layout="wide")

# --- CSS SIMPLIFICADO E COMPATÍVEL COM TEMAS ---
st.markdown("""
<style>
/* Remove o padding extra do topo da página */
.main .block-container {
    padding-top: 2rem;
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

# --- LÓGICA DA PÁGINA (sem alterações) ---
if 'email' in st.session_state:
    st.header(f"Bem-vindo de volta!", divider='rainbow')
    st.markdown(f"Você já está logado como **{st.session_state['email']}**.")
    st.info("Pode agora navegar para as páginas de análise na barra lateral esquerda.")
    if st.button("Logout", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
else:
    # --- Layout da Página de Login ---
    col1, col2 = st.columns([1.2, 1], gap="large")

    with col1:
        st.subheader("Decisões Guiadas por Dados, :orange[Sem Complicações.]")
        st.markdown(
            """
            Transforme os dados do seu Jira em insights acionáveis. Com o **Gauge Metrics**, você pode:
            - 📊 Criar dashboards personalizados com um clique.
            - 📈 Prever datas de entrega com base na performance real da sua equipa.
            - 🔬 Analisar o fluxo de trabalho para identificar e remover gargalos.
            
            **Faça login ou registe-se para começar!**
            """
        )

    with col2:
        # --- USA UM CONTAINER NATIVO PARA O CARTÃO ---
        with st.container(border=True):
            tab_login, tab_register = st.tabs(["**Login**", "**Registrar-se**"])

        with tab_login:
            with st.form("login_form"):
                st.markdown("##### Acesse a sua conta")
                email = st.text_input("Email", placeholder="email@exemplo.com")
                password = st.text_input("Senha", type="password", placeholder="Digite a sua senha")
                
                if st.form_submit_button("Entrar", use_container_width=True, type="primary"):
                    if email and password:
                        user = find_user(email)
                        if user and verify_password(password, user['hashed_password']):
                            st.session_state['email'] = user['email']
                            st.session_state['user_data'] = user
                            
                            # --- LÓGICA DE AUTO-ATIVAÇÃO ---
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
                st.markdown("##### Crie a sua conta")
                new_email = st.text_input("O seu Email corporativo", key="reg_email")
                new_password = st.text_input("Crie uma Senha", type="password", key="reg_pass")
                confirm_password = st.text_input("Confirme a Senha", type="password", key="reg_confirm")
                
                if st.form_submit_button("Registrar", use_container_width=True):
                    # Carrega a lista de domínios permitidos DA BASE DE DADOS
                    global_configs = get_global_configs()
                    ALLOWED_DOMAINS = global_configs.get("allowed_domains", [])
                    
                    if new_email and new_password and confirm_password:
                        try:
                            domain = new_email.split('@')[1]
                            # A verificação agora usa a lista da base de dados
                            if ALLOWED_DOMAINS and domain not in ALLOWED_DOMAINS:
                                st.error("Registro não permitido. O seu email deve pertencer a um dos domínios autorizados.")
                            else:
                                if new_password == confirm_password:
                                    if find_user(new_email):
                                        st.error("Este email já está registrado. Por favor, faça login.")
                                    else:
                                        hashed_password = get_password_hash(new_password)
                                        create_user(new_email, hashed_password)
                                        st.success("Registro bem-sucedido! Agora pode fazer login na aba ao lado.")
                                else:
                                    st.error("As senhas não coincidem.")
                        except IndexError:
                            st.error("Por favor, insira um endereço de email válido.")
                    else:
                        st.warning("Por favor, preencha todos os campos.")
            st.caption("ℹ️ Após o registo, você precisará de um Token de API do Jira para conectar a sua conta. [Pode criar um aqui](https://id.atlassian.com/manage-profile/security/api-tokens).")

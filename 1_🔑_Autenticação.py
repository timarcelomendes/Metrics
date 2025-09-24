# 1_🔑_Autenticação.py

import streamlit as st
import os
from security import *
from pathlib import Path
from jira_connector import *
from utils import send_email_with_attachment
from security import get_global_smtp_configs

st.set_page_config(page_title="Gauge Metrics - Login", 
                   page_icon="🔑", 
                   layout="wide" 
                   )

# Esta lógica será executada em todas as páginas e controlará o que é exibido.
if 'email' not in st.session_state:
    # Esconde a sidebar inteira se o utilizador não estiver logado
    st.markdown("""
        <style>
            [data-testid="stSidebar"] {
                display: none;
            }
        </style>
    """, unsafe_allow_html=True)
else:
    # Se estiver logado, verifica se é um admin
    ADMIN_EMAILS = st.secrets.get("app_settings", {}).get("ADMIN_EMAILS", [])
    if st.session_state['email'] not in ADMIN_EMAILS:
        # Se não for admin, esconde APENAS o link da página de administração
        st.markdown("""
            <style>
                /* Acha o link que contém a palavra "Administra" e esconde-o */
                a[href*="Administra"] {
                    display: none;
                }
            </style>
        """, unsafe_allow_html=True)
# =======================================================

# --- CSS para o design (sem alterações) ---
st.markdown("""
<style>
/* ... (Seu CSS aqui, sem alterações) ... */
</style>
""", unsafe_allow_html=True)

st.title (":blue[Gauge Products Hub] :signal_strength:")

# --- LÓGICA DA PÁGINA ---
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
    col1, col2 = st.columns([1, 0.9], gap="large")

    with col1:
        st.badge("Decisões Guiadas por Dados, Sem Complicações.")
        st.markdown(
            """
            O **Gauge Product Hub** é o seu copiloto estratégico, a transformar os dados operacionais do Jira em **insights** de alto nível. **Com ele, você está a poucos cliques de:**

            📊 Traduzir dados em narrativas: Crie dashboards que contam a história do progresso do seu projeto para qualquer audiência.
            
            📈 Substituir "achismos" por previsões: Entenda a capacidade real da sua equipa e preveja quando as suas iniciativas serão concluídas.
            
            🔬 Construir um sistema de entrega mais eficiente: Use a análise de fluxo para identificar oportunidades de melhoria contínua.

            Faça login ou registre-se para liderar com clareza.
            """
        )

    with col2:
        with st.container(border=True):
            col1, col2, col3 = st.tabs(["**Entrar**", "**Registrar-se**", "**Recuperar Senha**"])

        with col1:
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
                            
                            # Inicia o temporizador de inatividade da sessão
                            st.session_state['last_activity_time'] = datetime.now()
                            
                            # --- LÓGICA DE AUTO-ATIVAÇÃO DA CONEXÃO JIRA ---
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
                            
                            # Carrega as configurações globais e do utilizador na sessão
                            st.session_state['global_configs'] = get_global_configs()
                            st.session_state['smtp_configs'] = get_smtp_configs()
                            if user.get('last_project_key'):
                                st.session_state['last_project_key'] = user.get('last_project_key')

                            st.success("Login bem-sucedido! A carregar...")
                            st.switch_page("pages/2_🏠_Meu_Dashboard.py")
                        else:
                            st.error("Email ou senha inválidos.")
                    else:
                        st.warning("Por favor, preencha todos os campos.")

        with col2:
            with st.form("register_form", clear_on_submit=True):
                st.markdown("##### Crie a sua conta")
                new_email = st.text_input("O seu E-mail corporativo", key="reg_email")
                new_password = st.text_input("Crie uma Senha", type="password", key="reg_pass")
                confirm_password = st.text_input("Confirme a Senha", type="password", key="reg_confirm")
                
                if st.form_submit_button("Registrar", use_container_width=True, type="primary"):
                    if not all([new_email, new_password, confirm_password]):
                        st.warning("Por favor, preencha todos os campos.")
                    elif find_user(new_email):
                        st.error("Este e-mail já está registrado.")
                    elif len(new_password) < 8:
                        st.error("A senha deve ter pelo menos 8 caracteres.")
                    elif new_password != confirm_password:
                        st.error("As senhas não coincidem.")
                    else:
                        create_user(new_email, new_password)
                        st.success("Conta criada com sucesso! Por favor, faça login.")
                        
                        st.info("**Nota:** Para utilizar a ferramenta, você precisará de uma **conexão com o Jira**, que pode ser configurada após o seu primeiro login.", icon="ℹ️")

                        # --- ENVIO DO E-MAIL DE BOAS-VINDAS ---
                        welcome_subject = "Bem-vindo ao Gauge Metrics!"
                        welcome_html = """
                        <html><body>
                            <h2>Olá!</h2>
                            <p>A sua conta na plataforma Gauge Metrics foi criada com sucesso.</p>
                            <p>Estamos felizes por tê-lo a bordo. Faça login para começar a transformar os seus dados em insights.</p>
                            <p>Atenciosamente,<br>A Equipe Gauge Metrics</p>
                        </body></html>
                        """
                        send_email_with_attachment(new_email, welcome_subject, welcome_html)

with col3:
    st.markdown("##### Recuperação de Senha")
    st.info("Por favor, insira o seu e-mail. Se estiver registrado, enviaremos uma senha temporária para si.")
    with st.form("recover_form"):
        recover_email = st.text_input("Email", placeholder="email@exemplo.com")
        if st.form_submit_button("Enviar E-mail de Recuperação", use_container_width=True, type="primary"):
            if recover_email:
                user = find_user(recover_email)
                if user:
                    with st.spinner("A processar o seu pedido..."):
                        # Usa a nova função para carregar as configs globais
                        email_configs = get_global_smtp_configs()

                        if not email_configs:
                            st.error("Erro crítico: As configurações de envio de e-mail não foram encontradas. Por favor, contacte um administrador.")
                        else:
                            st.session_state['smtp_configs'] = email_configs
                            # O resto da lógica permanece igual...
                            temp_password = generate_temporary_password()
                            subject = "Recuperação de Senha - Gauge Metrics"
                            body_html = f"<html><body><p>Sua senha temporária é: <b>{temp_password}</b></p></body></html>"

                            success, message = send_email_with_attachment(recover_email, subject, body_html)

                            if success:
                                hashed_password = get_password_hash(temp_password)
                                update_user_password(recover_email, hashed_password)
                                st.success("E-mail de recuperação enviado com sucesso!")
                            else:
                                st.error(f"Falha ao enviar o e-mail: {message}. A sua senha não foi alterada.")
                else:
                    st.success("Se o seu e-mail estiver na nossa base, receberá as instruções.")
            else:
                st.warning("Por favor, insira um e-mail.")
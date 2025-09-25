# 1_🔑_Autenticação.py

import streamlit as st
import os
import base64
from security import *
from pathlib import Path
from jira_connector import *
from utils import send_email_with_attachment
from security import get_global_smtp_configs
from datetime import datetime

# --- CONFIGURAÇÃO DA PÁGINA ---
def get_image_as_base64(path):
    try:
        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode("utf-8")
        return f"data:image/png;base64,{data}"
    except FileNotFoundError:
        return None

logo_url = get_image_as_base64("images/logo.png")

st.set_page_config(page_title="Gauge Metrics - Login",
                   page_icon=logo_url if logo_url else "🔑",
                   layout="wide")

# --- CSS ---
def load_css(file_name):
    try:
        with open(file_name, "r", encoding="utf-8") as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
    except FileNotFoundError:
        st.warning(f"Arquivo CSS '{file_name}' não encontrado.")

load_css("css/login_style_innovative.css")

# --- INICIALIZAÇÃO SEGURA DO SESSION STATE ---
if 'remember_email' not in st.session_state:
    st.session_state.remember_email = ""

# --- CONTROLO DE ACESSO E SIDEBAR ---
if 'email' not in st.session_state:
    st.markdown('<style>[data-testid="stSidebar"] { display: none; }</style>', unsafe_allow_html=True)
else:
    ADMIN_EMAILS = st.secrets.get("app_settings", {}).get("ADMIN_EMAILS", [])
    if st.session_state['email'] not in ADMIN_EMAILS:
        st.markdown('<style>a[href*="Administra"] { display: none; }</style>', unsafe_allow_html=True)

# --- LÓGICA DA PÁGINA ---
if 'email' in st.session_state:
    st.header(f"Bem-vindo de volta!", divider='rainbow')
    st.markdown(f"Você já está logado como **{st.session_state['email']}**.")
    st.info("Pode agora navegar para as páginas de análise na barra lateral esquerda.")
    if st.button("Logout", use_container_width=True):
        keys_to_keep = ['remember_email']
        keys_to_delete = [key for key in st.session_state.keys() if key not in keys_to_keep]
        for key in keys_to_delete:
            del st.session_state[key]
        st.rerun()
else:
    # --- CABEÇALHO CENTRALIZADO COM LOGO E TÍTULO ---
    if logo_url:
        st.markdown(f"""
            <div class="header-container">
                <img src="{logo_url}" class="header-logo">
                <div class="title-container">
                    <div class="header-title">Gauge Products Hub</div>
                    <div class="header-subtitle">Decisões Guiadas por Dados, Sem Complicações.</div>
                </div>
            </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("<h1 style='text-align: center;'>Gauge Products Hub</h1>", unsafe_allow_html=True)
        st.markdown("<h4 style='text-align: center; color: #555;'>Decisões Guiadas por Dados, Sem Complicações.</h4>", unsafe_allow_html=True)

    st.divider()

    login_col, desc_col = st.columns([0.9, 1.1], gap="large")

    with login_col:
        with st.container(border=True):
            tab1, tab2, tab3 = st.tabs(["**Entrar**", "**Registrar-se**", "**Recuperar Senha**"])

            with tab1:
                with st.form("login_form"):
                    st.markdown("##### Acesse a sua conta")
                    email = st.text_input("Email", value=st.session_state.get('remember_email', ''), placeholder="email@exemplo.com")
                    password = st.text_input("Senha", type="password", placeholder="Digite a sua senha")
                    remember_me = st.checkbox("Lembrar-me", value=bool(st.session_state.get('remember_email', '')))

                    if st.form_submit_button("Entrar", use_container_width=True, type="primary"):
                        if email and password:
                            user = find_user(email)
                            if user and verify_password(password, user['hashed_password']):
                                if remember_me:
                                    st.session_state['remember_email'] = email
                                else:
                                    if st.session_state.get('remember_email'):
                                        st.session_state['remember_email'] = ""

                                st.session_state['email'] = user['email']
                                st.session_state['user_data'] = user
                                st.session_state['last_activity_time'] = datetime.now()
                                
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
                                st.session_state['smtp_configs'] = get_smtp_configs()
                                if user.get('last_project_key'):
                                    st.session_state['last_project_key'] = user.get('last_project_key')
                                
                                st.success("Login bem-sucedido! A carregar...")
                                st.switch_page("pages/2_🏠_Meu_Dashboard.py")
                            else:
                                st.error("Email ou senha inválidos.")
                        else:
                            st.warning("Por favor, preencha todos os campos.")

            with tab2:
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
                            st.info("Para utilizar a ferramenta, você precisará de uma conexão com o Jira, que pode ser configurada após o seu primeiro login.", icon="ℹ️")
                            welcome_subject = "Bem-vindo ao Gauge Metrics!"
                            welcome_html = "<html><body><h2>Olá!</h2><p>A sua conta na plataforma Gauge Metrics foi criada com sucesso.</p><p>Estamos felizes por tê-lo a bordo. Faça login para começar a transformar os seus dados em insights.</p><p>Atenciosamente,<br>A Equipe Gauge Metrics</p></body></html>"
                            send_email_with_attachment(new_email, welcome_subject, welcome_html)

            with tab3:
                with st.form("recover_form"):
                    st.markdown("##### Recuperação de Senha")
                    st.info("Por favor, insira o seu e-mail. Se estiver registrado, enviaremos uma senha temporária para si.")
                    recover_email = st.text_input("Email", placeholder="email@exemplo.com")
                    if st.form_submit_button("Enviar E-mail de Recuperação", use_container_width=True, type="primary"):
                        if recover_email:
                            user = find_user(recover_email)
                            if user:
                                with st.spinner("A processar o seu pedido..."):
                                    st.session_state['smtp_configs'] = get_global_smtp_configs()
                                    if not st.session_state['smtp_configs']:
                                        st.error("Erro crítico: As configurações de envio de e-mail não foram encontradas. Contacte um administrador.")
                                    else:
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
                                    if 'smtp_configs' in st.session_state:
                                        del st.session_state['smtp_configs']
                            else:
                                st.success("Se o seu e-mail estiver na nossa base, receberá as instruções.")
                        else:
                            st.warning("Por favor, insira um e-mail.")


    with desc_col:
        with st.container(border=True):
            st.markdown(
                """
                O **Gauge Product Hub** é o seu copiloto estratégico, que transforma dados operacionais do Jira em **insights** de alto nível. Com ele, você está a poucos cliques de:
                """
            )

            with st.container(border=True):
                st.markdown("📊 **Traduzir dados em narrativas:** Crie dashboards que contam a história do progresso do seu projeto.")

            with st.container(border=True):
                st.markdown("📈 **Substituir 'achismos' por previsões:** Entenda a capacidade real da sua equipa e preveja conclusões.")

            with st.container(border=True):
                st.markdown("🔬 **Construir um sistema de entrega mais eficiente:** Use a análise de fluxo para melhoria contínua.")
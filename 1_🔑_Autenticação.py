# 1_🔑_Autenticação.py

import streamlit as st
import os
from security import *
from pathlib import Path
from jira_connector import *
from utils import send_notification_email

st.set_page_config(page_title="Gauge Metrics - Login", 
                   page_icon="🔑", 
                   layout="wide" 
                   )

# ===== NOVO BLOCO DE CONTROLO DE VISIBILIDADE =====
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

# Define o logo que aparecerá no topo da sidebar (apenas para utilizadores logados)
with st.sidebar:
    project_root = Path(__file__).parent
    logo_path = project_root / "images" / "gauge-logo.svg"
    try:
        st.logo(str(logo_path), size="large")
    except FileNotFoundError:
        st.write("Gauge Metrics")
    
    if st.session_state.get("email"):
        st.markdown(f"🔐 Logado como: **{st.session_state['email']}**")
    else:
        st.info("⚠️ Usuário não conectado!")

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
    col1, col2 = st.columns([1, 1.3], gap="large")

    with col1:
        st.subheader("Decisões Guiadas por Dados, :orange[Sem Complicações.]")
        st.markdown(
            """
            Transforme os dados do seu Jira em insights acionáveis. Com o **Gauge Metrics**, você pode:
            - 📊 Criar dashboards personalizados com um clique.
            - 📈 Prever datas de entrega com base na performance real da sua equipa.
            - 🔬 Analisar o fluxo de trabalho para identificar e remover gargalos.
            
            **Faça login ou registre-se para começar!**
            """
        )

    with col2:
        # --- USA UM CONTAINER NATIVO PARA O CARTÃO ---
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

        with col2:
            with st.form("register_form", clear_on_submit=True):
                st.markdown("##### Crie a sua conta")
                new_email = st.text_input("O seu E-mail corporativo", key="reg_email")
                new_password = st.text_input("Crie uma Senha", type="password", key="reg_pass")
                confirm_password = st.text_input("Confirme a Senha", type="password", key="reg_confirm")
                
                if st.form_submit_button("Registrar", use_container_width=True):
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
                            <p>Atenciosamente,<br>A Equipa Gauge Metrics</p>
                        </body></html>
                        """
                        send_notification_email(new_email, welcome_subject, welcome_html)
                                        # --- NOVA MENSAGEM INFORMATIVA ---


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
                                    # Gera e guarda a nova senha, e obtém a versão em texto
                                    temp_password = reset_user_password_with_temporary(recover_email)
                                    
                                    # Envia o e-mail com a senha temporária
                                    subject = "Recuperação de Senha - Gauge Metrics"
                                    body_html = f"""
                                    <html><body>
                                        <h2>Recuperação de Senha</h2>
                                        <p>Olá,</p>
                                        <p>Você solicitou a recuperação da sua senha. Use a senha temporária abaixo para fazer login:</p>
                                        <p style="font-size: 1.2em; font-weight: bold; color: #1c4e80;">{temp_password}</p>
                                        <p><b>Importante:</b> Após o login, vá à sua página 'Minha Conta' e altere esta senha para uma da sua preferência.</p>
                                        <p>Se não foi você que fez esta solicitação, por favor, ignore este e-mail.</p>
                                    </body></html>
                                    """
                                    send_notification_email(recover_email, subject, body_html)
                            
                            # Mostra sempre uma mensagem de sucesso para não confirmar se um e-mail existe ou não
                            st.success("Pedido de recuperação enviado! Se o seu e-mail estiver na nossa base de dados, você receberá as instruções em breve.")
                        else:
                            st.warning("Por favor, insira um e-mail.")
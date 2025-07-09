# pages/3_👤_Minha_Conta.py
import streamlit as st
from jira_connector import connect_to_jira
from security import find_user, save_jira_credentials, encrypt_token, decrypt_token
import os

st.set_page_config(page_title="Minha Conta", page_icon="👤", layout="wide")

if st.session_state.get('jira_client'):
        st.caption(f"Conectado como: {st.session_state.get('email', '')}")
st.header("👤 Minha Conta e Credenciais do Jira")

if 'email' not in st.session_state:
    st.warning("Por favor, faça login para aceder a esta página.")
    st.page_link("1_🔑_Login.py", label="Ir para Login", icon="🔑")
    st.stop()
    
email = st.session_state['email']
user_data = find_user(email)
if not user_data:
    st.error("Utilizador não encontrado na base de dados."); st.stop()

with st.container(border=True):
    st.subheader(f"Credenciais Jira para: {email}")
    st.markdown("As suas credenciais são guardadas de forma segura e usadas para buscar os dados dos projetos.")

    with st.form("jira_credentials_form"):
        jira_server = st.text_input("URL do Servidor Jira", value=user_data.get('jira_url', ''))
        jira_email = st.text_input("Email da Conta Jira", value=user_data.get('jira_email', ''))
        
        if user_data.get('encrypted_token'):
            st.info("🔑 Um token já está guardado. Preencha abaixo apenas se quiser alterá-lo.")
            api_token = st.text_input("Novo Token da API Jira (opcional)", type="password")
        else:
            api_token = st.text_input("Token da API Jira", type="password")

        submitted = st.form_submit_button("Guardar e Testar Credenciais", type="primary")
        if submitted:
            final_token = api_token if api_token else decrypt_token(user_data['encrypted_token']) if user_data.get('encrypted_token') else None
            if not final_token: st.error("O Token da API é obrigatório.")
            else:
                with st.spinner("A testar conexão e a guardar..."):
                    client = connect_to_jira(jira_server, jira_email, final_token)
                    if client:
                        encrypted_token = encrypt_token(final_token)
                        save_jira_credentials(email, jira_server, jira_email, encrypted_token)
                        st.success("Credenciais do Jira guardadas e validadas com sucesso!")
                        # Limpa o cliente jira da sessão para forçar a recriação com as novas credenciais
                        if 'jira_client' in st.session_state:
                            del st.session_state['jira_client']
                    else:
                        st.error("Falha na conexão com o Jira. Verifique os dados inseridos.")

# ... (Barra lateral com logo e botão de Logout)
with st.sidebar:
    logo_path = os.path.join(os.path.dirname(__file__), "..", "images", "gauge-logo.svg")
    try: st.image(logo_path, width=150)
    except: pass
    st.divider()
    if st.button("Logout", use_container_width=True):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.switch_page("1_🔑_Login.py")
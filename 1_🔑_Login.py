# 1_🔑_Login.py

import streamlit as st
from security import find_user, create_user, verify_password, get_password_hash
from config import AVAILABLE_STANDARD_FIELDS

st.set_page_config(page_title="Login", page_icon="🔑", layout="centered")

if 'available_standard_fields' not in st.session_state:
    st.session_state['available_standard_fields'] = AVAILABLE_STANDARD_FIELDS

if 'email' in st.session_state:
    st.success(f"Login realizado como **{st.session_state['email']}**.")
    st.info("Pode agora navegar para as páginas de análise na barra lateral esquerda.")
    st.page_link("pages/2_🏠_Meu_Dashboard.py", label="Ir para o Meu Dashboard", icon="🏠")
    if st.button("Logout"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()
    st.stop()

col1, col2, col3 = st.columns([1,1,1])
with col2:
    try: st.image("images/gauge-logo.svg", width=250)
    except: pass

st.title("Dashboard de Métricas Ágeis")

with st.container(border=True):
    login_tab, register_tab = st.tabs(["Login", "Registar Nova Conta"])
    with login_tab:
        with st.form("login_form"):
            email = st.text_input("Email", placeholder="o.seu.email@exemplo.com", label_visibility="collapsed")
            password = st.text_input("Palavra-passe", type="password", placeholder="Digite a sua palavra-passe", label_visibility="collapsed")
            if st.form_submit_button("Entrar", type="primary", use_container_width=True):
                user = find_user(email)
                if user and verify_password(password, user['hashed_password']):
                    st.session_state['email'] = user['email']
                    # --- LÓGICA ATUALIZADA ---
                    # Guarda o último projeto visitado na sessão, se existir
                    if user.get('last_project_key'):
                        st.session_state['last_project_key'] = user.get('last_project_key')
                    st.success("Login bem-sucedido! A carregar o seu dashboard...")
                    st.switch_page("pages/2_🏠_Meu_Dashboard.py")
                else:
                    st.error("Email ou palavra-passe incorretos.")
    with register_tab:
        with st.form("register_form", clear_on_submit=True):
            st.subheader("Criar Nova Conta")
            new_email = st.text_input("Email", placeholder="O seu melhor email", label_visibility="collapsed")
            new_password = st.text_input("Crie uma Palavra-passe forte", type="password", placeholder="Crie uma palavra-passe forte", label_visibility="collapsed")
            confirm_password = st.text_input("Confirme a Palavra-passe", type="password", placeholder="Confirme a sua palavra-passe", label_visibility="collapsed")
            if st.form_submit_button("Registar", use_container_width=True):
                if not all([new_email, new_password, confirm_password]): st.error("Por favor, preencha todos os campos.")
                elif new_password != confirm_password: st.error("As palavras-passe não coincidem.")
                elif find_user(new_email): st.error("Este email já está registado.")
                else:
                    hashed_password = get_password_hash(new_password)
                    create_user(new_email, hashed_password)
                    st.success("Conta criada com sucesso! Por favor, faça login.")
st.sidebar.empty()

# Limpa a barra lateral apenas se o utilizador NÃO estiver logado
if 'email' not in st.session_state:
    st.sidebar.empty()
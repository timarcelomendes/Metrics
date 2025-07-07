# 1_🔑_Login.py
import streamlit as st
from security import find_user, create_user, verify_password, get_password_hash
from config import AVAILABLE_STANDARD_FIELDS

st.set_page_config(page_title="Login", page_icon="🔑", layout="centered")

# Guarda a lista de campos disponíveis na sessão para as outras páginas usarem
if 'available_standard_fields' not in st.session_state:
    st.session_state['available_standard_fields'] = AVAILABLE_STANDARD_FIELDS

with st.sidebar:
    try: st.image("images/gauge-logo.png", width=150)
    except Exception: pass

st.header("🔑 Acesso ao Dashboard de Métricas Ágeis")

if 'email' in st.session_state:
    st.success(f"Login realizado como **{st.session_state['email']}**.")
    st.info("Pode agora navegar para as páginas de análise na barra lateral.")
    if st.button("Logout", use_container_width=True, type="secondary"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()
    st.stop()

login_tab, register_tab = st.tabs(["Login", "Registar Nova Conta"])
with login_tab:
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Palavra-passe", type="password")
        if st.form_submit_button("Entrar", type="primary", use_container_width=True):
            user = find_user(email)
            if user and verify_password(password, user['hashed_password']):
                st.session_state['email'] = user['email']
                st.success("Login bem-sucedido! Redirecionando...")
                st.switch_page("pages/2_📊_Métricas_de_Fluxo.py")
            else:
                st.error("Email ou palavra-passe incorretos.")
with register_tab:
    with st.form("register_form", clear_on_submit=True):
        st.subheader("Registar Nova Conta")
        new_email = st.text_input("O seu melhor Email")
        new_password = st.text_input("Crie uma Palavra-passe", type="password")
        confirm_password = st.text_input("Confirme a Palavra-passe", type="password")
        if st.form_submit_button("Registar", use_container_width=True):
            if not all([new_email, new_password, confirm_password]): st.error("Por favor, preencha todos os campos.")
            elif new_password != confirm_password: st.error("As palavras-passe não coincidem.")
            elif find_user(new_email): st.error("Este email já está registado. Por favor, faça login.")
            else:
                hashed_password = get_password_hash(new_password)
                create_user(new_email, hashed_password)
                st.success("Conta criada com sucesso! Por favor, faça login na aba ao lado.")
# 1_🔑_Login.py

import streamlit as st
import os
from security import find_user, create_user, verify_password, get_password_hash, get_global_configs

st.set_page_config(page_title="Login", page_icon="🔑", layout="centered")

# --- NOVO: Adiciona a logo na sidebar ---
with st.sidebar:
    logo_path = os.path.join(os.path.dirname(__file__), "..", "images", "gauge-logo.svg")
    try:
        st.image(logo_path, width=150)
    except Exception as e:
        # Se a imagem não for encontrada, não quebra a aplicação
        st.error(f"Logo não encontrada: {e}", icon="🖼️")

# Carrega as configs globais na primeira execução
if 'global_configs' not in st.session_state:
    st.session_state['global_configs'] = get_global_configs()

# --- Lógica de Login e Registro (sem alterações) ---
if 'email' in st.session_state:
    st.header(f"Bem-vindo de volta!", divider='rainbow')
    st.markdown(f"Você já está logado como **{st.session_state['email']}**.")
    st.markdown("Selecione uma das opções no menu lateral para iniciar a sua análise.")
    if st.button("Logout"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
else:
    st.title("Dashboard de Métricas Ágeis")
    st.text("Por favor, faça login ou registe-se para continuar.")

    tab1, tab2 = st.tabs(["Login", "Registar-se"])

    with tab1:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar", use_container_width=True, type="primary"):
                if email and password:
                    user = find_user(email)
                    if user and verify_password(password, user['hashed_password']):
                        st.session_state['email'] = user['email']
                        st.session_state['user_data'] = user
                        st.session_state['global_configs'] = get_global_configs()
                        if user.get('last_project_key'):
                            st.session_state['last_project_key'] = user.get('last_project_key')
                        st.success("Login bem-sucedido! A carregar o seu dashboard...")
                        st.switch_page("pages/2_🏠_Meu_Dashboard.py")
                    else:
                        st.error("Email ou senha inválidos.")
                else:
                    st.warning("Por favor, preencha todos os campos.")

    with tab2:
        with st.form("register_form", clear_on_submit=True):
            new_email = st.text_input("Seu melhor Email")
            new_password = st.text_input("Crie uma Senha", type="password")
            confirm_password = st.text_input("Confirme a Senha", type="password")
            if st.form_submit_button("Registar", use_container_width=True):
                if new_email and new_password and confirm_password:
                    if new_password == confirm_password:
                        if find_user(new_email):
                            st.error("Este email já está registado. Por favor, faça login.")
                        else:
                            hashed_password = get_password_hash(new_password)
                            create_user(new_email, hashed_password)
                            st.success("Registo bem-sucedido! Agora pode fazer login.")
                    else:
                        st.error("As senhas não coincidem.")
                else:
                    st.warning("Por favor, preencha todos os campos.")
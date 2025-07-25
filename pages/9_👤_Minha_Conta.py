# pages/7_👤_Minha_Conta.py

import streamlit as st
import os
from pathlib import Path
from security import find_user, save_user_standard_fields, get_global_configs, verify_password, get_password_hash, update_user_password, save_user_custom_fields

st.set_page_config(page_title="Minha Conta", page_icon="👤", layout="wide")

st.header("👤 Minha Conta", divider='rainbow')

if 'email' not in st.session_state:
    st.warning("⚠️ Por favor, faça autenticação para acessar esta página."); st.page_link("1_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑"); st.stop()

email = st.session_state['email']
user_data = find_user(email)
global_configs = st.session_state.get('global_configs', {})

with st.sidebar:
    project_root = Path(__file__).parent.parent
    logo_path = project_root / "images" / "gauge-logo.svg"
    try:
        st.logo(
            logo_path, 
            size="large")
    except FileNotFoundError:
        st.write("Gauge Metrics") 
    
    if st.session_state.get("email"):
        st.markdown(f"🔐 Logado como: **{st.session_state['email']}**")
    else:
        st.info("⚠️ Usuário não conectado!")
        
    if st.button("Logout", use_container_width=True, type='secondary'):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.switch_page("1_🔑_Autenticação.py")

# --- ESTRUTURA DE ABAS ---
tab1, tab2 = st.tabs(["Perfil e Segurança", "Preferências de Campos"])

with tab1:
    st.subheader("Informações do Perfil")
    
    col1, col2 = st.columns(2, gap="large")
    with col1:
        with st.container(border=True):
            st.info(f"**Utilizador:** {email}")
            st.page_link(
                "pages/8_🔗_Conexões_Jira.py",
                label="Gerir Minhas Conexões Jira",
                icon="🔗"
            )
    
    with col2:
        with st.container(border=True):
            st.markdown("**Alterar Senha**")
            with st.form("change_password_form"):
                current_password = st.text_input("Senha Atual", type="password")
                new_password = st.text_input("Nova Senha", type="password")
                confirm_password = st.text_input("Confirmar Nova Senha", type="password")
                
                submitted = st.form_submit_button("Alterar Senha", use_container_width=True, type="primary")

                if submitted:
                    if not all([current_password, new_password, confirm_password]):
                        st.warning("Por favor, preencha todos os campos.")
                    elif not verify_password(current_password, user_data['hashed_password']):
                        st.error("A 'Senha Atual' está incorreta.")
                    elif len(new_password) < 8:
                        st.error("A nova senha deve ter pelo menos 8 caracteres.")
                    elif new_password != confirm_password:
                        st.error("A 'Nova Senha' e a 'Confirmação' não coincidem.")
                    else:
                        new_hashed_password = get_password_hash(new_password)
                        update_user_password(email, new_hashed_password)
                        st.success("Senha alterada com sucesso!")

with tab2:
    st.subheader("Preferências de Campos para Análise")
    st.caption("Ative os campos que você deseja que apareçam como opções nas páginas de análise.")
    
    col1, col2 = st.columns(2, gap="large")
    
    with col1:
        with st.container(border=True):
            st.markdown("**Campos Padrão**")
            available_standard_fields = global_configs.get('available_standard_fields', {})
            user_selected_standard = user_data.get('standard_fields', [])
            
            toggles_std = {}
            if not available_standard_fields:
                st.info("Nenhum campo padrão configurado pelo admin.")
            else:
                for name in sorted(available_standard_fields.keys()):
                    toggles_std[name] = st.toggle(name, value=(name in user_selected_standard), key=f"toggle_std_{name}")
    
    with col2:
        with st.container(border=True):
            st.markdown("**Campos Personalizados**")
            available_custom_fields = global_configs.get('custom_fields', [])
            user_selected_custom = user_data.get('enabled_custom_fields', [])

            if not available_custom_fields:
                st.info("Nenhum campo personalizado configurado pelo admin.")
            else:
                toggles_custom = {}
                for field in sorted(available_custom_fields, key=lambda x: x['name']):
                    name = field['name']
                    toggles_custom[name] = st.toggle(name, value=(name in user_selected_custom), key=f"toggle_custom_{name}")
    
    st.divider()
    if st.button("Salvar Minhas Preferências", use_container_width=True, type="primary"):
        new_selection_std = [name for name, is_on in toggles_std.items() if is_on]
        save_user_standard_fields(email, new_selection_std)
        
        if 'toggles_custom' in locals():
            new_selection_custom = [name for name, is_on in toggles_custom.items() if is_on]
            save_user_custom_fields(email, new_selection_custom)

        st.success("Suas preferências de campos foram guardadas!")
        st.rerun()
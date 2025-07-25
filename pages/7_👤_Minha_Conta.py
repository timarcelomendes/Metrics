# pages/7_👤_Minha_Conta.py

import streamlit as st
import os
from pathlib import Path
from security import find_user, save_user_standard_fields, save_user_custom_fields, get_global_configs

st.set_page_config(page_title="Minha Conta", page_icon="👤", layout="wide")

st.header("👤 Minha Conta", divider='rainbow')

if 'email' not in st.session_state:
    st.warning("⚠️ Por favor, faça login para aceder a esta página."); st.page_link("1_🔑_Login.py", label="Ir para Login", icon="🔑"); st.stop()

with st.sidebar:
    project_root = Path(__file__).parent.parent
    logo_path = project_root / "images" / "gauge-logo.svg"
    try:
        st.logo(
            logo_path, 
            size="large")
    except FileNotFoundError:
        st.write("Gauge Metrics") 

    st.markdown(f"Logado como: **{st.session_state.get('email', '')}**")

    if st.button("Logout", use_container_width=True, type='secondary'):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.switch_page("1_🔑_Login.py")

email = st.session_state['email']
user_data = find_user(email)
global_configs = st.session_state.get('global_configs', {})

col1, col2 = st.columns(2, gap="large")

with col1:
    with st.container(border=True):
        st.subheader("Informações do Perfil")
        st.info(f"**Utilizador:** {email}")
        st.page_link("pages/8_🔗_Conexões_Jira.py", label="Gerir Minhas Conexões Jira", icon="🔗")

with col2:
    with st.container(border=True):
        st.subheader("Preferências de Campos para Análise")
        st.caption("Ative os campos que você deseja que apareçam como opções nas páginas de análise.")
        
        # --- Secção para Campos Padrão ---
        st.markdown("**Campos Padrão**")
        available_standard_fields = global_configs.get('available_standard_fields', {})
        user_selected_standard = user_data.get('standard_fields', [])
        
        toggles_std = {}
        for name in sorted(available_standard_fields.keys()):
            toggles_std[name] = st.toggle(name, value=(name in user_selected_standard), key=f"toggle_std_{name}")
        
        # --- Secção para Campos Personalizados ---
        st.divider()
        st.markdown("**Campos Personalizados**")
        available_custom_fields = global_configs.get('custom_fields', [])
        user_selected_custom = user_data.get('enabled_custom_fields', [])

        if not available_custom_fields:
            st.info("Nenhum campo personalizado foi configurado pelo administrador.")
        else:
            toggles_custom = {}
            for field in sorted(available_custom_fields, key=lambda x: x['name']):
                name = field['name']
                toggles_custom[name] = st.toggle(name, value=(name in user_selected_custom), key=f"toggle_custom_{name}")
        
        # --- Botão de Salvar ---
        if st.button("Salvar Minhas Preferências", use_container_width=True, type="primary"):
            new_selection_std = [name for name, is_on in toggles_std.items() if is_on]
            save_user_standard_fields(email, new_selection_std)
            
            if available_custom_fields:
                new_selection_custom = [name for name, is_on in toggles_custom.items() if is_on]
                save_user_custom_fields(email, new_selection_custom)

            st.success("Suas preferências de campos foram guardadas!")
            st.rerun()
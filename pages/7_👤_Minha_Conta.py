# pages/7_👤_Minha_Conta.py

import streamlit as st
import os
from pathlib import Path
from security import find_user, save_user_standard_fields, get_global_configs

st.set_page_config(page_title="Minha Conta", page_icon="👤", layout="wide")

st.header("👤 Minha Conta", divider='rainbow')

if 'email' not in st.session_state:
    st.warning("⚠️ Por favor, faça login para aceder a esta página.")
    st.page_link("1_🔑_Login.py", label="Ir para Login", icon="🔑")
    st.stop()

email = st.session_state['email']
user_data = find_user(email)

col1, col2 = st.columns(2, gap="large")

with col1:
    with st.container(border=True):
        st.subheader("Informações do Perfil")
        st.info(f"**Utilizador:** {email}")
        st.page_link(
            "pages/8_🔗_Conexões_Jira.py",
            label="Gerir Minhas Conexões Jira",
            icon="🔗"
        )
        # Futuramente: st.button("Mudar Senha")

# --- NOVA SECÇÃO PARA PREFERÊNCIAS DE CAMPOS ---
with col2:
    with st.container(border=True):
        st.subheader("Preferências de Campos")
        st.caption("Ative os campos padrão que você deseja que apareçam como opções nas páginas de análise.")

        global_configs = get_global_configs()
        available_standard_fields = global_configs.get('available_standard_fields', {})
        user_selected_fields = user_data.get('standard_fields', [])
        
        if not available_standard_fields:
            st.info("Nenhum campo padrão foi configurado pelo administrador na página de Configurações Globais.")
        else:
            toggles = {}
            for name in sorted(available_standard_fields.keys()):
                is_selected = name in user_selected_fields
                toggles[name] = st.toggle(name, value=is_selected)

            if st.button("Salvar Minhas Preferências", use_container_width=True, type="primary"):
                # Cria a nova lista de campos selecionados
                new_selection = [name for name, is_toggled_on in toggles.items() if is_toggled_on]
                save_user_standard_fields(email, new_selection)
                st.success("Suas preferências de campos foram guardadas!")
                st.rerun()
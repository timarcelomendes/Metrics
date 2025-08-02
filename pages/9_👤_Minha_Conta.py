# pages/7_👤_Minha_Conta.py

import streamlit as st
import os
from pathlib import Path
from security import *

st.set_page_config(page_title="Minha Conta", page_icon="👤", layout="wide")

st.header("👤 Minha Conta", divider='rainbow')

if 'email' not in st.session_state:
    st.warning("⚠️ Por favor, faça login para aceder a esta página.")
    st.page_link("1_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑")
    st.stop()

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
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.switch_page("1_🔑_Autenticação.py")

# --- ESTRUTURA DE ABAS PRINCIPAL ---
tab1, tab2, tab3 = st.tabs(["**Perfil e Segurança**", "**Preferências de Campos**", "**Configurações de IA**"])

with tab1:
    st.subheader("Informações do Perfil")
    col1, col2 = st.columns(2, gap="large")
    with col1:
        with st.container(border=True):
            st.info(f"**Utilizador:** {email}")
            st.page_link("pages/8_🔗_Conexões_Jira.py", label="Gerir Minhas Conexões Jira", icon="🔗")
    with col2:
        with st.container(border=True):
            st.markdown("**Alterar Senha**")
            with st.form("change_password_form"):
                current_password = st.text_input("Senha Atual", type="password")
                new_password = st.text_input("Nova Senha", type="password")
                confirm_password = st.text_input("Confirmar Nova Senha", type="password")
                if st.form_submit_button("Alterar Senha", use_container_width=True, type="primary"):
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
    st.caption("Ative os campos que você deseja que apareçam como opções nas páginas de análise. As alterações são guardadas para o seu perfil.")

    # --- ABAS INTERNAS PARA ORGANIZAÇÃO ---
    tab_std, tab_custom = st.tabs(["🗂️ Campos Padrão", "✨ Campos Personalizados"])
    
    toggles_std = {}
    toggles_custom = {}

    with tab_std:
        available_standard_fields = global_configs.get('available_standard_fields', {})
        user_selected_standard = user_data.get('standard_fields', [])
        
        if not available_standard_fields:
            st.info("Nenhum campo padrão foi configurado pelo administrador.")
            st.page_link("pages/7_⚙️_Configurações.py", label="Configurar Campos Globais", icon="⚙️")
        else:
            st.markdown("**Ative os campos padrão que deseja usar:**")
            for name in sorted(available_standard_fields.keys()):
                toggles_std[name] = st.toggle(name, value=(name in user_selected_standard), key=f"toggle_std_{name}")

    with tab_custom:
        available_custom_fields = global_configs.get('custom_fields', [])
        user_selected_custom = user_data.get('enabled_custom_fields', [])

        if not available_custom_fields:
            st.info("Nenhum campo personalizado foi configurado pelo administrador.")
        else:
            st.markdown("**Ative os campos personalizados que deseja usar:**")
            for field in sorted(available_custom_fields, key=lambda x: x['name']):
                name = field['name']
                toggles_custom[name] = st.toggle(name, value=(name in user_selected_custom), key=f"toggle_custom_{name}")
    
    st.divider()
    if st.button("Salvar Preferências de Campos", use_container_width=True, type="primary"):
        new_selection_std = [name for name, is_on in toggles_std.items() if is_on]
        save_user_standard_fields(email, new_selection_std)
        
        if toggles_custom: # Só tenta salvar se a seção foi renderizada
            new_selection_custom = [name for name, is_on in toggles_custom.items() if is_on]
            save_user_custom_fields(email, new_selection_custom)

        st.success("Suas preferências de campos foram guardadas!")
        st.rerun()

with tab3:
    st.subheader("🤖 Configurações de Inteligência Artificial")
    with st.container(border=True):
        st.caption("Para usar as funcionalidades de IA, como a geração de insights, você precisa de fornecer a sua própria chave de API do Google Gemini e escolher o modelo a ser utilizado.")
        
        # --- Campo para a Chave de API ---
        key_exists = 'encrypted_gemini_key' in user_data and user_data['encrypted_gemini_key']
        if key_exists: st.success("Uma chave de API do Gemini já está configurada.", icon="✅")
        else: st.warning("Nenhuma chave de API do Gemini encontrada.", icon="⚠️")

        with st.form("gemini_config_form"):
            api_key = st.text_input("Sua Chave de API do Google Gemini", type="password", placeholder="Cole a sua chave de API aqui")
            
            # --- LINK DE AJUDA ADICIONADO AQUI ---
            st.caption("Não tem uma chave? [**Clique aqui para criar uma gratuitamente no Google AI Studio**](https://aistudio.google.com/app/apikey)")

            # --- Seletor de Modelo ---
            model_options = {
                "Gemini 1.5 Pro (Mais poderoso)": "gemini-1.5-pro-latest",
                "Gemini 1.5 Flash (Mais rápido)": "gemini-1.5-flash-latest"
            }
            user_preference = user_data.get('ai_model_preference', 'gemini-1.5-pro-latest')
            default_model_name = next((name for name, model_id in model_options.items() if model_id == user_preference), None)
            
            selected_model_name = st.selectbox(
                "Modelo de IA Preferido",
                options=model_options.keys(),
                index=list(model_options.keys()).index(default_model_name) if default_model_name else 0
            )
            
            if st.form_submit_button("Salvar Configurações de IA", use_container_width=True, type="primary"):
                if api_key:
                    encrypted_key = encrypt_token(api_key)
                    save_user_gemini_key(email, encrypted_key)
                
                selected_model_id = model_options[selected_model_name]
                save_user_ai_model_preference(email, selected_model_id)
                
                st.success("Suas configurações de IA foram guardadas com segurança!")
                st.rerun()
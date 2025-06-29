# 1_⚙️_Configurações.py

import streamlit as st
from jira_connector import connect_to_jira, get_projects
import json
import os
from config import * # Importa todas as constantes do ficheiro central
from security import (
    save_user_credentials, get_user_credentials, 
    get_all_profiles, encrypt_token, decrypt_token,
    delete_profile
)

st.set_page_config(page_title="Configurações", page_icon="⚙️", layout="wide")

# --- Funções de Configuração ---
def load_config(file_path, default_value):
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            try: return json.load(f)
            except json.JSONDecodeError: return default_value
    return default_value

def save_config(data, file_path):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

# --- LÓGICA DA PÁGINA ---
with st.sidebar:
    try:
        st.image("images/gauge-logo.png", width=150)
    except Exception:
        pass

st.header("⚙️ Configurações e Conexão")

# Bloco de status de conexão amigável
if 'jira_client' in st.session_state and st.session_state.jira_client is not None and st.session_state.get('active_profile'):
    with st.container(border=True):
        col1, col2 = st.columns([1, 4])
        with col1: st.success("Conectado", icon="✅")
        with col2:
            st.markdown(f"**Perfil Ativo:** `{st.session_state.active_profile}`")
            st.markdown(f"**Servidor:** `{st.session_state.jira_client._options['server']}`")
    st.info("Tudo pronto! Pode navegar para as páginas de análise na barra lateral.")
else:
    st.warning("Nenhum perfil conectado nesta sessão. Crie ou selecione um perfil e conecte-se.")

st.divider()

# Gestão de Perfis e Conexão
with st.container(border=True):
    st.subheader("1. Perfis de Conexão")
    st.markdown("Crie ou selecione um perfil para guardar as suas credenciais do Jira de forma segura.")
    
    profiles = get_all_profiles()
    selected_profile = st.selectbox("Selecione um Perfil Existente", options=[""] + profiles, index=0, format_func=lambda x: "Selecione para carregar ou apagar..." if x == "" else x)

    if selected_profile:
        if st.button(f"Apagar Perfil '{selected_profile}'", type="secondary"):
            delete_profile(selected_profile)
            if st.session_state.get('active_profile') == selected_profile:
                keys_to_clear = ['jira_client', 'active_profile', 'projects']
                for key in keys_to_clear:
                    if key in st.session_state: del st.session_state[key]
            st.success(f"Perfil '{selected_profile}' apagado."); st.rerun()

    with st.form("credential_form"):
        st.markdown("**Criar ou Atualizar Perfil:**")
        
        profile_name = st.text_input("Nome do Perfil", value=selected_profile or "")
        creds = get_user_credentials(profile_name) if profile_name and not selected_profile else get_user_credentials(selected_profile) if selected_profile else {}
        creds = creds or {}
        
        col1, col2 = st.columns(2)
        jira_server = col1.text_input("URL do Servidor Jira", value=creds.get('jira_url', ''))
        user_email = col2.text_input("Email do Usuário Jira", value=creds.get('jira_email', ''))
        
        if creds.get('encrypted_token'):
            st.info("🔑 Um token já está guardado. Preencha o campo abaixo apenas se quiser alterá-lo.")
            api_token = st.text_input("Novo Token da API Jira (opcional)", type="password")
        else:
            api_token = st.text_input("Token da API Jira", type="password")
            
        submitted = st.form_submit_button("Guardar e Conectar com este Perfil", type="primary", use_container_width=True)
        if submitted:
            if not all([profile_name, jira_server, user_email]): st.error("Por favor, preencha o Nome do Perfil, URL e Email.")
            else:
                final_token = api_token if api_token else decrypt_token(creds['encrypted_token']) if creds.get('encrypted_token') else None
                if not final_token: st.error("O Token da API é obrigatório para um novo perfil ou para uma atualização.")
                else:
                    with st.spinner(f"A conectar com o perfil '{profile_name}'..."):
                        client = connect_to_jira(jira_server, user_email, final_token)
                        if client:
                            projects = get_projects(client)
                            if projects:
                                encrypted_token = encrypt_token(final_token); save_user_credentials(profile_name, jira_server, user_email, encrypted_token)
                                st.session_state.jira_client = client; st.session_state.active_profile = profile_name; st.session_state.projects = projects
                                st.session_state['available_standard_fields'] = AVAILABLE_STANDARD_FIELDS
                                st.success(f"Conexão bem-sucedida! {len(projects)} projetos encontrados."); st.rerun()
                            else: st.warning("Conexão bem-sucedida, mas nenhum projeto foi encontrado. Verifique as permissões da sua conta no Jira.")
                        else: st.error("Falha na conexão. Verifique se a URL, Email e Token estão corretos.")

st.divider()

# --- ABAS PARA OUTRAS CONFIGURAÇÕES ---
st.header("Configurações Avançadas")
tab1, tab2, tab3 = st.tabs(["Mapeamento de Status", "Campos Padrão", "Campos Personalizados"])

with tab1:
    st.subheader("Mapeamento de Status do Workflow")
    st.markdown("Defina os nomes dos status que correspondem a estados iniciais (backlog) e finais (concluído). **Use letras minúsculas e separe por vírgula.**")
    status_mapping = load_config(STATUS_MAPPING_FILE, {})
    initial_states_str = st.text_area("Nomes de Status Iniciais", value=", ".join(status_mapping.get('initial', DEFAULT_INITIAL_STATES)))
    done_states_str = st.text_area("Nomes de Status Finais", value=", ".join(status_mapping.get('done', DEFAULT_DONE_STATES)))
    if st.button("Salvar Mapeamento de Status"):
        new_initial = [s.strip().lower() for s in initial_states_str.split(',') if s.strip()]; new_done = [s.strip().lower() for s in done_states_str.split(',') if s.strip()]
        save_config({'initial': new_initial, 'done': new_done}, STATUS_MAPPING_FILE); st.success("Mapeamento de status guardado!")

with tab2:
    st.subheader("Campos Padrão do Jira")
    st.markdown("Selecione quais campos padrão do Jira você deseja que apareçam como opções na Análise Dinâmica.")
    selected_standard_fields = load_config(STANDARD_FIELDS_FILE, [])
    toggles = {}
    for name, field_id in AVAILABLE_STANDARD_FIELDS.items():
        toggles[name] = st.toggle(name, value=(name in selected_standard_fields), key=f"std_{field_id}")
    if st.button("Salvar Seleção de Campos Padrão"):
        new_selection = [name for name, toggled in toggles.items() if toggled]; save_config(new_selection, STANDARD_FIELDS_FILE)
        st.success("Seleção de campos padrão guardada!"); st.rerun()

with tab3:
    st.subheader("Campos Personalizados (Custom Fields)")
    st.markdown("Adicione aqui campos específicos do seu Jira que não estão na lista acima.")
    custom_fields = load_config(CUSTOM_FIELDS_FILE, [])
    if custom_fields:
        for i, field in enumerate(custom_fields):
            col1, col2, col3 = st.columns([2, 2, 1]); col1.text_input("Nome", value=field['name'], key=f"name_{i}", disabled=True); col2.text_input("ID", value=field['id'], key=f"id_{i}", disabled=True)
            if col3.button("Remover", key=f"del_{field['id']}"): custom_fields.pop(i); save_config(custom_fields, CUSTOM_FIELDS_FILE); st.rerun()
        st.markdown("---")
    with st.form("new_custom_field_form", clear_on_submit=True):
        st.markdown("**Adicionar Novo Campo:**"); col1, col2 = st.columns(2)
        new_name = col1.text_input("Nome do Campo"); new_id = col2.text_input("ID do Campo (ex: customfield_10050)")
        if st.form_submit_button("➕ Adicionar Campo"):
            if new_name and new_id:
                if any(f['id'] == new_id for f in custom_fields): st.error(f"O ID '{new_id}' já existe.")
                else: custom_fields.append({'name': new_name, 'id': new_id}); save_config(custom_fields, CUSTOM_FIELDS_FILE); st.success(f"Campo '{new_name}' adicionado!"); st.rerun()
            else: st.error("Por favor, preencha o Nome e o ID.")
# 1_⚙️_Configurações.py
import streamlit as st
from jira_connector import connect_to_jira, get_projects
import json
import os
from config import *
from security import (
    save_user_credentials, get_user_credentials, 
    get_all_profiles, encrypt_token, decrypt_token,
    delete_profile
)

st.set_page_config(page_title="Configurações", page_icon="⚙️", layout="wide")
st.session_state['available_standard_fields'] = AVAILABLE_STANDARD_FIELDS

def load_config(file_path, default_value):
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            try: return json.load(f)
            except json.JSONDecodeError: return default_value
    return default_value

def save_config(data, file_path):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

def load_config(file_path, default_value):
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            try: return json.load(f)
            except json.JSONDecodeError: return default_value
    return default_value

def save_config(data, file_path):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

# --- Lógica da Página ---
with st.sidebar:
    try:
        st.image("images/gauge-logo.png", width=150)
    except Exception:
        st.write("Gauge Metrics") # Fallback se a imagem não carregar

st.header("⚙️ Configurações e Conexão")

st.header("👤 Perfis de Conexão")
st.markdown("Crie ou selecione um perfil para guardar e gerir as suas credenciais do Jira de forma segura e individual.")

# --- Seleção e Gestão de Perfis ---
profiles = get_all_profiles()
selected_profile = st.selectbox("Selecione um Perfil Existente", options=profiles, index=None, placeholder="Escolha um perfil...")

if selected_profile:
    if st.button(f"Apagar Perfil '{selected_profile}'", type="secondary"):
        delete_profile(selected_profile)
        st.success(f"Perfil '{selected_profile}' apagado.")
        # Limpa o estado da conexão se o perfil ativo for apagado
        if st.session_state.get('active_profile') == selected_profile:
            for key in ['jira_client', 'active_profile']:
                if key in st.session_state:
                    del st.session_state[key]
        st.rerun()

# --- Formulário para Criar/Atualizar um Perfil ---
with st.form("credential_form"):
    st.subheader("Criar ou Atualizar Perfil")
    
    profile_name = st.text_input("Nome do Perfil (ex: seu nome ou nome do projeto)", value=selected_profile or "")
    
    # Carrega os dados se um perfil for selecionado
    creds = get_user_credentials(profile_name) if profile_name else None
    
    jira_server = st.text_input("URL do Servidor Jira", value=creds['jira_url'] if creds else "")
    user_email = st.text_input("Email do Usuário Jira", value=creds['jira_email'] if creds else "")
    
    # Se já existem credenciais, não mostramos o token, apenas um campo para o alterar
    if creds and creds.get('encrypted_token'):
        st.info("🔑 Um token já está guardado para este perfil. Preencha o campo abaixo apenas se quiser alterá-lo.")
        api_token = st.text_input("Novo Token da API Jira (opcional)", type="password")
    else:
        api_token = st.text_input("Token da API Jira", type="password")
        
    submitted = st.form_submit_button("Guardar e Conectar com este Perfil")

    if submitted:
        if not all([profile_name, jira_server, user_email]):
            st.error("Por favor, preencha o Nome do Perfil, URL e Email.")
        else:
            final_token = api_token # Usa o novo token se fornecido
            if not api_token and creds and creds.get('encrypted_token'):
                final_token = decrypt_token(creds['encrypted_token']) # Reutiliza o token antigo se nenhum novo for fornecido
            
            if not final_token:
                st.error("O Token da API é obrigatório para um novo perfil ou para uma atualização.")
            else:
                with st.spinner("A testar a conexão e a guardar as credenciais..."):
                    client = connect_to_jira(jira_server, user_email, final_token)
                    if client:
                        encrypted_token = encrypt_token(final_token)
                        save_user_credentials(profile_name, jira_server, user_email, encrypted_token)
                        
                        st.session_state.jira_client = client
                        st.session_state.active_profile = profile_name
                        st.success(f"Conectado com sucesso como '{profile_name}'!")
                        st.switch_page("pages/2_📊_Métricas_de_Fluxo.py")
                    else:
                        st.error("Falha na conexão. Verifique as credenciais.")

# --- Status da Conexão Atual ---
st.divider()
if 'jira_client' in st.session_state and st.session_state.get('active_profile'):
    st.success(f"Você está conectado com o perfil: **{st.session_state.active_profile}**")
else:
    st.warning("Nenhum perfil conectado nesta sessão.")

st.divider()
st.header("2. Gestão de Campos e Status para Análise")

# SEÇÃO DE MAPEAMENTO DE STATUS
with st.container(border=True):
    st.subheader("Mapeamento de Status do Workflow")
    st.markdown("Defina os nomes dos status que correspondem a estados iniciais (backlog) e finais (concluído). **Use letras minúsculas e separe por vírgula.**")
    status_mapping = load_config(STATUS_MAPPING_FILE, {})
    initial_states_str = st.text_area("Nomes de Status Iniciais (Backlog)", value=", ".join(status_mapping.get('initial', DEFAULT_INITIAL_STATES)))
    done_states_str = st.text_area("Nomes de Status Finais (Concluído)", value=", ".join(status_mapping.get('done', DEFAULT_DONE_STATES)))
    if st.button("Salvar Mapeamento de Status"):
        new_initial = [s.strip().lower() for s in initial_states_str.split(',') if s.strip()]
        new_done = [s.strip().lower() for s in done_states_str.split(',') if s.strip()]
        save_config({'initial': new_initial, 'done': new_done}, STATUS_MAPPING_FILE); st.success("Mapeamento de status guardado!")

# SEÇÃO DE CAMPOS PADRÃO
with st.container(border=True):
    st.subheader("Campos Padrão do Jira")
    st.markdown("Selecione quais campos padrão do Jira você deseja que apareçam como opções na Análise Dinâmica.")
    selected_standard_fields = load_config(STANDARD_FIELDS_FILE, [])
    toggles = {}
    for name, field_id in AVAILABLE_STANDARD_FIELDS.items():
        toggles[name] = st.toggle(name, value=(name in selected_standard_fields), key=f"std_{field_id}")
    if st.button("Salvar Seleção de Campos Padrão"):
        new_selection = [name for name, toggled in toggles.items() if toggled]; save_config(new_selection, STANDARD_FIELDS_FILE)
        st.success("Seleção de campos padrão guardada!"); st.rerun()

# SEÇÃO DE CAMPOS PERSONALIZADOS
with st.container(border=True):
    st.subheader("Campos Personalizados (Custom Fields)")
    st.markdown("Adicione aqui campos específicos do seu Jira que não estão na lista acima.")
    custom_fields = load_config(CUSTOM_FIELDS_FILE, [])
    if custom_fields:
        st.markdown("**Campos Atuais:**")
        for i, field in enumerate(custom_fields):
            col1, col2, col3 = st.columns([2, 2, 1])
            col1.text_input("Nome Amigável", value=field['name'], key=f"name_{i}", disabled=True); col2.text_input("ID do Campo", value=field['id'], key=f"id_{i}", disabled=True)
            if col3.button("Remover", key=f"del_{field['id']}"): custom_fields.pop(i); save_config(custom_fields, CUSTOM_FIELDS_FILE); st.rerun()
        st.markdown("---")
    with st.form("new_custom_field_form", clear_on_submit=True):
        st.subheader("Adicionar Novo Campo Personalizado")
        col1, col2 = st.columns(2)
        new_name = col1.text_input("Nome do Campo (como aparecerá nos gráficos)"); new_id = col2.text_input("ID do Campo (ex: customfield_10050)")
        if st.form_submit_button("➕ Adicionar Campo"):
            if new_name and new_id:
                if any(f['id'] == new_id for f in custom_fields): st.error(f"O campo com ID '{new_id}' já existe.")
                else: custom_fields.append({'name': new_name, 'id': new_id}); save_config(custom_fields, CUSTOM_FIELDS_FILE); st.success(f"Campo '{new_name}' adicionado!"); st.rerun()
            else: st.error("Por favor, preencha o Nome e o ID do campo.")
# 1_⚙️_Configurações.py
import streamlit as st
from jira_connector import connect_to_jira, get_projects
import json
import os
from config import *

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

# Bloco de status de conexão amigável
if 'jira_client' in st.session_state and st.session_state.jira_client is not None:
    with st.container(border=True):
        col1, col2 = st.columns([1, 4])
        with col1:
            st.success("Conectado", icon="✅")
        with col2:
            st.markdown(f"**Utilizador:** `{st.secrets.get('JIRA_USER_EMAIL', 'N/A')}`")
            st.markdown(f"**Servidor:** `{st.session_state.jira_client._options['server']}`")
    st.info("Tudo pronto! Pode começar a navegar pelas páginas de análise na barra lateral.")
else:
    st.warning("Você não está conectado. Por favor, conecte-se abaixo para continuar.")

st.divider()

# Formulário de Conexão
with st.container(border=True):
    st.subheader("1. Conexão com o Jira")
    st.markdown("Suas credenciais são carregadas do arquivo `.streamlit/secrets.toml` e podem ser alteradas abaixo.")
    
    jira_server = st.text_input("URL do Servidor Jira", value=st.secrets.get("JIRA_SERVER", ""))
    user_email = st.text_input("Email do Usuário Jira", value=st.secrets.get("JIRA_USER_EMAIL", ""))
    api_token = st.text_input("Token da API Jira", type="password", value=st.secrets.get("JIRA_API_TOKEN", ""))

    if st.button("Conectar ao Jira"):
        if not all([jira_server, user_email, api_token]):
            st.error("Por favor, preencha todas as credenciais.")
        else:
            with st.spinner("Conectando..."):
                client = connect_to_jira(jira_server, user_email, api_token)
                if client:
                    st.session_state.jira_client = client
                    st.session_state.projects = get_projects(client)
                    st.success("Conectado com sucesso! Redirecionando para as métricas...")
                    st.switch_page("pages/2_📊_Métricas_de_Fluxo.py")
                else:
                    st.error("Falha na conexão. Verifique suas credenciais e a URL do servidor.")

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
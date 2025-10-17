# pages/8_🔗_Conexões_Jira.py (VERSÃO CORRIGIDA E FINAL)

import streamlit as st
from security import (
    find_user, 
    save_user_connections, 
    encrypt_token, 
    decrypt_token, 
    save_last_active_connection,
    delete_jira_connection,
    deactivate_active_connection
)
# --- 1: Importar a função get_projects ---
from jira_connector import connect_to_jira, validate_jira_connection, get_projects
import uuid
import time
from pathlib import Path

st.set_page_config(page_title="Conexões Jira", page_icon="🔗", layout="wide")

st.header("🔗 Gerir Conexões Jira", divider='rainbow')

st.markdown("""
<style>
    div[data-testid="stButton"] > button:has(span:contains('Apagar')) {
        background-color: #D32F2F; color: white; border: 1px solid #D32F2F;
    }
    div[data-testid="stButton"] > button:has(span:contains('Apagar')):hover {
        background-color: #B71C1C; border: 1px solid #B71C1C; color: white;
    }
    div[data-testid="stButton"] > button:has(span:contains('Apagar')):focus {
        box-shadow: 0 0 0 0.2rem rgba(211, 47, 47, 0.5) !important;
    }
</style>
""", unsafe_allow_html=True)

# --- Verificações de Segurança ---
if 'email' not in st.session_state:
    st.warning("⚠️ Por favor, faça login para aceder."); st.page_link("1_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑"); st.stop()

if 'invalid_connection_id' in st.session_state and st.session_state.invalid_connection_id:
    # Obtém a razão específica do erro da sessão, ou usa uma mensagem padrão
    error_reason = st.session_state.get('connection_error_reason', 'A sua conexão Jira que estava ativa é inválida ou expirou.')
    
    st.error(
        f"**Atenção:** {error_reason}\n\n"
        "Por favor, edite a conexão com um novo token de API, ative outra, ou crie uma nova.",
        icon="💔"
    )

user_data = find_user(st.session_state['email'])
connections = user_data.get('jira_connections', [])
active_connection_id = user_data.get('last_active_connection_id')

with st.sidebar:
    project_root = Path(__file__).parent.parent
    logo_path = project_root / "images" / "gauge-logo.svg"
    try:
        st.logo(str(logo_path), size="large")
    except (FileNotFoundError, AttributeError):
        st.write("Gauge Metrics") 

    if st.session_state.get("email"):
        st.markdown(f"🔐 Logado como: **{st.session_state['email']}**")
    else:
        st.info("⚠️ Usuário não conectado!")

    if st.button("Logout", width='stretch', type='secondary'):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.switch_page("1_🔑_Autenticação.py")

# --- Adicionar Nova Conexão ---
st.subheader("Adicionar Nova Conexão")
with st.form("new_connection_form", clear_on_submit=True):
    name = st.text_input("Nome da Conexão*", placeholder="Ex: Jira da Empresa X")
    url = st.text_input("URL do Jira*", placeholder="https://sua-empresa.atlassian.net")
    email = st.text_input("E-mail do Jira*", placeholder="seu-email@empresa.com")
    token = st.text_input("Token de API*", type="password", help="O seu token de API, não a sua senha.")
    
    if st.form_submit_button("Testar e Salvar Conexão", type="primary", use_container_width=True):
        if all([name, url, email, token]):
            with st.spinner("A testar a conexão..."):
                client = connect_to_jira(url, email, token)
                if client and validate_jira_connection(client):
                    new_conn = {
                        "id": str(uuid.uuid4()), "name": name, "jira_url": url,
                        "jira_email": email, "encrypted_token": encrypt_token(token)
                    }
                    connections.append(new_conn)
                    save_user_connections(st.session_state['email'], connections)
                    st.success(f"Conexão '{name}' salva e validada com sucesso!")
                    time.sleep(1); st.rerun()
                else:
                    st.error("Falha na conexão. Verifique se a URL, o e-mail e o token de API estão corretos.")
        else:
            st.warning("Por favor, preencha todos os campos.")

st.divider()

# --- Listar Conexões Existentes ---
st.subheader("Conexões Guardadas")
if not connections:
    st.info("Nenhuma conexão Jira foi guardada ainda.")
else:
    for i, conn in enumerate(connections):
        conn_id = conn['id']
        is_active = (conn_id == active_connection_id)
        is_invalid = (conn_id == st.session_state.get('invalid_connection_id'))

        with st.container(border=True):
            col1, col2, col3 = st.columns([0.6, 0.2, 0.2])
            with col1:
                label = conn['name']
                if is_invalid:
                    st.markdown(f"**{label}** ⚠️ <span style='color: #d32f2f; font-size: 0.9em;'>(Inválida / Requer Atenção)</span>", unsafe_allow_html=True)
                elif is_active:
                    st.markdown(f"**{label}** 🟢 <span style='color: #28a745; font-size: 0.9em;'>(Ativa)</span>", unsafe_allow_html=True)
                else:
                    st.markdown(f"**{label}**")
                st.caption(f"URL: {conn['jira_url']} | E-mail: {conn['jira_email']}")
            
            with col2:
                if is_active:
                    if st.button("Desativar", key=f"deactivate_{conn_id}", use_container_width=True):
                        deactivate_active_connection(st.session_state['email'])
                        if 'jira_client' in st.session_state: del st.session_state['jira_client']
                        if 'projects' in st.session_state: del st.session_state['projects'] # Limpa também os projetos
                        st.success(f"Conexão '{conn['name']}' desativada."); time.sleep(1); st.rerun()
                else:
                    if st.button("Ativar", key=f"activate_{conn_id}", use_container_width=True, type="primary"):
                        with st.spinner("A ativar e validar a nova conexão..."):
                            save_last_active_connection(st.session_state['email'], conn_id)
                            
                            conn_details = conn 
                            token = decrypt_token(conn_details['encrypted_token'])
                            client = connect_to_jira(conn_details['jira_url'], conn_details['jira_email'], token)
                            
                            if 'connection_error_reason' in st.session_state:
                                del st.session_state['connection_error_reason']

                            if client and validate_jira_connection(client):
                                st.session_state['jira_client'] = client
                                st.session_state['active_connection'] = conn_details
                                
                                # --- 2: Carrega os projetos para a sessão ---
                                st.session_state['projects'] = get_projects(client)
                                
                                if 'invalid_connection_id' in st.session_state: del st.session_state['invalid_connection_id']
                                st.success(f"Conexão '{conn['name']}' ativada com sucesso!")
                            else:
                                st.session_state['invalid_connection_id'] = conn_id
                                deactivate_active_connection(st.session_state['email'])
                                st.error("Falha ao validar esta conexão. Verifique os detalhes e o token.")
                        time.sleep(1); st.rerun()

            with col3:
                if st.button("Apagar", key=f"delete_{conn_id}", use_container_width=True):
                    delete_jira_connection(conn_id)
                    if is_active: deactivate_active_connection(st.session_state['email'])
                    if st.session_state.get('invalid_connection_id') == conn_id: del st.session_state['invalid_connection_id']
                    if 'connection_error_reason' in st.session_state:
                        del st.session_state['connection_error_reason']
                    st.success("Conexão apagada!"); time.sleep(1); st.rerun()

            with st.expander("Editar Conexão"):
                with st.form(f"edit_form_{conn_id}"):
                    st.text_input("Nome da Conexão", value=conn['name'], key=f"name_{conn_id}")
                    st.text_input("URL do Jira", value=conn['jira_url'], key=f"url_{conn_id}")
                    st.text_input("E-mail do Jira", value=conn['jira_email'], key=f"email_{conn_id}")
                    st.text_input("Novo Token de API (Opcional)", type="password", help="Preencha apenas se quiser atualizar o token.", key=f"token_{conn_id}")
                    if st.form_submit_button("Salvar Alterações", type="primary", use_container_width=True):
                        connections[i]['name'] = st.session_state[f"name_{conn_id}"]
                        connections[i]['jira_url'] = st.session_state[f"url_{conn_id}"]
                        connections[i]['jira_email'] = st.session_state[f"email_{conn_id}"]
                        new_token = st.session_state[f"token_{conn_id}"]
                        if new_token: connections[i]['encrypted_token'] = encrypt_token(new_token)
                        save_user_connections(st.session_state['email'], connections)
                        st.success("Alterações salvas!"); time.sleep(1); st.rerun()
# pages/8_🔗_Conexões_Jira.py

import streamlit as st
from security import *
from jira_connector import connect_to_jira, validate_jira_connection
import uuid
import time
from pathlib import Path

st.set_page_config(page_title="Conexões Jira", page_icon="🔗", layout="wide")

st.header("🔗 Gerir Conexões Jira", divider='rainbow')

# --- BLOCO 1: ALERTA GLOBAL DE CONEXÃO INVÁLIDA ---
# Verifica se o utilizador foi redirecionado para esta página devido a uma conexão inválida
if 'invalid_connection_id' in st.session_state and st.session_state.invalid_connection_id:
    st.error(
        "A sua conexão Jira que estava ativa é inválida, expirou ou não tem as permissões necessárias. "
        "Por favor, edite-a com um novo token de API, ative outra conexão ou crie uma nova.",
        icon="💔"
    )

# --- Verificações de Segurança ---
if 'email' not in st.session_state:
    st.warning("⚠️ Por favor, faça login para acessar."); st.page_link("1_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑"); st.stop()

if check_session_timeout():
    st.warning(f"Sua sessão expirou por inatividade de {SESSION_TIMEOUT_MINUTES} minutos. Por favor, faça login novamente.")
    st.page_link("1_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑")
    st.stop()
    
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
        
user_data = find_user(st.session_state['email'])
connections = user_data.get('jira_connections', [])
active_connection_id = user_data.get('active_jira_connection')

# --- Adicionar Nova Conexão ---
st.subheader("Adicionar Nova Conexão")
with st.form("new_connection_form"):
    st.text_input("Nome da Conexão*", placeholder="Ex: Jira da Empresa X", key="new_conn_name")
    st.text_input("URL do Jira*", placeholder="https://sua-empresa.atlassian.net", key="new_conn_url")
    st.text_input("E-mail do Jira*", placeholder="seu-email@empresa.com", key="new_conn_email")
    st.text_input("Token de API*", type="password", help="O seu token de API, não a sua senha.", key="new_conn_token")
    
    if st.form_submit_button("Testar e Salvar Conexão", type="primary"):
        name = st.session_state.new_conn_name
        url = st.session_state.new_conn_url
        email = st.session_state.new_conn_email
        token = st.session_state.new_conn_token

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
        # --- BLOCO 2: VERIFICA SE A CONEXÃO ATUAL É A INVÁLIDA ---
        is_invalid = (conn_id == st.session_state.get('invalid_connection_id'))

        # Constrói o rótulo do expander dinamicamente para incluir os ícones
        label = conn['name']
        if is_invalid:
            label = f"⚠️ {label} (Inválida / Requer Atenção)"
        elif is_active:
            label = f"🟢 {label} (Ativa)"

        with st.expander(label):
            with st.form(f"form_{conn_id}"):
                st.text_input("Nome da Conexão", value=conn['name'], key=f"name_{conn_id}")
                st.text_input("URL do Jira", value=conn['jira_url'], key=f"url_{conn_id}")
                st.text_input("E-mail do Jira", value=conn['jira_email'], key=f"email_{conn_id}")
                st.text_input("Novo Token de API (Opcional)", type="password", help="Preencha apenas se quiser atualizar o token.", key=f"token_{conn_id}")

                c1, c2, c3 = st.columns([2, 1, 1])
                with c1:
                    if st.form_submit_button("Ativar Conexão", type="primary", disabled=is_active):
                        save_last_active_connection(st.session_state['email'], conn_id)

                        if 'invalid_connection_id' in st.session_state:
                            del st.session_state['invalid_connection_id']
                        st.success(f"Conexão '{conn['name']}' ativada. A aplicação irá reiniciar.")
                        time.sleep(2)
                        st.switch_page("1_🔑_Autenticação.py")
                with c2:
                    if st.form_submit_button("Salvar Alterações"):
                        connections[i]['name'] = st.session_state[f"name_{conn_id}"]
                        connections[i]['jira_url'] = st.session_state[f"url_{conn_id}"]
                        connections[i]['jira_email'] = st.session_state[f"email_{conn_id}"]
                        new_token = st.session_state[f"token_{conn_id}"]
                        if new_token:
                            connections[i]['encrypted_token'] = encrypt_token(new_token)
                        save_user_connections(st.session_state['email'], connections)
                        st.success("Alterações salvas!")
                        time.sleep(1); st.rerun()
                with c3:
                    if st.form_submit_button("Apagar"):
                        delete_jira_connection(conn_id)

                        if st.session_state.get('invalid_connection_id') == conn_id:
                            del st.session_state['invalid_connection_id']
                        st.success("Conexão apagada!")
                        time.sleep(1); st.rerun()
# pages/10_👑_Administração.py

import streamlit as st
from security import *
from pathlib import Path
import pandas as pd
from security import save_global_smtp_configs, get_global_smtp_configs, validate_smtp_connection, encrypt_token

st.set_page_config(page_title="Administração", page_icon="👑", layout="wide")
st.header("👑 Painel de Administração", divider='rainbow')

# --- Bloco de Autenticação e Conexão ---
if 'email' not in st.session_state:
    st.warning("⚠️ Por favor, faça login para acessar."); st.page_link("1_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑"); st.stop()
if 'jira_client' not in st.session_state:
    st.warning("⚠️ Nenhuma conexão Jira ativa."); st.page_link("pages/8_🔗_Conexões_Jira.py", label="Ativar uma Conexão", icon="🔗"); st.stop()

# --- VERIFICAÇÃO DE ADMIN ---
try:
    ADMIN_EMAILS = st.secrets.get("app_settings", {}).get("ADMIN_EMAILS", [])
except Exception as e:
    st.error(f"Erro ao ler a lista de administradores do ficheiro de segredos: {e}")
    ADMIN_EMAILS = []

if st.session_state['email'] not in ADMIN_EMAILS:
    st.error("🚫 Acesso Negado. Esta página é reservada para administradores.");
    st.stop()

# --- Se chegou até aqui, o utilizador é um admin. ---
configs = get_global_configs()

# --- BARRA LATERAL ---
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

    if st.button("Logout", use_container_width=True, type='secondary'):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.switch_page("1_🔑_Autenticação.py")

# --- Interface Principal com Abas ---
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🌐 Domínios", 
    "👥 Utilizadores", 
    "📖 Playbooks", 
    "💎 Competências", 
    "🎯 Metas", 
    "📧 Configurar E-mail"
])

with tab1:
    st.subheader("Domínios com Permissão de Registro")
    with st.container(border=True):
        allowed_domains = configs.get('allowed_domains', [])
        
        for domain in list(allowed_domains):
            col1, col2 = st.columns([4, 1])
            col1.text(domain)
            if col2.button("Remover", key=f"del_{domain}", use_container_width=True):
                allowed_domains.remove(domain)
                configs['allowed_domains'] = allowed_domains
                save_global_configs(configs)
                get_global_configs.clear() # <<-- CORREÇÃO APLICADA
                st.rerun()

        with st.form("new_domain_form", clear_on_submit=True):
            new_domain = st.text_input("Adicionar novo domínio permitido:")
            if st.form_submit_button("Adicionar Domínio", type="primary"):
                if new_domain and new_domain not in allowed_domains:
                    allowed_domains.append(new_domain)
                    configs['allowed_domains'] = allowed_domains
                    save_global_configs(configs)
                    get_global_configs.clear() # <<-- CORREÇÃO APLICADA
                    st.rerun()

with tab2:
    st.subheader("Utilizadores Registados no Sistema")

    # Bloco para exibir a senha temporária após o reset
    if 'temp_password_info' in st.session_state:
        user_email = st.session_state.temp_password_info['email']
        temp_pass = st.session_state.temp_password_info['password']
        st.success(f"Senha para **{user_email}** redefinida com sucesso!", icon="🔑")
        st.code(temp_pass, language=None)
        st.warning("Por favor, copie esta senha e envie-a ao utilizador por um canal seguro. Ela só será exibida uma vez.")
        del st.session_state.temp_password_info
        st.divider()

    all_users = list(get_users_collection().find({}))
    users_to_display = [user for user in all_users if user['email'] != st.session_state['email']]
    
    if not users_to_display:
        st.info("Não há outros utilizadores no sistema para gerir.")
    else:
        for user in users_to_display:
            with st.container(border=True):
                col1, col2, col3 = st.columns([2, 1, 1])
                col1.text(user['email'])
                
                with col2:
                    # Lógica do botão para resetar e mostrar a senha
                    if st.button("Resetar Senha", key=f"reset_pass_{user['_id']}", use_container_width=True):
                        temp_password = generate_temporary_password()
                        hashed_password = get_password_hash(temp_password)
                        update_user_password(user['email'], hashed_password)
                        
                        # Guarda a senha na memória da sessão para ser exibida no topo
                        st.session_state.temp_password_info = {'email': user['email'], 'password': temp_password}
                        st.rerun()

                with col3:
                    if st.button("Remover Utilizador", key=f"del_user_{user['_id']}", use_container_width=True, type="secondary"):
                        delete_user(user['email'])
                        st.success(f"Utilizador '{user['email']}' e todos os seus dados foram removidos.")
                        st.rerun()

with tab3:
    st.header("Gestão de Conteúdo dos Playbooks")
    playbooks = configs.get('playbooks', {})

    with st.expander("➕ Adicionar Novo Tema de Playbook"):
        with st.form("new_playbook_form", clear_on_submit=True):
            new_theme_name = st.text_input("Nome do Novo Tema*")
            new_theme_content = st.text_area("Conteúdo (suporta Markdown)*", height=300)
            if st.form_submit_button("Adicionar Tema", type="primary"):
                if new_theme_name and new_theme_content:
                    configs['playbooks'][new_theme_name] = new_theme_content
                    save_global_configs(configs)
                    get_global_configs.clear() # <<-- CORREÇÃO APLICADA
                    st.rerun()
    
    st.divider()
    st.subheader("Editar ou Remover Tema Existente")
    if playbooks:
        theme_to_edit = st.selectbox("Selecione um tema para gerir:", options=list(playbooks.keys()))
        if theme_to_edit:
            edited_content = st.text_area("Conteúdo:", value=playbooks.get(theme_to_edit, ""), height=400)
            c1, c2 = st.columns(2)
            if c1.button("Salvar Alterações", use_container_width=True, key=f"save_{theme_to_edit}"):
                configs['playbooks'][theme_to_edit] = edited_content
                save_global_configs(configs)
                get_global_configs.clear() # <<-- CORREÇÃO APLICADA
                st.rerun()
            if c2.button("❌ Remover Tema", use_container_width=True, type="secondary", key=f"del_{theme_to_edit}"):
                del configs['playbooks'][theme_to_edit]
                save_global_configs(configs)
                get_global_configs.clear() # <<-- CORREÇÃO APLICADA
                st.rerun()

with tab4:
    st.header("Framework de Competências")
    framework_data = configs.get('competency_framework', {})
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🛠️ Hard Skills")
        edited_hard_skills = st.data_editor(pd.DataFrame(framework_data.get('hard_skills', [])), num_rows="dynamic")
    with col2:
        st.subheader("🧠 Soft Skills")
        edited_soft_skills = st.data_editor(pd.DataFrame(framework_data.get('soft_skills', [])), num_rows="dynamic")
        
    if st.button("Salvar Framework de Competências", type="primary", use_container_width=True):
        configs['competency_framework'] = {
            'hard_skills': edited_hard_skills.to_dict('records'),
            'soft_skills': edited_soft_skills.to_dict('records')
        }
        save_global_configs(configs)
        get_global_configs.clear() # <<-- CORREÇÃO APLICADA
        st.success("Framework salvo!")
        st.rerun()

with tab5:
    st.subheader("Metas de KPIs Globais")
    with st.form("kpi_targets_form"):
        target_margin = st.number_input("Meta da Margem de Contribuição (%)", value=configs.get('target_contribution_margin', 25.0))
        if st.form_submit_button("Salvar Metas", use_container_width=True):
            configs['target_contribution_margin'] = target_margin
            save_global_configs(configs)
            get_global_configs.clear() # <<-- CORREÇÃO APLICADA
            st.success("Metas salvas!")
            st.rerun()

with tab6:
    st.subheader("Configuração Global de Envio de E-mail")
    st.info("Estas credenciais serão usadas por toda a aplicação para enviar e-mails (ex: recuperação de senha).")

    current_smtp_configs = get_global_smtp_configs() or {}
    current_provider = current_smtp_configs.get('provider', 'SendGrid')

    provider_options = ["SendGrid", "Gmail (SMTP)"]
    provider_index = provider_options.index(current_provider) if current_provider in provider_options else 0
    email_provider = st.radio(
        "Selecione o provedor de e-mail do sistema:",
        provider_options,
        horizontal=True,
        index=provider_index
    )

    with st.form("global_smtp_config_form"):
        from_email = ""
        credential = ""

        if email_provider == 'SendGrid':
            if current_smtp_configs.get('api_key_encrypted'):
                st.success("Uma chave de API do SendGrid já está configurada.", icon="✅")

            from_email = st.text_input("E-mail de Origem (SendGrid)", value=current_smtp_configs.get('from_email', ''))
            credential = st.text_input("SendGrid API Key", type="password", placeholder="Insira uma nova chave para salvar ou alterar")

        # Adicione aqui a lógica para o Gmail (SMTP) se necessário

        if st.form_submit_button("Validar e Salvar Credenciais Globais", use_container_width=True, type="primary"):
            if from_email and credential:
                with st.spinner("A validar as suas credenciais..."):
                    is_valid, message = validate_smtp_connection(email_provider, from_email, credential)

                if is_valid:
                    encrypted_credential = encrypt_token(credential)
                    configs_to_save = {
                        'provider': 'SendGrid', 
                        'from_email': from_email, 
                        'api_key_encrypted': encrypted_credential
                    }
                    save_global_smtp_configs(configs_to_save)
                    st.success(message + " As credenciais globais foram salvas com sucesso!")
                    st.rerun()
                else:
                    st.error(message)
            else:
                st.error("Por favor, preencha todos os campos para validar e salvar.")
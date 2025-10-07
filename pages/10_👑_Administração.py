# pages/10_👑_Administração.py

import streamlit as st
from security import *
from pathlib import Path
import pandas as pd
from config import SESSION_TIMEOUT_MINUTES
from streamlit_quill import st_quill
import uuid

st.set_page_config(page_title="Administração", page_icon="👑", layout="wide")
st.header("👑 Painel de Administração", divider='rainbow')

# --- Bloco de Autenticação e Conexão ---
if 'email' not in st.session_state:
    st.warning("⚠️ Por favor, faça login para acessar."); st.page_link("1_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑"); st.stop()

if check_session_timeout():
    st.warning(f"Sua sessão expirou por inatividade de {SESSION_TIMEOUT_MINUTES} minutos. Por favor, faça login novamente.")
    st.page_link("1_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑")
    st.stop()

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

configs = get_global_configs()

def force_hub_reload():
    """Remove a flag de dados carregados do hub para forçar o recarregamento na próxima visita."""
    if 'hub_data_loaded' in st.session_state:
        del st.session_state['hub_data_loaded']

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

# --- Interface Principal com Abas Reorganizadas ---
main_tab_content, main_tab_system = st.tabs(["**📄 Gestão de Conteúdo**", "**⚙️ Configurações do Sistema**"])

with main_tab_content:
    st.subheader("Gestão de Conteúdo do Product Hub")
    
    content_tab_playbooks, content_tab_competencies, content_tab_roles = st.tabs([
        "📖 Playbooks", 
        "💎 Competências", 
        "👨‍🔬 Papéis"
    ])

    with content_tab_playbooks:
        st.markdown("##### Gestão de Conteúdo dos Playbooks")
        playbooks = configs.get('playbooks', {})
        
        toolbar_options = [[{'header': [1, 2, 3, 4, 5, 6, False]}], ['bold', 'italic', 'underline', 'strike'], [{'list': 'ordered'}, {'list': 'bullet'}], [{'color': []}, {'background': []}], ['link', 'image'], ['clean']]

        with st.expander("➕ Adicionar Novo Tema de Playbook"):
            with st.form("new_playbook_form", clear_on_submit=True):
                new_theme_name_input = st.text_input("Nome do Novo Tema*")
                st.markdown("Conteúdo (suporta formatação de texto)*")
                new_theme_content = st_quill(placeholder="Escreva aqui o conteúdo do seu playbook...", html=True, toolbar=toolbar_options, key="new_playbook_editor")
                if st.form_submit_button("Adicionar Tema", type="primary"):
                    # --- INÍCIO DA MODIFICAÇÃO ---
                    new_theme_name = new_theme_name_input.strip() # Remove espaços
                    # --- FIM DA MODIFICAÇÃO ---
                    if new_theme_name and new_theme_content:
                        configs.setdefault('playbooks', {})[new_theme_name] = new_theme_content
                        save_global_configs(configs)
                        force_hub_reload()
                        st.rerun()
        
        st.divider()
        st.markdown("###### Editar ou Remover Tema Existente")
        if playbooks:
            theme_to_edit = st.selectbox("Selecione um tema para gerir:", options=list(playbooks.keys()))
            if theme_to_edit:
                edited_content = st_quill(value=playbooks.get(theme_to_edit, ""), html=True, toolbar=toolbar_options, key="edit_playbook_editor")
                with st.container(border=True):
                    st.markdown("Pré-visualização do Conteúdo")
                    st.markdown(edited_content, unsafe_allow_html=True)
                c1, c2 = st.columns(2)
                if c1.button("Salvar Alterações", use_container_width=True, key=f"save_{theme_to_edit}"):
                    configs['playbooks'][theme_to_edit] = edited_content
                    save_global_configs(configs)
                    force_hub_reload()
                    st.rerun()
                if c2.button("❌ Remover Tema", use_container_width=True, type="secondary", key=f"del_{theme_to_edit}"):
                    del configs['playbooks'][theme_to_edit]
                    save_global_configs(configs)
                    force_hub_reload()
                    st.rerun()

    with content_tab_competencies:
        st.markdown("##### Framework de Competências")
        st.caption("Defina as competências e descrições que serão usadas na plataforma.")

        if 'competency_framework' not in configs:
            configs['competency_framework'] = {'hard_skills': [], 'soft_skills': []}

        framework_data = configs.get('competency_framework', {})
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("###### 🛠️ Hard Skills")
            edited_hard_skills = st.data_editor(pd.DataFrame(framework_data.get('hard_skills', [])), num_rows="dynamic", use_container_width=True, column_config={"Competência": "Competência*", "Descrição": "Descrição"})
        with col2:
            st.markdown("###### 🧠 Soft Skills")
            edited_soft_skills = st.data_editor(pd.DataFrame(framework_data.get('soft_skills', [])), num_rows="dynamic", use_container_width=True, column_config={"Competência": "Competência*", "Descrição": "Descrição"})
            
        if st.button("Salvar Framework de Competências", type="primary", use_container_width=True):
            configs['competency_framework']['hard_skills'] = edited_hard_skills.to_dict('records')
            configs['competency_framework']['soft_skills'] = edited_soft_skills.to_dict('records')
            save_global_configs(configs)
            force_hub_reload()
            st.success("Framework de competências salvo com sucesso!")
            st.rerun()

    with content_tab_roles:
        st.markdown("##### Papéis do Product Hub")
        st.caption("Adicione ou remova os papéis (funções) que podem ser atribuídos às equipas.")
        
        if 'editing_role_id' not in st.session_state: st.session_state.editing_role_id = None

        user_roles_raw = configs.get('user_roles', [])
        needs_migration = any(isinstance(role, str) for role in user_roles_raw)
        if needs_migration:
            migrated_roles = []
            for role in user_roles_raw:
                if isinstance(role, str): migrated_roles.append({"id": str(uuid.uuid4()), "name": role, "description": ""})
                elif isinstance(role, dict) and 'id' in role: migrated_roles.append(role)
            configs['user_roles'] = migrated_roles
            save_global_configs(configs)
            user_roles = migrated_roles
            st.toast("Dados de papéis foram atualizados para o novo formato.", icon="✨")
        else:
            user_roles = user_roles_raw

        toolbar_options_roles = [[{'header': [1, 2, 3, False]}], ['bold', 'italic', 'underline'], [{'list': 'ordered'}, {'list': 'bullet'}]]

        with st.expander("➕ Adicionar Novo Papel"):
            with st.form("new_role_form", clear_on_submit=True):
                role_name_input = st.text_input("Nome do Papel* (Ex: PM, Tech Lead)")
                st.markdown("Descrição e Responsabilidades*")
                role_description = st_quill(placeholder="Descreva o papel...", html=True, toolbar=toolbar_options_roles, key="new_role_editor")
                if st.form_submit_button("Adicionar Papel", type="primary"):
                    # --- INÍCIO DA MODIFICAÇÃO ---
                    role_name = role_name_input.strip() # Remove espaços
                    # --- FIM DA MODIFICAÇÃO ---
                    if role_name and role_description:
                        new_role = {"id": str(uuid.uuid4()), "name": role_name, "description": role_description}
                        user_roles.append(new_role)
                        configs['user_roles'] = sorted(user_roles, key=lambda x: x['name'])
                        save_global_configs(configs)
                        force_hub_reload()
                        st.rerun()
        
        st.divider()
        st.markdown("###### Papéis Atuais")
        if not user_roles:
            st.info("Nenhum papel foi cadastrado ainda.")
        else:
            for i, role in enumerate(user_roles):
                if st.session_state.editing_role_id == role['id']:
                    with st.form(f"edit_role_form_{role['id']}"):
                        st.subheader(f"Editando: {role['name']}")
                        edited_name_input = st.text_input("Nome do Papel*", value=role.get('name', ''))
                        st.markdown("Descrição e Responsabilidades*")
                        edited_description = st_quill(value=role.get('description', ''), html=True, toolbar=toolbar_options_roles, key=f"edit_role_editor_{role['id']}")
                        c1, c2 = st.columns(2)
                        if c1.form_submit_button("Salvar Alterações", use_container_width=True, type="primary"):
                            # --- INÍCIO DA MODIFICAÇÃO ---
                            edited_name = edited_name_input.strip() # Remove espaços
                            # --- FIM DA MODIFICAÇÃO ---
                            user_roles[i] = {"id": role['id'], "name": edited_name, "description": edited_description}
                            configs['user_roles'] = sorted(user_roles, key=lambda x: x['name'])
                            save_global_configs(configs)
                            force_hub_reload()
                            st.session_state.editing_role_id = None
                            st.rerun()
                        if c2.form_submit_button("Cancelar", use_container_width=True):
                            st.session_state.editing_role_id = None
                            st.rerun()
                else:
                    with st.container(border=True):
                        c1, c2 = st.columns([0.8, 0.2])
                        with c1: st.subheader(role['name'])
                        with c2:
                            btn_cols = st.columns(2)
                            if btn_cols[0].button("✏️", key=f"edit_role_{role['id']}", help="Editar Papel", use_container_width=True):
                                st.session_state.editing_role_id = role['id']
                                st.rerun()
                            if btn_cols[1].button("❌", key=f"del_role_{role['id']}", help="Remover Papel", use_container_width=True):
                                user_roles.pop(i)
                                configs['user_roles'] = user_roles
                                save_global_configs(configs)
                                force_hub_reload()
                                st.rerun()
                        st.markdown(role.get('description', 'Nenhuma descrição.'), unsafe_allow_html=True)

with main_tab_system:
    st.subheader("Configurações Gerais do Sistema")
    
    system_tab_domains, system_tab_users, system_tab_kpis, system_tab_email, tab_link = st.tabs([
        "🌐 Domínios", "👥 Utilizadores", "🎯 Metas", "📧 E-mail", "🔗 Link de Avaliação"
    ])

    with system_tab_domains:
        st.markdown("##### Domínios com Permissão de Registro")
        with st.container(border=True):
            allowed_domains = configs.get('allowed_domains', [])
            for domain in list(allowed_domains):
                col1, col2 = st.columns([4, 1])
                col1.text(domain)
                if col2.button("Remover", key=f"del_sys_domain_{domain}", use_container_width=True):
                    allowed_domains.remove(domain)
                    configs['allowed_domains'] = allowed_domains
                    save_global_configs(configs)
                    st.rerun()
            with st.form("new_sys_domain_form", clear_on_submit=True):
                new_domain_input = st.text_input("Adicionar novo domínio permitido:")
                if st.form_submit_button("Adicionar Domínio", type="primary"):
                    new_domain = new_domain_input.strip()
                    if new_domain and new_domain not in allowed_domains:
                        allowed_domains.append(new_domain)
                        configs['allowed_domains'] = allowed_domains
                        save_global_configs(configs)
                        st.rerun()

    with system_tab_users:
        st.markdown("##### Utilizadores Registados no Sistema")
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
                        if st.button("Resetar Senha", key=f"reset_pass_sys_{user['_id']}", use_container_width=True):
                            temp_password = generate_temporary_password()
                            hashed_password = get_password_hash(temp_password)
                            update_user_password(user['email'], hashed_password)
                            st.session_state.temp_password_info = {'email': user['email'], 'password': temp_password}
                            st.rerun()
                    with col3:
                        if st.button("Remover Utilizador", key=f"del_user_sys_{user['_id']}", use_container_width=True, type="secondary"):
                            delete_user(user['email'])
                            st.success(f"Utilizador '{user['email']}' e todos os seus dados foram removidos.")
                            st.rerun()

    with system_tab_kpis:
        st.markdown("##### Metas de KPIs Globais")
        with st.form("kpi_targets_form"):
            target_margin = st.number_input("Meta da Margem de Contribuição (%)", value=configs.get('target_contribution_margin', 25.0))
            if st.form_submit_button("Salvar Metas", use_container_width=True):
                configs['target_contribution_margin'] = target_margin
                save_global_configs(configs)
                st.rerun()

    with system_tab_email:
        st.markdown("##### Configuração Global de Envio de E-mail")
        st.caption("Estas credenciais serão usadas por toda a aplicação para enviar e-mails.")
        current_smtp_configs = get_global_smtp_configs() or {}
        current_provider = current_smtp_configs.get('provider', 'SendGrid')
        provider_options = ["SendGrid", "Gmail (SMTP)"]
        provider_index = provider_options.index(current_provider) if current_provider in provider_options else 0
        email_provider = st.radio("Selecione o provedor de e-mail do sistema:", provider_options, horizontal=True, index=provider_index)
        with st.form("global_smtp_config_form"):
            from_email = ""
            credential = ""
            if email_provider == 'SendGrid':
                if current_smtp_configs.get('api_key_encrypted'): st.success("Uma chave de API do SendGrid já está configurada.", icon="✅")
                from_email = st.text_input("E-mail de Origem (SendGrid)", value=current_smtp_configs.get('from_email', ''))
                credential = st.text_input("SendGrid API Key", type="password", placeholder="Insira uma nova chave para salvar ou alterar")
            elif email_provider == 'Gmail (SMTP)':
                if current_smtp_configs.get('app_password_encrypted'): st.success("Uma senha de aplicação do Gmail já está configurada.", icon="✅")
                st.info("Para usar o Gmail, é necessário criar uma 'senha de aplicação' na sua conta Google.")
                from_email = st.text_input("E-mail de Origem (Gmail)", value=current_smtp_configs.get('from_email', ''))
                credential = st.text_input("Senha de Aplicação (App Password)", type="password", placeholder="Insira uma nova senha para salvar ou alterar")
            if st.form_submit_button("Validar e Salvar Credenciais Globais", use_container_width=True, type="primary"):
                if from_email and credential:
                    with st.spinner("A validar as suas credenciais..."):
                        is_valid, message = validate_smtp_connection(email_provider, from_email, credential)
                    if is_valid:
                        encrypted_credential = encrypt_token(credential)
                        if email_provider == 'SendGrid':
                            configs_to_save = {'provider': 'SendGrid', 'from_email': from_email, 'api_key_encrypted': encrypted_credential}
                        else:
                            configs_to_save = {'provider': 'Gmail (SMTP)', 'from_email': from_email, 'app_password_encrypted': encrypted_credential}
                        save_global_smtp_configs(configs_to_save)
                        st.success(message + " As credenciais globais foram salvas com sucesso!")
                        st.rerun()
                    else:
                        st.error(message)
                else:
                    st.error("Por favor, preencha todos os campos para validar e salvar.")

with tab_link:
    st.subheader("Configurações Gerais da Aplicação")
    
    configs = get_global_configs()
    
    with st.form("general_configs_form"):
        st.markdown("#### URL Base da Aplicação")
        st.info("Esta URL é usada para gerar links partilháveis, como os de autoavaliação.")
        
        base_url_input = st.text_input(
            "URL Base", 
            value=configs.get("app_base_url", ""),
            placeholder="https://seu-app.streamlit.app"
        )

        st.divider()

        # A sua funcionalidade original de domínios
        st.markdown("#### Domínios Permitidos para Cadastro")
        st.info("Defina os domínios de e-mail que podem se cadastrar na aplicação. Separe múltiplos domínios por vírgula.")
        
        allowed_domains_input = st.text_area(
            "Domínios de E-mail Permitidos",
            value=", ".join(configs.get("allowed_domains", [])), # Usa a chave 'allowed_domains'
            placeholder="exemplo.com, outrodominio.com.br"
        )
        
        if st.form_submit_button("Salvar Configurações Gerais", type="primary", use_container_width=True):
            configs['app_base_url'] = base_url_input
            configs['allowed_domains'] = [domain.strip() for domain in allowed_domains_input.split(',') if domain.strip()]
            
            save_global_configs(configs)
            st.success("Configurações gerais salvas com sucesso!")
            st.rerun()
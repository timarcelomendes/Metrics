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

# --- VERIFICAÇÃO DE ADMIN CORRIGIDA ---
# Usamos a função centralizada is_admin() que verifica Master Users e admins do banco de dados.
if not is_admin(st.session_state['email']):
    st.error("🚫 Acesso Negado. Esta página é reservada para administradores.");
    st.stop()
# --- FIM DA CORREÇÃO ---

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

    if st.button("Logout", width='stretch', type='secondary'):
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
        # ... (código existente) ...
        st.markdown("##### Gestão de Conteúdo dos Playbooks")
        playbooks = configs.get('playbooks', {})
        
        toolbar_options = [[{'header': [1, 2, 3, 4, 5, 6, False]}], ['bold', 'italic', 'underline', 'strike'], [{'list': 'ordered'}, {'list': 'bullet'}], [{'color': []}, {'background': []}], ['link', 'image'], ['clean']]

        with st.expander("➕ Adicionar Novo Tema de Playbook"):
            with st.form("new_playbook_form", clear_on_submit=True):
                new_theme_name_input = st.text_input("Nome do Novo Tema*")
                st.markdown("Conteúdo (suporta formatação de texto)*")
                new_theme_content = st_quill(placeholder="Escreva aqui o conteúdo do seu playbook...", html=True, toolbar=toolbar_options, key="new_playbook_editor")
                if st.form_submit_button("Adicionar Tema", type="primary"):
                    new_theme_name = new_theme_name_input.strip()
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
                if c1.button("Salvar Alterações", width='stretch', key=f"save_{theme_to_edit}"):
                    configs['playbooks'][theme_to_edit] = edited_content
                    save_global_configs(configs)
                    force_hub_reload()
                    st.rerun()
                if c2.button("❌ Remover Tema", width='stretch', type="secondary", key=f"del_{theme_to_edit}"):
                    del configs['playbooks'][theme_to_edit]
                    save_global_configs(configs)
                    force_hub_reload()
                    st.rerun()

    with content_tab_competencies:
        # ... (código existente) ...
        st.markdown("##### Framework de Competências")
        st.caption("Defina as competências e descrições que serão usadas na plataforma.")

        if 'competency_framework' not in configs:
            configs['competency_framework'] = {'hard_skills': [], 'soft_skills': []}

        framework_data = configs.get('competency_framework', {})
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("###### 🛠️ Hard Skills")
            edited_hard_skills = st.data_editor(
                pd.DataFrame(framework_data.get('hard_skills', [])), 
                num_rows="dynamic", 
                width='stretch', 
                column_config={"Competência": "Competência*", "Descrição": "Descrição"},
                key="hard_skills_editor"
            )
        with col2:
            st.markdown("###### 🧠 Soft Skills")
            edited_soft_skills = st.data_editor(
                pd.DataFrame(framework_data.get('soft_skills', [])), 
                num_rows="dynamic", 
                width='stretch', 
                column_config={"Competência": "Competência*", "Descrição": "Descrição"},
                key="soft_skills_editor"
            )
            
        if st.button("Salvar Framework de Competências", type="primary", width='stretch'):
            configs['competency_framework']['hard_skills'] = edited_hard_skills.to_dict('records')
            configs['competency_framework']['soft_skills'] = edited_soft_skills.to_dict('records')
            save_global_configs(configs)
            force_hub_reload()
            st.success("Framework de competências salvo com sucesso!")
            st.rerun()

    with content_tab_roles:
        # ... (código existente) ...
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
                    role_name = role_name_input.strip()
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
                        if c1.form_submit_button("Salvar Alterações", width='stretch', type="primary"):
                            edited_name = edited_name_input.strip()
                            user_roles[i] = {"id": role['id'], "name": edited_name, "description": edited_description}
                            configs['user_roles'] = sorted(user_roles, key=lambda x: x['name'])
                            save_global_configs(configs)
                            force_hub_reload()
                            st.session_state.editing_role_id = None
                            st.rerun()
                        if c2.form_submit_button("Cancelar", width='stretch'):
                            st.session_state.editing_role_id = None
                            st.rerun()
                else:
                    with st.container(border=True):
                        c1, c2 = st.columns([0.8, 0.2])
                        with c1: st.subheader(role['name'])
                        with c2:
                            btn_cols = st.columns(2)
                            if btn_cols[0].button("✏️", key=f"edit_role_{role['id']}", help="Editar Papel", width='stretch'):
                                st.session_state.editing_role_id = role['id']
                                st.rerun()
                            if btn_cols[1].button("❌", key=f"del_role_{role['id']}", help="Remover Papel", width='stretch'):
                                user_roles.pop(i)
                                configs['user_roles'] = user_roles
                                save_global_configs(configs)
                                force_hub_reload()
                                st.rerun()
                        st.markdown(role.get('description', 'Nenhuma descrição.'), unsafe_allow_html=True)


with main_tab_system:
    st.subheader("Configurações Gerais do Sistema")
    
    system_tab_fields, system_tab_domains, system_tab_users, system_tab_kpis, system_tab_email, tab_link = st.tabs([
        "📝 Campos Jira", "🌐 Domínios", "👥 Utilizadores", "🎯 Metas", "📧 E-mail", "🔗 Link de Avaliação"
    ])

    with system_tab_fields:
        st.markdown("##### Gestão de Campos Globais para Análise")
        st.caption("Controle aqui os campos do Jira que estarão disponíveis para os utilizadores ativarem nos seus perfis.")
        
        current_configs_for_display = get_global_configs()

        # --- CAMPOS PADRÃO ---
        st.markdown("###### 🗂️ Campos Padrão (Standard Fields)")
        st.info("Estes são campos nativos do Jira. Ative aqueles que são relevantes para as suas análises.")
        
        STANDARD_FIELDS_MAP = {
            "Resolution": "Resolução", "Components": "Componentes", "Environment": "Ambiente",
            "Priority": "Prioridade", "Status": "Status", "Assignee": "Responsável",
            "DueDate": "Data de Vencimento", "Parent": "Pai", "StatusCategory": "Categoria de Status",
            "Labels": "Labels", "Project": "Projeto", "Reporter": "Relator", "Creator": "Criador",
            "Created": "Criado em", "Updated": "Atualizado em", "TimeTracking": "Controle de tempo"
        }
        
        standard_fields_config = current_configs_for_display.get('available_standard_fields', {})
        if not isinstance(standard_fields_config, dict): standard_fields_config = {}
        
        selected_standard_fields = st.multiselect(
            "Selecione os campos padrão a disponibilizar:",
            options=list(STANDARD_FIELDS_MAP.keys()),
            format_func=lambda key: STANDARD_FIELDS_MAP[key],
            default=list(standard_fields_config.keys()),
            key="multiselect_standard_fields"
        )
        
        if st.button("Salvar Campos Padrão", key="save_standard_fields", width='stretch'):
            configs_to_save = get_global_configs()
            configs_to_save['available_standard_fields'] = {field: {} for field in selected_standard_fields}
            save_global_configs(configs_to_save)
            get_global_configs.clear()
            st.success("Campos padrão atualizados com sucesso!")
            st.rerun()

        st.divider()

        # --- CAMPOS PERSONALIZADOS ---
        st.markdown("###### ✨ Campos Personalizados (Custom Fields)")
        st.info("Selecione os campos personalizados do seu Jira que devem estar disponíveis para análise na aplicação.")

        @st.cache_data(ttl=3600)
        def get_all_custom_fields_from_jira(_jira_client):
            try:
                all_fields = _jira_client.fields()
                custom_fields = [{'id': field['id'], 'name': field['name']} for field in all_fields if field['id'].startswith('customfield_')]
                return sorted(custom_fields, key=lambda x: x['name'])
            except Exception as e:
                st.error(f"Erro ao buscar campos personalizados do Jira."); print(e); return None

        try:
            all_jira_custom_fields = get_all_custom_fields_from_jira(st.session_state['jira_client'])

            if all_jira_custom_fields is not None:
                saved_custom_fields = current_configs_for_display.get('custom_fields', [])
                if not isinstance(saved_custom_fields, list): saved_custom_fields = []
                
                saved_custom_field_ids = [field['id'] for field in saved_custom_fields if isinstance(field, dict)]
                field_display_map = {field['id']: f"{field['name']} ({field['id']})" for field in all_jira_custom_fields}
                
                selected_field_ids = st.multiselect(
                    "Selecione os campos personalizados a disponibilizar:",
                    options=list(field_display_map.keys()),
                    format_func=lambda field_id: field_display_map.get(field_id, field_id),
                    default=saved_custom_field_ids,
                    key="multiselect_custom_fields"
                )

                if st.button("Salvar Campos Personalizados", key="save_custom_fields", width='stretch', type="primary"):
                    configs_to_save = get_global_configs()
                    updated_custom_fields = [{'id': field_id, 'name': field_display_map[field_id].split(' (')[0]} for field_id in selected_field_ids]
                    configs_to_save['custom_fields'] = updated_custom_fields
                    save_global_configs(configs_to_save)
                    get_global_configs.clear()
                    st.success("Campos personalizados salvos com sucesso!")
                    st.rerun()
            else:
                 st.error("Não foi possível carregar os campos personalizados do Jira. Verifique a conexão e as permissões.")
        except Exception as e:
            st.error(f"Ocorreu um erro inesperado na seção de campos personalizados."); st.caption(f"Detalhes: {e}");

        # --- CAMPO DE AGRUPAMENTO ESTRATÉGICO FOI REMOVIDO DAQUI ---

    with system_tab_domains:
        # ... (código existente) ...
        st.markdown("##### Domínios com Permissão de Registro")
        with st.container(border=True):
            allowed_domains = configs.get('allowed_domains', [])
            for domain in list(allowed_domains):
                col1, col2 = st.columns([4, 1])
                col1.text(domain)
                if col2.button("Remover", key=f"del_sys_domain_{domain}", width='stretch'):
                    allowed_domains.remove(domain)
                    configs['allowed_domains'] = allowed_domains
                    save_global_configs(configs)
                    get_global_configs.clear()
                    st.rerun()
            with st.form("new_sys_domain_form", clear_on_submit=True):
                new_domain_input = st.text_input("Adicionar novo domínio permitido:")
                if st.form_submit_button("Adicionar Domínio", type="primary"):
                    new_domain = new_domain_input.strip()
                    if new_domain and new_domain not in allowed_domains:
                        allowed_domains.append(new_domain)
                        configs['allowed_domains'] = allowed_domains
                        save_global_configs(configs)
                        get_global_configs.clear()
                        st.rerun()

    with system_tab_users:
        # ... (código existente com o novo design de cartões) ...
        st.markdown("##### 👥 Utilizadores Registados no Sistema")
        st.caption("Gira as permissões e contas dos utilizadores da plataforma.")
        
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
                is_current_user_admin = user.get('is_admin', False)
                is_master_user_target = user['email'] in MASTER_USERS
                
                with st.container(border=True):
                    col1, col2 = st.columns([0.7, 0.3])
                    with col1:
                        st.subheader(user['email'])
                    with col2:
                        if is_master_user_target:
                            st.success("🏆 Master User", icon="🏆")
                        elif is_current_user_admin:
                            st.success("👑 Administrador", icon="👑")
                        else:
                            st.info("👤 Utilizador Padrão", icon="👤")
                            
                    st.divider() 

                    st.markdown("**Ações Disponíveis**")
                    action_cols = st.columns(3)
                    
                    with action_cols[0]: # Promover / Despromover
                        if not is_master_user_target:
                            if is_current_user_admin:
                                st.button(
                                    "Despromover", 
                                    key=f"demote_admin_{user['_id']}", 
                                    type="secondary",
                                    on_click=lambda u=user['email']: set_admin_status(u, False),
                                    use_container_width=True
                                )
                            else:
                                st.button(
                                    "Promover a Admin", 
                                    key=f"promote_admin_{user['_id']}", 
                                    type="primary",
                                    on_click=lambda u=user['email']: set_admin_status(u, True),
                                    use_container_width=True
                                )
                        else:
                            st.button("Promover", disabled=True, use_container_width=True) 

                    with action_cols[1]: # Resetar Senha
                        st.button(
                            "Resetar Senha", 
                            key=f"reset_pass_sys_{user['_id']}", 
                            on_click=lambda u=user: (
                                setattr(st.session_state, 'temp_password_info', {
                                    'email': u['email'], 
                                    'password': generate_temporary_password()
                                }),
                                update_user_password(u['email'], get_password_hash(st.session_state.temp_password_info['password']))
                            ),
                            use_container_width=True
                        )

                    with action_cols[2]: # Remover Utilizador
                        st.button(
                            "Remover Utilizador", 
                            key=f"del_user_sys_{user['_id']}", 
                            type="secondary",
                            disabled=is_master_user_target, 
                            on_click=lambda u=user['email']: delete_user(u),
                            use_container_width=True
                        )

            if any(key.startswith(('reset_pass', 'del_user', 'demote_admin', 'promote_admin')) and st.session_state[key] for key in st.session_state):
                 st.rerun()

    with system_tab_kpis:
        # ... (código existente) ...
        st.markdown("##### Metas de KPIs Globais")
        with st.form("kpi_targets_form"):
            target_margin = st.number_input("Meta da Margem de Contribuição (%)", value=configs.get('target_contribution_margin', 25.0))
            if st.form_submit_button("Salvar Metas", width='stretch'):
                configs['target_contribution_margin'] = target_margin
                save_global_configs(configs)
                get_global_configs.clear()
                st.rerun()

    with system_tab_email:
        # ... (código existente) ...
        st.markdown("##### Configuração Global de Envio de E-mail")
        st.caption("Estas credenciais serão usadas por toda a aplicação para enviar e-mails.")
        current_smtp_configs = configs.get('smtp_settings', {})
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
            if st.form_submit_button("Validar e Salvar Credenciais Globais", width='stretch', type="primary"):
                if from_email and credential:
                    with st.spinner("A validar as suas credenciais..."):
                        is_valid, message = validate_smtp_connection(email_provider, from_email, credential)
                    if is_valid:
                        encrypted_credential = encrypt_token(credential)
                        smtp_data_to_save = {
                            'provider': email_provider, 
                            'from_email': from_email,
                        }
                        if email_provider == 'SendGrid':
                            smtp_data_to_save['api_key_encrypted'] = encrypted_credential
                        else:
                            smtp_data_to_save['app_password_encrypted'] = encrypted_credential
                        configs['smtp_settings'] = smtp_data_to_save
                        save_global_configs(configs) 
                        get_global_configs.clear()
                        st.success(message + " As credenciais globais foram salvas com sucesso!")
                        st.rerun()
                    else:
                        st.error(message)
                else:
                    st.error("Por favor, preencha todos os campos para validar e salvar.")


    with tab_link:
        # ... (código existente) ...
        st.subheader("Configurações Gerais da Aplicação")
        with st.form("general_configs_form"):
            st.markdown("#### URL Base da Aplicação")
            st.info("Esta URL é usada para gerar links partilháveis, como os de autoavaliação.")
            base_url_input = st.text_input(
                "URL Base", 
                value=configs.get("app_base_url", ""),
                placeholder="https://seu-app.streamlit.app"
            )
            st.divider()
            st.markdown("#### Domínios Permitidos para Cadastro")
            st.info("Defina os domínios de e-mail que podem se cadastrar na aplicação. Separe múltiplos domínios por vírgula.")
            allowed_domains_input = st.text_area(
                "Domínios de E-mail Permitidos",
                value=", ".join(configs.get("allowed_domains", [])),
                placeholder="exemplo.com, outrodominio.com.br"
            )
            if st.form_submit_button("Salvar Configurações Gerais", type="primary", width='stretch'):
                configs['app_base_url'] = base_url_input
                configs['allowed_domains'] = [domain.strip() for domain in allowed_domains_input.split(',') if domain.strip()]
                save_global_configs(configs)
                get_global_configs.clear()
                st.success("Configurações gerais salvas com sucesso!")
                st.rerun()
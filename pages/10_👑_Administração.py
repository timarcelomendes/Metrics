# pages/9_👑_Administração.py

import streamlit as st
from security import *
from pathlib import Path
import pandas as pd
from security import *

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
    
    # --- PAINEL DE DIAGNÓSTICO ---
    with st.expander("🔍 Ajuda de Diagnóstico"):
        st.write("O seu e-mail de login não foi encontrado na lista de administradores.")
        st.write(f"**Seu E-mail:** `{st.session_state['email']}`")
        st.write(f"**Lista de Admins que a Aplicação Conseguiu Ler:** `{ADMIN_EMAILS}`")
        st.info("Se a lista acima estiver vazia ou incorreta, verifique se o seu ficheiro `.streamlit/secrets.toml` está correto e **reinicie completamente o servidor do Streamlit** (`Ctrl+C` no terminal e `streamlit run ...` de novo).")
    st.stop()

# --- Se chegou até aqui, o utilizador é um admin. ---
configs = get_global_configs()
# Carrega as configurações globais
global_configs = get_global_configs()

# --- BARRA LATERAL ---
with st.sidebar:
    project_root = Path(__file__).parent.parent
    logo_path = project_root / "images" / "gauge-logo.svg"
    try:
        st.logo(logo_path, size="large")
    except FileNotFoundError:
        st.write("Gauge Metrics") 
    
    if st.session_state.get("email"):
        st.markdown(f"🔐 Logado como: **{st.session_state['email']}**")
    else:
        st.info("⚠️ Usuário não conectado!")

    if st.button("Logout", use_container_width=True, type='secondary'):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.switch_page("1_🔑_Autenticação.py")

# --- Interface Principal com Abas ---
tab1, tab2, tab3, tab4 = st.tabs(["👨‍💻Domínios Permitidos", "🙎Gerir Utilizadores", "📝 Gerir Playbooks", "💎 Gerir Competências"])

with tab1:
    st.subheader("Domínios com Permissão de Registro")
    st.caption("Apenas utilizadores com emails destes domínios poderão criar uma conta na aplicação.")
    
    with st.container(border=True):
        allowed_domains = configs.get('allowed_domains', [])
        
        for domain in list(allowed_domains):
            col1, col2 = st.columns([4, 1])
            col1.text(domain)
            if col2.button("Remover", key=f"del_{domain}", use_container_width=True):
                allowed_domains.remove(domain)
                configs['allowed_domains'] = allowed_domains
                save_global_configs(configs); get_global_configs.clear()
                st.session_state['global_configs'] = get_global_configs()
                st.rerun()

        with st.form("new_domain_form", clear_on_submit=True):
            new_domain = st.text_input("Adicionar novo domínio permitido:")
            if st.form_submit_button("Adicionar Domínio", type="primary"):
                if new_domain and new_domain not in allowed_domains:
                    allowed_domains.append(new_domain)
                    configs['allowed_domains'] = allowed_domains
                    save_global_configs(configs); get_global_configs.clear()
                    st.session_state['global_configs'] = get_global_configs()
                    st.rerun()
                elif not new_domain:
                    st.warning("Por favor, insira um domínio.")
                else:
                    st.warning(f"O domínio '{new_domain}' já existe na lista.")

with tab2:
    st.subheader("Utilizadores Registados no Sistema")

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
                    if st.button("Resetar Senha", key=f"reset_pass_{user['_id']}", use_container_width=True):
                        temp_password = generate_temporary_password()
                        hashed_password = get_password_hash(temp_password)
                        update_user_password(user['email'], hashed_password)
                        
                        st.session_state.temp_password_info = {'email': user['email'], 'password': temp_password}
                        st.rerun()

                with col3:
                    if st.button("Remover Utilizador", key=f"del_user_{user['_id']}", use_container_width=True, type="secondary"):
                        delete_user(user['email'])
                        st.success(f"Utilizador '{user['email']}' e todos os seus dados foram removidos.")
                        st.rerun()

with tab3:
    st.header("Gestão de Conteúdo dos Playbooks")
    st.info("Adicione, edite ou remova os temas do Playbook. As alterações serão visíveis para todos os utilizadores.")
    
    playbooks = configs.get('playbooks', {})

    with st.expander("➕ Adicionar Novo Tema de Playbook"):
        with st.form("new_playbook_form", clear_on_submit=True):
            new_theme_name = st.text_input("Nome do Novo Tema*")
            new_theme_content = st.text_area("Conteúdo (suporta Markdown)*", height=300)
            if st.form_submit_button("Adicionar Tema", type="primary"):
                if new_theme_name and new_theme_content:
                    configs['playbooks'][new_theme_name] = new_theme_content
                    save_global_configs(configs)
                    st.rerun()

    st.divider()
    st.subheader("Editar ou Remover Tema Existente")
    
    if not playbooks:
        st.warning("Nenhum playbook encontrado. Adicione o primeiro tema acima.")
    else:
        theme_to_edit = st.selectbox("Selecione um tema para gerir:", options=list(playbooks.keys()))
        
        if theme_to_edit:
            edited_content = st.text_area(
                f"Conteúdo do tema '{theme_to_edit}':",
                value=playbooks.get(theme_to_edit, ""),
                height=400,
                key=f"editor_{theme_to_edit}"
            )
            
            c1, c2 = st.columns(2)
            if c1.button("Salvar Alterações", use_container_width=True):
                configs['playbooks'][theme_to_edit] = edited_content
                save_global_configs(configs)
                st.rerun()
            
            if c2.button("❌ Remover Tema", use_container_width=True, type="secondary", disabled=(len(playbooks) <= 1)):
                del configs['playbooks'][theme_to_edit]
                save_global_configs(configs)
                st.rerun()

with tab4:
    st.header("Framework de Competências")
    st.info("Defina os pilares, competências e descrições que serão usados na plataforma.")

    if 'competency_framework' not in global_configs:
        global_configs['competency_framework'] = {
            'hard_skills': [{"Pilar": "Desenvolvimento", "Competência": "Exemplo Técnico", "Descrição": "Descreva o que se espera."}],
            'soft_skills': [{"Pilar": "Comunicação", "Competência": "Exemplo Comportamental", "Descrição": "Descreva o que se espera."}]
        }

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🛠️ Hard Skills")
        hard_skills_df = pd.DataFrame(global_configs['competency_framework'].get('hard_skills', []))
        edited_hard_skills = st.data_editor(
            hard_skills_df,
            num_rows="dynamic",
            use_container_width=True,
            column_order=("Pilar", "Competência", "Descrição"), # Define a ordem das colunas
            column_config={
                "Pilar": st.column_config.TextColumn("Pilar Estratégico*", required=True),
                "Competência": st.column_config.TextColumn("Competência*", required=True),
                "Descrição": st.column_config.TextColumn("Descrição", width="large")
            },
            key="hard_skills_editor"
        )

    with col2:
        st.subheader("🧠 Soft Skills")
        soft_skills_df = pd.DataFrame(global_configs['competency_framework'].get('soft_skills', []))
        edited_soft_skills = st.data_editor(
            soft_skills_df,
            num_rows="dynamic",
            use_container_width=True,
            column_order=("Pilar", "Competência", "Descrição"), # Define a ordem das colunas
            column_config={
                "Pilar": st.column_config.TextColumn("Pilar Estratégico*", required=True),
                "Competência": st.column_config.TextColumn("Competência*", required=True),
                "Descrição": st.column_config.TextColumn("Descrição", width="large")
            },
            key="soft_skills_editor"
        )
        
    st.divider()

    if st.button("Salvar Framework de Competências", type="primary", use_container_width=True):
        global_configs['competency_framework']['hard_skills'] = edited_hard_skills.to_dict('records')
        global_configs['competency_framework']['soft_skills'] = edited_soft_skills.to_dict('records')
        
        save_global_configs(global_configs)
        st.success("Framework de competências salvo com sucesso!")
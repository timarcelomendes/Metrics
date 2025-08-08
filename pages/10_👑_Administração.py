# pages/9_👑_Administração.py

import streamlit as st
from security import *
from pathlib import Path

st.set_page_config(page_title="Administração", page_icon="👑", layout="wide")

st.header("👑 Painel de Administração", divider='rainbow')

# --- BLOCO DE CONTROLO DE ACESSO ---
if 'email' not in st.session_state:
    st.warning("⚠️ Por favor, faça login para acessar."); st.page_link("1_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑"); st.stop()

ADMIN_EMAILS = st.secrets.get("app_settings", {}).get("ADMIN_EMAILS", [])
if st.session_state['email'] not in ADMIN_EMAILS:
    st.error("🚫 Acesso Negado. Esta página é reservada para administradores."); st.stop()

# Se chegou até aqui, o utilizador é um admin.
configs = get_global_configs()

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
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.switch_page("1_🔑_Autenticação.py")


tab1, tab2 = st.tabs(["Gestão de Domínios Permitidos", "Gestão de Utilizadores"])

with tab1:
    st.subheader("Domínios com Permissão de Registro")
    st.caption("Apenas utilizadores com emails destes domínios poderão criar uma conta na aplicação.")
    
    with st.container(border=True):
        allowed_domains = configs.get('allowed_domains', [])
        
        # Exibir domínios atuais com botão de remover
        for domain in list(allowed_domains):
            col1, col2 = st.columns([4, 1])
            col1.text(domain)
            if col2.button("Remover", key=f"del_{domain}", use_container_width=True):
                allowed_domains.remove(domain)
                configs['allowed_domains'] = allowed_domains
                save_global_configs(configs); get_global_configs.clear()
                st.session_state['global_configs'] = get_global_configs()
                st.rerun()

        # Adicionar novo domínio
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

    # --- LÓGICA PARA EXIBIR A SENHA TEMPORÁRIA ---
    if 'temp_password_info' in st.session_state:
        user_email = st.session_state.temp_password_info['email']
        temp_pass = st.session_state.temp_password_info['password']
        st.success(f"Senha para **{user_email}** redefinida com sucesso!", icon="🔑")
        st.code(temp_pass, language=None)
        st.warning("Por favor, copie esta senha e envie-a ao utilizador por um canal seguro. Ela só será exibida uma vez.")
        del st.session_state.temp_password_info # Limpa a senha da memória
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
                
                # --- BOTÃO DE RESETAR SENHA ---
                with col2:
                    if st.button("Resetar Senha", key=f"reset_pass_{user['_id']}", use_container_width=True):
                        temp_password = generate_temporary_password()
                        hashed_password = get_password_hash(temp_password)
                        update_user_password(user['email'], hashed_password)
                        
                        # Guarda a senha temporária na sessão para exibir após o rerun
                        st.session_state.temp_password_info = {'email': user['email'], 'password': temp_password}
                        st.rerun()

                # --- BOTÃO DE REMOVER UTILIZADOR ---
                with col3:
                    if st.button("Remover Utilizador", key=f"del_user_{user['_id']}", use_container_width=True, type="secondary"):
                        delete_user(user['email'])
                        st.success(f"Utilizador '{user['email']}' e todos os seus dados foram removidos.")
                        st.rerun()
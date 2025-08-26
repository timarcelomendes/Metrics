# pages/7_👤_Minha_Conta.py

import streamlit as st
import os
from pathlib import Path
from security import *
from utils import send_notification_email

st.set_page_config(page_title="Minha Conta", page_icon="👤", layout="wide")

st.header("👤 Minha Conta", divider='rainbow')

# --- Bloco de Autenticação e Conexão ---
if 'email' not in st.session_state:
    st.warning("⚠️ Por favor, faça login para acessar."); st.page_link("1_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑"); st.stop()

# --- LÓGICA DE VERIFICAÇÃO DE CONEXÃO CORRIGIDA ---
if 'jira_client' not in st.session_state:
    # Verifica se o utilizador tem alguma conexão guardada na base de dados
    user_connections = get_user_connections(st.session_state['email'])
    
    if not user_connections:
        # Cenário 1: O utilizador nunca configurou uma conexão
        st.warning("Nenhuma conexão Jira foi configurada ainda.", icon="🔌")
        st.info("Para começar, você precisa de adicionar as suas credenciais do Jira.")
        st.page_link("pages/8_🔗_Conexões_Jira.py", label="Configurar sua Primeira Conexão", icon="🔗")
        st.stop()
    else:
        # Cenário 2: O utilizador tem conexões, mas nenhuma está ativa
        st.warning("Nenhuma conexão Jira está ativa para esta sessão.", icon="⚡")
        st.info("Por favor, ative uma das suas conexões guardadas para carregar os dados.")
        st.page_link("pages/8_🔗_Conexões_Jira.py", label="Ativar uma Conexão", icon="🔗")
        st.stop()

email = st.session_state['email']
user_data = find_user(email)
global_configs = st.session_state.get('global_configs', {})

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
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.switch_page("1_🔑_Autenticação.py")

# --- ESTRUTURA DE ABAS PRINCIPAL ---
tab_perfil, tab_campos, tab_ai, tab_tokens = st.tabs(["👤 Perfil e Senha", "Jira: Campos Dinâmicos", "Configurações de AI", "🔑 Tokens e Credenciais"])

with tab_perfil:
    st.subheader("Informações do Perfil")
    col1, col2 = st.columns(2, gap="large")
    with col1:
        with st.container(border=True):
            st.info(f"**Utilizador:** {email}")
            st.page_link("pages/8_🔗_Conexões_Jira.py", label="Gerir Minhas Conexões Jira", icon="🔗")
    with col2:
        with st.container(border=True):
            st.markdown("**Alterar Senha**")
            with st.form("change_password_form"):
                current_password = st.text_input("Senha Atual", type="password")
                new_password = st.text_input("Nova Senha", type="password")
                confirm_password = st.text_input("Confirmar Nova Senha", type="password")
                if st.form_submit_button("Alterar Senha", use_container_width=True, type="primary"):
                    if not all([current_password, new_password, confirm_password]):
                        st.warning("Por favor, preencha todos os campos.")
                    elif not verify_password(current_password, user_data['hashed_password']):
                        st.error("A 'Senha Atual' está incorreta.")
                    elif len(new_password) < 8:
                        st.error("A nova senha deve ter pelo menos 8 caracteres.")
                    elif new_password != confirm_password:
                        st.error("A 'Nova Senha' e a 'Confirmação' não coincidem.")
                    else:
                        new_hashed_password = get_password_hash(new_password)
                        update_user_password(email, new_hashed_password)
                        st.success("Senha alterada com sucesso!")

                        # --- ENVIO DO E-MAIL DE NOTIFICAÇÃO ---
                        subject = "Alerta de Segurança: A sua senha foi alterada"
                        body_html = f"""
                        <html><body>
                            <h2>Olá,</h2>
                            <p>Este é um e-mail para confirmar que a senha da sua conta ({email}) na plataforma Gauge Metrics foi alterada com sucesso.</p>
                            <p>Se não foi você que fez esta alteração, por favor, contacte o suporte imediatamente.</p>
                            <p>Atenciosamente,<br>A Equipe Gauge Metrics</p>
                        </body></html>
                        """
                        send_notification_email(email, subject, body_html)
with tab_campos:
    st.subheader("Preferências de Campos para Análise")
    st.caption("Ative os campos que você deseja que apareçam como opções nas páginas de análise. As alterações são guardadas para o seu perfil.")

    # --- ABAS INTERNAS PARA ORGANIZAÇÃO ---
    tab_std, tab_custom = st.tabs(["🗂️ Campos Padrão", "✨ Campos Personalizados"])
    
    toggles_std = {}
    toggles_custom = {}

    with tab_std:
        available_standard_fields = global_configs.get('available_standard_fields', {})
        user_selected_standard = user_data.get('standard_fields', [])
        
        if not available_standard_fields:
            st.info("Nenhum campo padrão foi configurado pelo administrador.")
            st.page_link("pages/7_⚙️_Configurações.py", label="Configurar Campos Globais", icon="⚙️")
        else:
            st.markdown("**Ative os campos padrão que deseja usar:**")
            for name in sorted(available_standard_fields.keys()):
                toggles_std[name] = st.toggle(name, value=(name in user_selected_standard), key=f"toggle_std_{name}")

    with tab_custom:
        available_custom_fields = global_configs.get('custom_fields', [])
        user_selected_custom = user_data.get('enabled_custom_fields', [])

        if not available_custom_fields:
            st.info("Nenhum campo personalizado foi configurado pelo administrador.")
        else:
            st.markdown("**Ative os campos personalizados que deseja usar:**")
            for field in sorted(available_custom_fields, key=lambda x: x['name']):
                name = field['name']
                toggles_custom[name] = st.toggle(name, value=(name in user_selected_custom), key=f"toggle_custom_{name}")
    
    st.divider()
    if st.button("Salvar Preferências de Campos", use_container_width=True, type="primary"):
        new_selection_std = [name for name, is_on in toggles_std.items() if is_on]
        save_user_standard_fields(email, new_selection_std)
        
        if toggles_custom: # Só tenta salvar se a seção foi renderizada
            new_selection_custom = [name for name, is_on in toggles_custom.items() if is_on]
            save_user_custom_fields(email, new_selection_custom)

        st.success("Suas preferências de campos foram guardadas!")
        st.rerun()

with tab_ai:
    st.subheader("🤖 Configurações de Inteligência Artificial")
    st.caption("Selecione o seu provedor de IA preferido e insira a sua chave de API pessoal.")

    with st.container(border=True):
        provider_options = ["Google Gemini", "OpenAI (ChatGPT)"]
        user_provider = user_data.get('ai_provider_preference', 'Google Gemini')
        
        selected_provider = st.radio(
            "Selecione o seu Provedor de IA Preferido:",
            provider_options,
            index=provider_options.index(user_provider) if user_provider in provider_options else 0,
            horizontal=True
        )

        if selected_provider != user_provider:
            save_user_ai_provider_preference(email, selected_provider)
            st.session_state['user_data'] = find_user(email)
            st.rerun()
        
        st.divider()

        if selected_provider == "Google Gemini":
            key_exists = 'encrypted_gemini_key' in user_data and user_data['encrypted_gemini_key']
            if key_exists: st.success("Uma chave de API do Gemini já está configurada.", icon="✅")
            else:
                st.warning("Nenhuma chave de API do Gemini configurada.", icon="⚠️")
            
            with st.form("gemini_form"):
                api_key_input = st.text_input("Chave de API do Google Gemini", type="password", placeholder="Cole a sua chave aqui para adicionar ou alterar")
                model_options = {"Gemini 1.5 Pro (Mais poderoso)": "gemini-1.5-pro-latest", "Gemini 1.5 Flash (Mais rápido)": "gemini-1.5-flash-latest"}
                user_model = user_data.get('ai_model_preference', 'gemini-1.5-pro-latest')
                default_model_name = next((name for name, model_id in model_options.items() if model_id == user_model), None)
                selected_model_name = st.selectbox("Modelo Gemini Preferido", options=model_options.keys(), index=list(model_options.keys()).index(default_model_name) if default_model_name else 0)
                st.caption("[Crie uma chave gratuitamente no Google AI Studio](https://aistudio.google.com/app/apikey)")
                
                s1, s2 = st.columns([1,1])
                if s1.form_submit_button("Salvar / Alterar", use_container_width=True, type="primary"):
                    if api_key_input: save_user_gemini_key(email, encrypt_token(api_key_input))
                    if 'selected_model_name' in locals(): save_user_ai_model_preference(email, model_options[selected_model_name])
                    st.session_state['user_data'] = find_user(email); st.success("Configurações do Gemini guardadas!"); st.rerun()
                if s2.form_submit_button("Remover Chave", use_container_width=True, disabled=not key_exists):
                    remove_user_gemini_key(email)
                    st.session_state['user_data'] = find_user(email); st.success("Chave do Gemini removida!"); st.rerun()

        else: # OpenAI
            key_exists = 'encrypted_openai_key' in user_data and user_data['encrypted_openai_key']
            if key_exists: st.success("Uma chave de API da OpenAI já está configurada.", icon="✅")
            else:
                st.warning("Nenhuma chave de API do OpenAI configurada.", icon="⚠️")
            
            with st.form("openai_form"):
                api_key_input = st.text_input("Chave de API da OpenAI", type="password", placeholder="Cole a sua chave de API aqui (sk-...)")
                st.caption("[Crie uma chave no site da OpenAI](https://platform.openai.com/api-keys)")

                s1, s2 = st.columns([1,1])
                if s1.form_submit_button("Salvar / Alterar Chave", use_container_width=True, type="primary"):
                    if api_key_input:
                        save_user_openai_key(email, encrypt_token(api_key_input))
                        st.session_state['user_data'] = find_user(email); st.success("Chave da OpenAI guardada!"); st.rerun()
                    else:
                        st.warning("Por favor, insira uma chave para salvar.")
                if s2.form_submit_button("Remover Chave", use_container_width=True, disabled=not key_exists):
                    remove_user_openai_key(email)
                    st.session_state['user_data'] = find_user(email); st.success("Chave da OpenAI removida!"); st.rerun()

# ===== ABA DE TOKENS E CREDENCIAIS =====
with tab_tokens:
    st.subheader("Gestão de Tokens de API e Credenciais de E-mail")
    st.caption("Guarde as suas credenciais aqui. Elas são guardadas de forma encriptada na base de dados.")
    
    # --- Seção do Figma ---
    with st.container(border=True):
        with st.form("figma_token_form"):
            st.markdown("**Token de Acesso Pessoal do Figma**")
            st.info("Este token é necessário para usar a funcionalidade 'Gerador de Histórias com IA'. [Clique aqui para criar um novo token no Figma](https://www.figma.com/developers/api#access-tokens).", icon="💡")
            
            # Busca o token existente para exibi-lo (se houver)
            current_figma_token = get_user_figma_token(email)
            
            figma_token = st.text_input(
                "Seu Token do Figma", 
                value=current_figma_token or "",
                type="password",
                help="O seu token é guardado de forma encriptada na base de dados."
            )

            if current_figma_token:
                st.warning("O seu token está a ser exibido. Não partilhe esta informação.", icon="⚠️")
            
            if st.form_submit_button("Salvar Token do Figma", use_container_width=True, type="primary"):
                save_user_figma_token(email, figma_token)
                st.success("Token do Figma guardado com sucesso!")
                st.rerun()

    # --- Seção de E-mail ---
    with st.container(border=True):
        st.markdown("**Configuração de Envio de E-mail**")
        current_smtp_configs = get_smtp_configs() or {}
        current_provider = current_smtp_configs.get('provider', 'SendGrid')

        provider_options = ["SendGrid", "Gmail (SMTP)"]
        provider_index = provider_options.index(current_provider) if current_provider in provider_options else 0
        email_provider = st.radio("Selecione o seu provedor:", provider_options, horizontal=True, index=provider_index)
        
        with st.form("smtp_config_form"):
            if email_provider == 'Gmail (SMTP)':
                from_email = st.text_input("E-mail de Origem (Gmail)", value=current_smtp_configs.get('from_email', ''))
                app_password = st.text_input("Senha de Aplicação (App Password)", value=current_smtp_configs.get('app_password', ''), type="password")
                smtp_configs_to_save = {'provider': 'Gmail (SMTP)', 'from_email': from_email, 'app_password': app_password}
            
            elif email_provider == 'SendGrid':
                from_email = st.text_input("E-mail de Origem (SendGrid)", value=current_smtp_configs.get('from_email', ''))
                sendgrid_api_key = st.text_input("SendGrid API Key", value=current_smtp_configs.get('api_key', ''), type="password")
                smtp_configs_to_save = {'provider': 'SendGrid', 'from_email': from_email, 'api_key': sendgrid_api_key}
            
            if st.form_submit_button("Salvar Credenciais de E-mail", use_container_width=True, type="primary"):
                if from_email:
                    save_smtp_configs(smtp_configs_to_save)
                    st.success("Configurações de e-mail salvas com sucesso!")
                    st.rerun()
                else:
                    st.error("Por favor, preencha o e-mail de origem.")
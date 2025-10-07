# pages/7_👤_Minha_Conta.py

import streamlit as st
import os
from pathlib import Path
from security import *
from utils import send_email_with_attachment, validate_smtp_connection
from config import SESSION_TIMEOUT_MINUTES

st.set_page_config(page_title="Minha Conta", page_icon="👤", layout="wide")

st.header("👤 Minha Conta", divider='rainbow')

# --- Bloco de Autenticação e Conexão ---
if 'email' not in st.session_state:
    st.warning("⚠️ Por favor, faça login para acessar."); st.page_link("1_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑"); st.stop()

if check_session_timeout():
    # Usa uma f-string para formatar a mensagem com o valor da variável
    st.warning(f"Sua sessão expirou por inatividade de {SESSION_TIMEOUT_MINUTES} minutos. Por favor, faça login novamente.")
    st.page_link("1_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑")
    st.stop()

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
            with st.form("change_password_form", clear_on_submit=True):
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
                        success, message = send_email_with_attachment(to_address=email, subject=subject, body=body_html)
                        
                        # --- MENSAGEM SIMPLIFICADA AQUI ---
                        if success:
                            st.info("Um e-mail de notificação foi enviado.")
                        else:
                            st.error(f"A senha foi alterada, mas falhou o envio do e-mail de notificação: {message}")

with tab_campos:
    st.subheader("Preferências de Campos para Análise")
    st.caption("Ative os campos que você deseja que apareçam como opções nas páginas de análise. As alterações são guardadas para o seu perfil.")

    # Define as variáveis num escopo mais alto, acessível ao botão "Salvar"
    available_custom_fields = global_configs.get('custom_fields', [])
    user_selected_custom = user_data.get('enabled_custom_fields', [])
    id_to_name_map = {field['id']: field['name'] for field in available_custom_fields}
    
    toggles_std = {}
    toggles_custom = {}

    # --- ABAS INTERNAS PARA ORGANIZAÇÃO ---
    tab_std, tab_custom = st.tabs(["🗂️ Campos Padrão", "✨ Campos Personalizados"])
    
    with tab_std:
        available_standard_fields = global_configs.get('available_standard_fields', {})
        user_selected_standard = user_data.get('standard_fields', [])
        
        if not available_standard_fields:
            st.info("Nenhum campo padrão foi configurado pelo administrador.")
        else:
            search_term_std = st.text_input("Filtrar campos padrão:", placeholder="Digite para pesquisar...", key="search_std")
            
            filtered_standard_fields = {
                name: details for name, details in available_standard_fields.items()
                if search_term_std.lower() in name.lower()
            }
            
            st.markdown("**Ative os campos padrão que deseja usar:**")
            for name in sorted(filtered_standard_fields.keys()):
                toggles_std[name] = st.toggle(name, value=(name in user_selected_standard), key=f"toggle_std_{name}")

    with tab_custom:
        if not available_custom_fields:
            st.info("Nenhum campo personalizado foi configurado pelo administrador.")
        else:
            search_term_custom = st.text_input("Filtrar campos personalizados:", placeholder="Digite para pesquisar...", key="search_custom")

            filtered_custom_fields = [
                field for field in available_custom_fields
                if search_term_custom.lower() in field.get('name', '').lower()
            ]

            st.markdown("**Ative os campos personalizados que deseja usar:**")
            
            for field in sorted(filtered_custom_fields, key=lambda x: x['name']):
                field_id = field['id']
                name = field['name']
                toggles_custom[field_id] = st.toggle(
                    name, 
                    value=(name in user_selected_custom), 
                    key=f"toggle_custom_{field_id}"
                )
    
    st.divider()
    if st.button("Salvar Preferências de Campos", use_container_width=True, type="primary", key="save_field_prefs_button"):
        # Lógica para campos padrão
        new_selection_std = [name for name, is_on in toggles_std.items() if is_on]
        unchanged_std = [name for name in user_selected_standard if name not in toggles_std]
        save_user_standard_fields(email, new_selection_std + unchanged_std)
        
        # Lógica para campos personalizados
        if toggles_custom:
            new_selection_custom_ids = [field_id for field_id, is_on in toggles_custom.items() if is_on]
            new_selection_custom_names = [id_to_name_map[fid] for fid in new_selection_custom_ids]
            
            unchanged_custom_names = [
                name for name in user_selected_custom 
                if name not in [id_to_name_map.get(fid) for fid in toggles_custom.keys()]
            ]
            save_user_custom_fields(email, new_selection_custom_names + unchanged_custom_names)

        st.success("Suas preferências de campos foram guardadas!")
        st.rerun()

with tab_ai:
    st.subheader("🤖 Configurações de Inteligência Artificial")
    st.caption("Selecione o seu provedor de IA preferido e insira a sua chave de API pessoal.")

    provider_options = ["Google Gemini", "OpenAI (ChatGPT)"]
    user_provider = user_data.get('ai_provider_preference', 'Google Gemini')
    
    selected_provider = st.radio(
        "Selecione o seu Provedor de IA:",
        provider_options,
        index=provider_options.index(user_provider) if user_provider in provider_options else 0,
        horizontal=True
    )

    if selected_provider != user_provider:
        update_user_configs(email, {'ai_provider_preference': selected_provider})
        st.rerun()

    st.divider()

    if selected_provider == "Google Gemini":
        st.markdown("##### Configuração do Google Gemini")
        key_exists = 'encrypted_gemini_key' in user_data and user_data['encrypted_gemini_key']
        if key_exists: st.success("Uma chave de API do Gemini já está configurada.", icon="✅")
        
        with st.form("gemini_form"):
            api_key_input = st.text_input("Chave de API do Google Gemini", type="password", placeholder="Cole a sua chave aqui para adicionar ou alterar")
            
            GEMINI_MODELS = {
                "Flash (Rápido, Multimodal)": "gemini-flash-latest",
                "Pro (Avançado, Estável)": "gemini-pro-latest"
            }
            current_model_id = user_data.get('ai_model_preference', 'gemini-1.5-flash-latest')
            model_names_list = list(GEMINI_MODELS.keys())
            default_model_index = model_names_list.index(next((name for name, model_id in GEMINI_MODELS.items() if model_id == current_model_id), "Flash (Rápido, Multimodal)"))
            
            selected_model_name = st.selectbox("Modelo Gemini Preferido:", options=model_names_list, index=default_model_index)
            st.caption("[Crie uma chave gratuitamente no Google AI Studio](https://aistudio.google.com/app/apikey)")
            
            s1, s2 = st.columns(2)
            if s1.form_submit_button("Salvar Configurações Gemini", use_container_width=True, type="primary"):
                updates = {'ai_model_preference': GEMINI_MODELS[selected_model_name]}
                if api_key_input:
                    updates['encrypted_gemini_key'] = encrypt_token(api_key_input)
                update_user_configs(email, updates)
                st.success("Configurações do Gemini guardadas!"); st.rerun()
            if s2.form_submit_button("Remover Chave", use_container_width=True, disabled=not key_exists):
                update_user_configs(email, {'encrypted_gemini_key': None})
                st.success("Chave do Gemini removida!"); st.rerun()

    elif selected_provider == "OpenAI (ChatGPT)":
        st.markdown("##### Configuração da OpenAI (ChatGPT)")
        st.info("Ao selecionar OpenAI, a aplicação utilizará o modelo **GPT-4o**.", icon="✨")
        
        key_exists = 'encrypted_openai_key' in user_data and user_data['encrypted_openai_key']
        if key_exists: st.success("Uma chave de API da OpenAI já está configurada.", icon="✅")

        with st.form("openai_form"):
            api_key_input = st.text_input("Chave de API da OpenAI", type="password", placeholder="Cole a sua chave de API aqui (sk-...)")
            st.caption("[Crie uma chave no site da OpenAI](https://platform.openai.com/api-keys)")

            s1, s2 = st.columns(2)
            if s1.form_submit_button("Salvar Chave OpenAI", use_container_width=True, type="primary"):
                if api_key_input:
                    update_user_configs(email, {'encrypted_openai_key': encrypt_token(api_key_input)})
                    st.success("Chave da OpenAI guardada!"); st.rerun()
                else:
                    st.warning("Por favor, insira uma chave para salvar.")
            if s2.form_submit_button("Remover Chave", use_container_width=True, disabled=not key_exists):
                update_user_configs(email, {'encrypted_openai_key': None})
                st.success("Chave da OpenAI removida!"); st.rerun()

with tab_tokens:
    st.subheader("Configuração do Figma")
    st.info("Para utilizar a funcionalidade de gerar histórias a partir do Figma, é necessário fornecer o seu Token de Acesso Pessoal.")
    
    with st.form("figma_token_form"):
        figma_token_encrypted = user_data.get('encrypted_figma_token')
        figma_token_status = "✅ Token configurado." if figma_token_encrypted else "❌ Nenhum token configurado."
        
        st.caption(f"Status do Token do Figma: {figma_token_status}")
        
        figma_token = st.text_input(
            "Seu Token de Acesso Pessoal do Figma",
            type="password",
            placeholder="Insira aqui para salvar ou atualizar",
            help="Pode gerar um novo token nas configurações do seu perfil no Figma."
        )

        if st.form_submit_button("Salvar Token do Figma", use_container_width=True, type="primary"):
            if figma_token:
                updates = {'encrypted_figma_token': encrypt_token(figma_token)}
                update_user_configs(st.session_state['email'], updates)
                st.success("O seu token do Figma foi salvo com sucesso!")
                st.rerun()
            else:
                st.warning("Por favor, insira um token para salvar.")
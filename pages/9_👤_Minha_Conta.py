# pages/9_👤_Minha_Conta.py

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
    st.warning("⚠️ Por favor, faça login para acessar."); st.page_link("0_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑"); st.stop()
if check_session_timeout():
    st.warning(f"Sua sessão expirou por inatividade de {SESSION_TIMEOUT_MINUTES} minutos. Por favor, faça login novamente.")
    st.page_link("0_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑"); st.stop()
if 'jira_client' not in st.session_state:
    st.warning("⚠️ Nenhuma conexão Jira ativa."); st.page_link("pages/8_🔗_Conexões_Jira.py", label="Ativar uma Conexão", icon="🔗"); st.stop()

email = st.session_state['email']
user_data = find_user(email)

# Força a leitura das configurações globais mais recentes usando a função cacheada,
# em vez de depender de uma versão potencialmente desatualizada no session_state.
global_configs = get_global_configs()

with st.sidebar:
    project_root = Path(__file__).parent.parent
    logo_path = project_root / "images" / "gauge-logo.svg"
    try:
        st.logo(logo_path, size="large")
    except (FileNotFoundError, AttributeError):
        st.write("Gauge Metrics") 
    
    if st.session_state.get("email"):
        st.markdown(f"🔐 Logado como: **{st.session_state['email']}**")
    if st.button("Logout", use_container_width=True, type='secondary'):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.switch_page("0_🔑_Autenticação.py")

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
                    elif not verify_password(current_password, user_data.get('hashed_password') or user_data.get('password')):
                        st.error("A 'Senha Atual' está incorreta.")
                    elif len(new_password) < 8:
                        st.error("A nova senha deve ter pelo menos 8 caracteres.")
                    elif new_password != confirm_password:
                        st.error("A 'Nova Senha' e a 'Confirmação' não coincidem.")
                    else:
                        new_hashed_password = get_password_hash(new_password)
                        update_user_password(email, new_hashed_password)
                        st.success("Senha alterada com sucesso!")

with tab_campos:
    st.subheader("Preferências de Campos para Análise")
    st.caption("Ative os campos que você deseja que apareçam como opções nas páginas de análise. As alterações são guardadas para o seu perfil.")

    toggles_std, toggles_custom = {}, {}
    tab_std, tab_custom = st.tabs(["🗂️ Campos Padrão", "✨ Campos Personalizados"])
    
    # --- Carregamento de dados movido para cima ---
    # Isto é necessário para que a 'id_to_name_map' esteja disponível na aba custom
    available_custom_fields = global_configs.get('custom_fields', [])
    id_to_name_map = {
        field['id']: field['name'] 
        for field in available_custom_fields 
        if 'id' in field and 'name' in field
    }
    # --- Fim do carregamento de dados ---

    with tab_std:
        available_standard_fields_config = global_configs.get('available_standard_fields', {})
    
        STANDARD_FIELDS_MAP = st.session_state.get('standard_fields_map', {})
            
        # Filtra apenas os campos que o Admin ativou
        available_standard_fields_ids = list(available_standard_fields_config.keys())
        user_selected_standard = user_data.get('standard_fields', [])
        
        if not available_standard_fields_ids:
            st.info("Nenhum campo padrão foi configurado pelo administrador.")
        else:
            st.markdown("**Ative os campos padrão que deseja usar:**")
            
            # Ordena por nome amigável, não por ID
            sorted_fields_to_show = sorted(
                available_standard_fields_ids, 
                key=lambda field_id: STANDARD_FIELDS_MAP.get(field_id, field_id)
            )

            for field_id in sorted_fields_to_show:
                # Busca o nome amigável (ex: "Categoria de Status") do JSON
                display_name = STANDARD_FIELDS_MAP.get(field_id, field_id)
                # O valor salvo no utilizador (user_selected_standard) é o ID (ex: "StatusCategory")
                toggles_std[field_id] = st.toggle(
                    display_name, 
                    value=(field_id in user_selected_standard), 
                    key=f"toggle_std_{field_id}"
                )

        # --- BOTÃO 1: SALVAR CAMPOS PADRÃO ---
        st.divider()
        if st.button("Salvar Campos Padrão", key="save_std_fields", use_container_width=True, type="primary"):
            # A lógica de salvar agora usa os IDs (keys)
            new_selection_std = [field_id for field_id, is_on in toggles_std.items() if is_on]
            
            updates_to_save = {'standard_fields': new_selection_std}
            update_user_configs(email, updates_to_save) 

            st.success("Suas preferências de campos padrão foram guardadas!")
            st.rerun()

with tab_custom:
        
        # 1. Carregar o que está salvo (o 'id_to_name_map' já foi carregado na aba anterior)
        old_list_by_name = user_data.get('enabled_custom_fields', []) # Lista de Nomes (ex: "Story Points")
        new_list_by_id = user_data.get('enabled_custom_field_ids', []) # Lista de IDs (ex: "customfield_10042")

        # 2. Lógica de Migração (executa uma vez)
        # Se a lista antiga (por nome) existe E a lista nova (por ID) não existe, migramos.
        if old_list_by_name and not new_list_by_id:
            st.info("A migrar as suas configurações de campos personalizados para o novo formato (baseado em ID)...")
            
            # Constrói um mapa reverso (Nome -> ID)
            # Isto pode falhar se houver nomes duplicados, mas é a melhor tentativa
            name_to_id_map_reverse = {name: fid for fid, name in id_to_name_map.items()}
            
            # Converte os nomes salvos de volta para IDs
            migrated_ids = [name_to_id_map_reverse.get(name) for name in old_list_by_name if name_to_id_map_reverse.get(name)]
            
            # Salva a nova lista de IDs e limpa a antiga
            updates_to_save = {
                'enabled_custom_field_ids': list(set(migrated_ids)), # Remove duplicados da migração
                'enabled_custom_fields': [] # Limpa a lista antiga
            }
            update_user_configs(email, updates_to_save)
            st.success("Migração concluída! Por favor, verifique as suas seleções.")
            st.rerun()
        
        # 3. Lógica de Exibição (agora usa a 'new_list_by_id' como fonte)
        if not available_custom_fields:
            st.info("Nenhum campo personalizado foi configurado pelo administrador.")
        else:
            st.markdown("**Ative os campos personalizados que deseja usar:**")
            
            # Ordena por nome para uma exibição amigável
            for field in sorted(available_custom_fields, key=lambda x: x.get('name', '')):
                field_id = field.get('id')
                field_name = field.get('name')
                
                if not field_id or not field_name:
                    continue
                    
                display_label = f"{field_name} ({field_id})"
                
                # A verificação agora é feita pelo ID
                is_currently_enabled = field_id in new_list_by_id
                
                toggles_custom[field_id] = st.toggle(
                    display_label, 
                    value=is_currently_enabled, 
                    key=f"toggle_custom_{field_id}"
                )
        
        # --- BOTÃO 2: SALVAR CAMPOS PERSONALIZADOS (CORRIGIDO) ---
        st.divider()
        if st.button("Salvar Campos Personalizados", key="save_custom_fields", use_container_width=True, type="primary"):
            
            # A lógica de salvar agora usa os IDs (keys)
            new_selection_custom_ids = [
                field_id for field_id, is_on in toggles_custom.items() if is_on
            ]
            
            updates_to_save = {
                'enabled_custom_field_ids': list(set(new_selection_custom_ids)), # Salva a nova lista (por ID)
                'enabled_custom_fields': [] # Garante que a lista antiga (por Nome) está limpa
            }
            
            update_user_configs(email, updates_to_save) 

            st.success("Suas preferências de campos personalizados (por ID) foram guardadas!")
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

    st.divider()

    if selected_provider == "Google Gemini":
        st.markdown("##### Configuração do Google Gemini")
        key_exists = 'encrypted_gemini_key' in user_data and user_data['encrypted_gemini_key']
        if key_exists: st.success("Uma chave de API do Gemini já está configurada.", icon="✅")
        
        with st.form("gemini_form"):
            api_key_input = st.text_input("Chave de API do Google Gemini", type="password", placeholder="Cole a sua chave aqui para adicionar ou alterar")
            
            GEMINI_MODELS = {"Flash (Rápido, Multimodal)": "gemini-flash-latest", "Pro (Avançado, Estável)": "gemini-pro-latest"}
            current_model_id = user_data.get('ai_model_preference', 'gemini-1.5-flash-latest')
            model_names_list = list(GEMINI_MODELS.keys())
            default_model_index = model_names_list.index(next((name for name, model_id in GEMINI_MODELS.items() if model_id == current_model_id), "Flash (Rápido, Multimodal)"))
            
            selected_model_name = st.selectbox("Modelo Gemini Preferido:", options=model_names_list, index=default_model_index)
            st.caption("[Crie uma chave gratuitamente no Google AI Studio](https://aistudio.google.com/app/apikey)")
            
            s1, s2 = st.columns(2)
            if s1.form_submit_button("Salvar Configurações Gemini", use_container_width=True, type="primary"):
                updates = {'ai_provider_preference': selected_provider, 'ai_model_preference': GEMINI_MODELS[selected_model_name]}
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
                updates = {'ai_provider_preference': selected_provider}
                if api_key_input:
                    updates['encrypted_openai_key'] = encrypt_token(api_key_input)
                    update_user_configs(email, updates)
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
        
        figma_token = st.text_input("Seu Token de Acesso Pessoal do Figma", type="password", placeholder="Insira aqui para salvar ou atualizar", help="Pode gerar um novo token nas configurações do seu perfil no Figma.")

        if st.form_submit_button("Salvar Token do Figma", use_container_width=True, type="primary"):
            if figma_token:
                updates = {'encrypted_figma_token': encrypt_token(figma_token)}
                update_user_configs(st.session_state['email'], updates)
                st.success("O seu token do Figma foi salvo com sucesso!"); st.rerun()
            else:
                st.warning("Por favor, insira um token para salvar.")
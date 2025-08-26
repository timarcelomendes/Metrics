# pages/9_🚀_Gerador_de_Histórias_(IA).py

import streamlit as st
import requests
import json
import base64
import re
from jira import JIRAError
from security import decrypt_token
from jira_connector import get_project_issue_types
from utils import get_ai_user_story_from_figma, get_ai_user_story_from_text
from pathlib import Path

# --- Funções de Ajuda ---
def parse_figma_url(url):
    """Extrai o file_key e o node_id de um URL do Figma."""
    match = re.search(r'figma\.com/(?:file|design)/([A-Za-z0-9]+)/.*?node-id=([0-9%A-F-]+)', url)
    if match:
        file_key = match.group(1)
        node_id_url = match.group(2)
        # Converte o formato do URL (ex: 123-45) para o formato da API (ex: 123:45)
        node_id_api = node_id_url.replace('-', ':').replace('%3A', ':')
        return file_key, node_id_url, node_id_api
    return None, None, None

def create_jira_issue(jira_domain, jira_email, jira_token, jira_project_key, story, issuetype_name):
    """Cria uma única issue no Jira, com a formatação BDD completa."""
    jira_url_endpoint = f"{jira_domain}/rest/api/3/issue"
    auth_string = f"{jira_email}:{jira_token}"
    
    jira_headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Basic {base64.b64encode(auth_string.encode()).decode()}"
    }
    
    description_content = [
        {"type": "paragraph", "content": [{"type": "text", "text": "Link para o Elemento no Figma: ", "marks": [{"type": "strong"}]}, {"type": "text", "text": story['figma_link']}]},
        {"type": "rule"},
        {"type": "paragraph", "content": [{"type": "text", "text": "Job Story:", "marks": [{"type": "strong"}]}]},
        {"type": "paragraph", "content": [{"type": "text", "text": story['description']}]},
        {"type": "rule"},
        {"type": "paragraph", "content": [{"type": "text", "text": "Critérios de Aceitação:", "marks": [{"type": "strong"}]}]},
        {"type": "bulletList", "content": [{"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": criteria.strip()}]}]} for criteria in story['acceptance_criteria'].split('\n') if criteria.strip()]},
        {"type": "rule"},
        {"type": "paragraph", "content": [{"type": "text", "text": "Cenários de Teste (BDD):", "marks": [{"type": "strong"}]}]},
        {"type": "paragraph", "content": [{"type": "text", "text": story['bdd_scenarios']}]}
    ]

    jira_payload = {
        "fields": {
            "project": {"key": jira_project_key},
            "summary": story['title'],
            "description": {"type": "doc", "version": 1, "content": description_content},
            "issuetype": {"name": issuetype_name}
        }
    }
    
    try:
        response = requests.post(jira_url_endpoint, headers=jira_headers, data=json.dumps(jira_payload))
        response.raise_for_status()
        return response.json().get('key')
    except requests.exceptions.HTTPError as e:
        st.error(f"Erro ao criar issue no Jira (Status {e.response.status_code}):")
        st.code(e.response.text, language="json")
        return None

# --- Configurações da Página e Autenticação ---
st.set_page_config(page_title="Gerador de Histórias com IA", page_icon="🚀", layout="wide")
st.title("🚀 Gerador de Histórias com IA")
st.markdown("Crie histórias de usuário a partir de uma tela do Figma ou de uma simples descrição.")

if 'email' not in st.session_state:
    st.warning("⚠️ Por favor, faça login para aceder."); st.page_link("1_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑"); st.stop()
if 'jira_client' not in st.session_state:
    st.warning("⚠️ Nenhuma conexão Jira ativa."); st.page_link("pages/2_🔗_Conexões_Jira.py", label="Ativar uma Conexão", icon="🔗"); st.stop()

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

# --- Seleção de Modo ---
creation_mode = st.radio(
    "Como deseja começar?",
    ["Analisar Elemento do Figma", "Descrever a Ideia"],
    horizontal=True,
    key="creation_mode_selector"
)
st.markdown("---")

# --- MODO 1: FIGMA PARA JIRA ---
if creation_mode == "Analisar Elemento do Figma":
    st.header("1. Cole o Link do Elemento do Figma")
    figma_url_input = st.text_input("URL do Elemento no Figma*", help="No Figma, selecione o elemento (tela, componente, etc.) e copie o URL do navegador.")

    if st.button("Buscar Elemento", use_container_width=True):
        if not figma_url_input:
            st.warning("⚠️ Por favor, insira o URL do elemento do Figma.")
        else:
            file_key, url_node_id, api_node_id = parse_figma_url(figma_url_input)
            if not file_key or not url_node_id:
                st.error("URL do Figma inválido.")
            else:
                with st.spinner("A buscar no Figma..."):
                    try:
                        figma_headers = {'X-Figma-Token': st.secrets['FIGMA_ACCESS_TOKEN']}
                        
                        node_details_url = f"https://api.figma.com/v1/files/{file_key}/nodes?ids={url_node_id}"
                        response_details = requests.get(node_details_url, headers=figma_headers)
                        response_details.raise_for_status()
                        node_data = response_details.json()['nodes'][api_node_id]['document']
                        
                        image_url_req = f"https://api.figma.com/v1/images/{file_key}?ids={url_node_id}&format=png&scale=2"
                        response_image = requests.get(image_url_req, headers=figma_headers)
                        response_image.raise_for_status()
                        image_data = response_image.json()

                        if not image_data.get('images') or not image_data['images'].get(api_node_id):
                            st.error(f"Não foi possível renderizar a imagem para o nó selecionado.", icon="🖼️")
                        else:
                            st.session_state.figma_image_url = image_data['images'][api_node_id]
                            st.session_state.target_node_data = node_data
                            st.session_state.figma_full_url = figma_url_input
                            st.session_state.screen_fetched = True
                            st.rerun()
                    except Exception as e:
                        st.error(f"Ocorreu um erro ao buscar no Figma: {e}")

# --- MODO 2: TEXTO PARA JIRA ---
elif creation_mode == "Descrever a Ideia":
    st.header("1. Descreva a sua Ideia")
    user_context_text = st.text_area("Contexto da História*", height=200, placeholder="Descreva a funcionalidade ou o problema...")
    
    if st.button("Gerar História com Gauge AI", use_container_width=True):
        if not user_context_text:
            st.warning("Por favor, preencha o campo de contexto.")
        else:
            with st.spinner("Gauge AI está a escrever a história..."):
                generated_story = get_ai_user_story_from_text(user_context_text)
                st.session_state.generated_story = generated_story
                st.session_state.story_generated = True

# --- PASSO 2 (COMUM): GERAR HISTÓRIA ---
if st.session_state.get('screen_fetched') and not st.session_state.get('story_generated'):
    st.header("2. Gerar História com IA")
    target_node = st.session_state.target_node_data
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.image(st.session_state.figma_image_url, caption=f"Elemento: {target_node['name']}")
    with col2:
        st.info(f"Análise focada no elemento: **{target_node['name']}**")
        user_context_figma = st.text_area("Adicione contexto para a IA (Opcional)", height=200)
        
        if st.button("Gerar História com Gauge AI", use_container_width=True):
            with st.spinner("Gauge AI está a analisar o elemento e a escrever a história..."):
                generated_story = get_ai_user_story_from_figma(
                    st.session_state.figma_image_url, 
                    user_context_figma,
                    target_node['name']
                )
                st.session_state.generated_story = generated_story
                st.session_state.story_generated = True

# --- PASSO 3 (FINAL): CRIAR ISSUE NO JIRA ---
if st.session_state.get('story_generated'):
    st.header("3. Criar Issue no Jira")
    story_data = st.session_state.generated_story
    
    active_conn = st.session_state.get('active_connection', {})
    projects = st.session_state.get('projects', {})
    
    selected_project_name = st.selectbox("Selecione o Projeto do Jira*", options=list(projects.keys()), key="jira_project_selector")
    jira_project_key = projects.get(selected_project_name)

    jira_issuetype = None
    if jira_project_key:
        issue_types = get_project_issue_types(st.session_state.jira_client, jira_project_key)
        if issue_types:
            jira_issuetype = st.selectbox("Selecione o Tipo de Issue:", options=issue_types, key="jira_issuetype_selector")
    
    with st.form("jira_form"):
        st.info("Revise a história de usuário gerada pela IA e crie a issue no Jira.")
        
        title = st.text_input("Título da História", value=story_data.get('title', ''))
        description = st.text_area("Descrição (Job Story)", value=story_data.get('description', ''), height=150)
        acceptance_criteria = st.text_area("Critérios de Aceitação", value=story_data.get('acceptance_criteria', ''), height=200)
        bdd_scenarios = st.text_area("Cenários de Teste (BDD)", value=story_data.get('bdd_scenarios', ''), height=200)
        
        create_button = st.form_submit_button("Criar Issue no Jira", type="primary", use_container_width=True, disabled=(jira_issuetype is None))

    if create_button:
        jira_api_token = decrypt_token(active_conn.get('encrypted_token'))
        
        final_story = {
            'title': title,
            'description': description,
            'acceptance_criteria': acceptance_criteria,
            'bdd_scenarios': bdd_scenarios,
            'frame_name': st.session_state.get('target_node_data', {}).get('name', 'N/A'),
            'figma_link': st.session_state.get('figma_full_url', 'N/A')
        }

        with st.spinner("A criar a issue..."):
            issue_key = create_jira_issue(
                jira_domain=active_conn.get('jira_url', ''),
                jira_email=active_conn.get('jira_email', ''),
                jira_token=jira_api_token,
                jira_project_key=jira_project_key,
                story=final_story,
                issuetype_name=jira_issuetype
            )
        
        if issue_key:
            st.balloons()
            st.success(f"🎉 Processo concluído! Issue '{issue_key}' criada com sucesso.")
            for key in ['screen_fetched', 'story_generated', 'generated_story', 'target_node_data', 'figma_full_url']:
                if key in st.session_state: del st.session_state[key]
# pages/Avaliacao.py

import streamlit as st
from security import (
    validate_assessment_token, 
    save_assessment_response, 
    mark_token_as_used, 
    get_user_product_hub_data,
    get_global_configs
)
import pandas as pd
from datetime import datetime
import re

# --- Configuração da Página ---
st.set_page_config(page_title="Autoavaliação de Competências", page_icon="📝", layout="wide")
st.header("📝 Autoavaliação de Competências", divider='rainbow')

# Se a avaliação já foi submetida com sucesso nesta sessão, exibe a mensagem final e para.
if st.session_state.get("submission_complete"):
    st.success("Avaliação submetida com sucesso! Obrigado pela sua participação.")
    st.balloons()
    st.info("Pode fechar esta página.")
    st.stop()

# --- 1. Validação do Token ---
query_params = st.query_params
token_from_url = query_params.get("token")
token = None

if isinstance(token_from_url, list) and token_from_url:
    token = token_from_url[0]
elif isinstance(token_from_url, str):
    token = token_from_url

if not token:
    st.error("URL inválido. O link de avaliação deve conter um token de acesso.")
    st.stop()

token_info = validate_assessment_token(token)
if not token_info:
    st.error("Link de avaliação inválido, expirado ou já utilizado. Por favor, solicite um novo link.")
    st.stop()

hub_owner_email = token_info["hub_owner_email"]
evaluated_email = token_info["evaluated_email"]

# Carrega as competências a partir das configurações GLOBAIS
global_configs = get_global_configs()
framework = global_configs.get('competency_framework', {})
all_competencies = framework.get('hard_skills', []) + framework.get('soft_skills', [])

if not all_competencies:
    st.error("Nenhum framework de competências foi configurado para esta avaliação.")
    st.stop()

st.info(f"A avaliar o desempenho de: **{evaluated_email}**")
st.caption("Por favor, avalie as competências de 1 a 5 (1 = Pouco desenvolvido, 5 = Totalmente desenvolvido).")

# --- 2. Inicialização e Carregamento dos Dados da Avaliação ---
if 'assessment_data' not in st.session_state:
    st.session_state.assessment_data = {}
    for comp_data in all_competencies:
        comp_name = comp_data.get("Competência")
        if comp_name:
            st.session_state.assessment_data[comp_name] = {"leader": {"level": 0, "pdi": ""}, "member": {"level": 0, "pdi": ""}}
    
    hub_owner_data = get_user_product_hub_data(hub_owner_email)
    existing_evals = hub_owner_data.get("avaliacoes", {}).get(evaluated_email, {})
    
    if existing_evals and isinstance(existing_evals, dict):
        eval_data_to_load = existing_evals.get('data', existing_evals)
        for comp, data in eval_data_to_load.items():
            if comp in st.session_state.assessment_data and isinstance(data, dict):
                st.session_state.assessment_data[comp] = data

# --- 3. Função para Renderizar o Formulário ---
def render_evaluation_ui(eval_type, skills_list):
    if not skills_list: 
        st.info("Nenhuma competência deste tipo foi definida.")
        return
        
    for skill in skills_list:
        comp = skill['Competência']
        if comp in st.session_state.assessment_data:
            st.markdown(f"**{comp}**")
            level = st.slider("Nível", 1, 5, value=st.session_state.assessment_data[comp][eval_type]['level'], key=f"level_{eval_type}_{comp}")
            pdi = st.text_area("Plano de Desenvolvimento / Comentários", value=st.session_state.assessment_data[comp][eval_type]['pdi'], key=f"pdi_{eval_type}_{comp}", height=100)
            st.session_state.assessment_data[comp][eval_type]['level'] = level
            st.session_state.assessment_data[comp][eval_type]['pdi'] = pdi
            st.markdown("---")

# --- 4. Exibição das Abas e do Formulário ---
tab_leader, tab_member = st.tabs(["**Avaliação como Líder**", "**Autoavaliação como Membro**"])
with tab_leader:
    st.subheader("Competências de Liderança")
    render_evaluation_ui('leader', all_competencies)

with tab_member:
    st.subheader("Competências como Membro da Equipa")
    render_evaluation_ui('member', all_competencies)

st.divider()

# --- 5. Secção de Confirmação e Validação ---
st.subheader("Confirmação de Envio")
responder_name = st.text_input("O seu nome completo*", placeholder="Insira o seu nome e sobrenome")
responder_email = st.text_input("O seu e-mail profissional*", placeholder="Insira o seu e-mail para validação")

is_name_valid = ' ' in responder_name.strip()
is_email_valid_format = re.fullmatch(r'([A-Za-z0-9]+[.-_])*[A-Za-z0-9]+@[A-Za-z0-9-]+(\.[A-Z|a-z]{2,})+', responder_email)
allowed_domains = global_configs.get("allowed_domains", []) 
is_email_domain_valid = any(responder_email.endswith(f"@{domain}") for domain in allowed_domains) if allowed_domains else True

if responder_name and not is_name_valid:
    st.warning("Por favor, insira o seu nome e sobrenome.")
if responder_email and not is_email_valid_format:
    st.warning("Por favor, insira um formato de e-mail válido.")
elif responder_email and not is_email_domain_valid:
    st.error(f"O domínio do seu e-mail não é permitido. Domínios aceites: {', '.join(allowed_domains)}")

agree_checkbox = st.checkbox(f"Eu, {responder_name or '...'}, confirmo que as informações prestadas são verdadeiras e representam a minha avaliação honesta.")

# --- 6. Lógica de Submissão ---
is_form_valid = is_name_valid and is_email_valid_format and is_email_domain_valid and agree_checkbox
if st.button("Submeter Avaliação", type="primary", use_container_width=True, disabled=not is_form_valid):
    with st.spinner("A guardar a sua avaliação..."):
        final_assessment_payload = {
            "responder_name": responder_name,
            "responder_email": responder_email,
            "submission_date": datetime.utcnow().isoformat(),
            "data": st.session_state.assessment_data
        }
        
        success = save_assessment_response(hub_owner_email, evaluated_email, final_assessment_payload)
        
        if success:
            mark_token_as_used(token)
            # Define o estado de sucesso e recarrega a página
            st.session_state.submission_complete = True
            st.rerun()
        else:
            st.error("Ocorreu um erro ao guardar a sua avaliação. O utilizador dono do hub pode não ter sido encontrado ou a operação falhou. Por favor, tente novamente.")
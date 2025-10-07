# pages/15_📝_Auto_Avaliação.py

import streamlit as st
from security import validate_assessment_token, save_assessment_response, mark_token_as_used, find_user
import pandas as pd

st.set_page_config(page_title="Autoavaliação de Competências", page_icon="📝", layout="wide")

st.header("📝 Autoavaliação de Competências", divider='rainbow')

# --- Validação do Token ---
query_params = st.query_params
token = query_params.get("token")

if not token:
    st.error("URL inválido. O link de avaliação deve conter um token de acesso.")
    st.stop()

# Valida o token e obtém o e-mail associado
user_email = validate_assessment_token(token)

if not user_email:
    st.error("Link de avaliação inválido, expirado ou já utilizado. Por favor, solicite um novo link ao administrador.")
    st.stop()

# --- Carregamento dos Dados do Formulário ---
# Para garantir que as competências e papéis são os mesmos que os definidos no Product Hub,
# precisamos de uma forma de os carregar. Idealmente, eles estariam numa configuração global.
# Por agora, vamos defini-los estaticamente, mas o ideal seria ler de 'get_global_configs()'.
COMPETENCIAS_PADRAO = ["Metodologias Ágeis", "Comunicação clara", "Trabalho em equipe", "Ferramentas de gestão"]
PAPEIS_PADRAO = ["Liderança de Produto", "Membro da Equipa"]

st.info(f"A avaliar o desempenho de: **{user_email}**")
st.caption("Por favor, avalie as competências de 1 a 5, onde 1 é 'Pouco desenvolvido' e 5 é 'Totalmente desenvolvido'.")

# --- Construção do Formulário de Avaliação ---
if 'assessment_data' not in st.session_state:
    st.session_state.assessment_data = {comp: {"leader": {"level": 0, "pdi": ""}, "member": {"level": 0, "pdi": ""}} for comp in COMPETENCIAS_PADRAO}

# Tenta carregar dados existentes para pré-preencher
user_data = find_user(user_email)
if user_data:
    existing_evals = user_data.get("product_hub_data", {}).get("avaliacoes", {}).get(user_email, {})
    if existing_evals:
        for comp, data in existing_evals.items():
            if comp in st.session_state.assessment_data:
                st.session_state.assessment_data[comp] = data

form_cols = st.columns(len(COMPETENCIAS_PADRAO))

for i, comp in enumerate(COMPETENCIAS_PADRAO):
    with form_cols[i]:
        st.subheader(comp)
        
        # Avaliação para o papel de Liderança
        st.markdown("**Como Líder:**")
        level_leader = st.slider(
            "Nível (Líder)", 1, 5, 
            st.session_state.assessment_data[comp]["leader"]["level"], 
            key=f"level_leader_{comp}"
        )
        pdi_leader = st.text_area(
            "Plano de Desenvolvimento (Líder)", 
            st.session_state.assessment_data[comp]["leader"]["pdi"], 
            key=f"pdi_leader_{comp}",
            height=100
        )
        st.session_state.assessment_data[comp]["leader"]["level"] = level_leader
        st.session_state.assessment_data[comp]["leader"]["pdi"] = pdi_leader
        
        st.divider()

        # Avaliação para o papel de Membro da Equipa
        st.markdown("**Como Membro da Equipa:**")
        level_member = st.slider(
            "Nível (Membro)", 1, 5, 
            st.session_state.assessment_data[comp]["member"]["level"], 
            key=f"level_member_{comp}"
        )
        pdi_member = st.text_area(
            "Plano de Desenvolvimento (Membro)", 
            st.session_state.assessment_data[comp]["member"]["pdi"], 
            key=f"pdi_member_{comp}",
            height=100
        )
        st.session_state.assessment_data[comp]["member"]["level"] = level_member
        st.session_state.assessment_data[comp]["member"]["pdi"] = pdi_member

st.divider()

if st.button("Submeter Avaliação", type="primary", use_container_width=True):
    with st.spinner("A guardar a sua avaliação..."):
        success = save_assessment_response(user_email, st.session_state.assessment_data)
        if success:
            mark_token_as_used(token)
            st.success("Avaliação submetida com sucesso! Obrigado pela sua participação.")
            st.balloons()
            # Limpa o formulário e impede nova submissão
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.info("Pode fechar esta página.")
        else:
            st.error("Ocorreu um erro ao guardar a sua avaliação. Por favor, tente novamente.")
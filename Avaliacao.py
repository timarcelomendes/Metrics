# pages/Avaliacao.py - CÓDIGO FINAL COM HEADER E LAYOUT DINÂMICO

import streamlit as st
import pandas as pd
from security import *
from pathlib import Path


st.markdown("""
<style>

    /* 1. Oculta a barra lateral com prioridade máxima */
    [data-testid="stSidebar"] {
        display: none !important;
    }

    /* 2. Encontra o contentor principal da aplicação e remove a margem 
          que o Streamlit reserva para a barra lateral. */
    div[data-testid="stAppViewContainer"] {
        margin-left: 0px !important;
    }

    /* 3. Garante que o bloco de conteúdo principal não tenha um
           padding excessivo que o empurre para fora da tela. */
    section[data-testid="main-block"] {
        padding-left: 2rem !important;
        padding-right: 2rem !important;
    }
</style>
""", unsafe_allow_html=True)

# 1. Define o layout padrão se não estiver definido na sessão
if 'avaliacao_layout' not in st.session_state:
    st.session_state.avaliacao_layout = 'centered'

# 2. Configura a página com o layout guardado na sessão
st.set_page_config(
    page_title="Avaliação de Competências",
    page_icon="📝",
    layout=st.session_state.avaliacao_layout
)

# --- Carregamento e Validação do Token ---
try:
    token = st.query_params["token"]
    payload = verify_assessment_token(token)
    if not payload:
        st.error("❌ Token de avaliação inválido ou expirado. Por favor, solicite um novo link.")
        st.stop()
except KeyError:
    st.error("❌ Link de avaliação inválido. Nenhum token foi fornecido.")
    st.stop()

# Armazena informações do token
st.session_state.update(token=token, hub_owner_email=payload['hub_owner_email'], evaluated_member_name=payload['evaluated_email'])

# Carrega o framework de competências
if 'competency_framework' not in st.session_state:
    st.session_state.competency_framework = get_global_configs().get('competency_framework', {})

# Inicializa o dicionário de respostas
if 'current_evaluation' not in st.session_state:
    st.session_state.current_evaluation = {}

# O caminho para a imagem é relativo à localização do script
image_path = Path(__file__).parent.parent / "images" / "avaliacao.jpg"
st.image(str(image_path))


# --- Interface Principal ---
st.title("📝 Avaliação de Competências")

# Coloca o toggle de forma discreta
with st.container():
    col1, col_spacer, col2 = st.columns([3, 1, 1])
    with col1:
        st.info("A sua perspectiva é fundamental para o desenvolvimento contínuo. Por favor, avalie as competências abaixo.")
    with col2:
        use_wide_layout = st.toggle(
            "Tela cheia",
            value=(st.session_state.avaliacao_layout == "wide"),
            key='layout_toggle',
            help="Ative para que o conteúdo ocupe toda a largura do ecrã."
        )
        current_layout = 'wide' if use_wide_layout else 'centered'
        if current_layout != st.session_state.avaliacao_layout:
            st.session_state.avaliacao_layout = current_layout
            st.rerun()

st.divider()

st.subheader("Sua Autoavaliação")
st.markdown(f"**Nome:** `{st.session_state.get('evaluated_member_name', 'N/A')}`")
responder_name = st.text_input("Por favor, confirme o seu nome para submeter*", help="O seu nome será gravado junto com a avaliação.")

# --- Níveis de Competência (Legenda) ---
SKILL_LEVELS = {
    0: {"name": "Não Avaliado", "desc": "Ainda não foi definido um nível para esta competência."},
    1: {"name": "Iniciante", "desc": "Possui conhecimento teórico, mas precisa de supervisão constante para aplicar na prática."},
    2: {"name": "Iniciante Avançado", "desc": "Consegue aplicar a competência em tarefas simples e com alguma supervisão."},
    3: {"name": "Proficiente", "desc": "Atua de forma autônoma na maioria das situações e pode orientar os menos experientes."},
    4: {"name": "Avançado", "desc": "Domina a competência em cenários complexos, sendo uma referência para o time."},
    5: {"name": "Especialista", "desc": "É uma referência na empresa, inova e mentora outros, influenciando a estratégia."}
}

# --- Função para Renderizar a UI de Avaliação ---
def render_evaluation_ui(skills_list):
    if not skills_list:
        st.info("Nenhuma competência deste tipo foi definida no framework.")
        return
    
    for skill in skills_list:
        with st.container(border=True):
            comp = skill['Competência']
            st.session_state.current_evaluation.setdefault(comp, {"member": {"level": 0, "pdi": ""}})
            eval_data = st.session_state.current_evaluation[comp]['member']

            st.markdown(f"<h5>{skill['Competência']}</h5>", unsafe_allow_html=True)
            st.caption(skill.get('Descrição', ''))

            comment_visibility_key = f"comment_visible_member_{comp}"
            col1, col2 = st.columns([2, 1])
            with col1:
                pill_options = [SKILL_LEVELS[level]['name'] for level in SKILL_LEVELS]
                current_level_index = eval_data.get('level', 0)
                default_selection = pill_options[current_level_index]
                selected_pill = st.pills("Nível", options=pill_options, default=default_selection, key=f"pills_member_{comp}", label_visibility="collapsed")
                level = pill_options.index(selected_pill)
            with col2:
                is_comment_visible = st.session_state.get(comment_visibility_key, False)
                has_existing_comment = bool(eval_data.get('pdi', ''))
                if is_comment_visible:
                    if st.button("✖️ Ocultar", key=f"btn_hide_member_{comp}", use_container_width=True, type="primary"):
                        st.session_state[comment_visibility_key] = False
                        st.rerun()
                elif has_existing_comment:
                    if st.button("📝 Editar", key=f"btn_edit_member_{comp}", use_container_width=True, type="secondary"):
                        st.session_state[comment_visibility_key] = True
                        st.rerun()
                else:
                    if st.button("💬 Adicionar", key=f"btn_add_member_{comp}", use_container_width=True, type="secondary"):
                        st.session_state[comment_visibility_key] = True
                        st.rerun()

            if st.session_state.get(comment_visibility_key, False):
                pdi = st.text_area("Comentário", value=eval_data.get('pdi', ''), key=f"pdi_member_{comp}", height=120, label_visibility="collapsed")
            else:
                pdi = eval_data.get('pdi', '')

            st.info(f"**{SKILL_LEVELS[level]['name']}:** {SKILL_LEVELS[level]['desc']}")
            
            st.session_state.current_evaluation[comp]['member']['level'] = level
            st.session_state.current_evaluation[comp]['member']['pdi'] = pdi

# --- Abas e Lógica de Submissão ---
framework = st.session_state.get('competency_framework', {})
hard_skills = framework.get('hard_skills', [])
soft_skills = framework.get('soft_skills', [])

tab_hard, tab_soft = st.tabs(["🛠️ Hard Skills", "🧠 Soft Skills"])
with tab_hard:
    st.markdown("##### Avalie as seguintes competências técnicas:")
    render_evaluation_ui(hard_skills)
with tab_soft:
    st.markdown("##### Avalie as seguintes competências comportamentais:")
    render_evaluation_ui(soft_skills)

st.divider()

is_form_valid = bool(responder_name.strip())
if not is_form_valid:
    st.warning("⚠️ Por favor, preencha o seu nome no campo 'Confirme o seu nome para submeter' antes de continuar.")

if st.button("Submeter Avaliação", type="primary", use_container_width=True, disabled=not is_form_valid, key="final_submission_button"):
    submission_data = {
        "responder_name": responder_name,
        "submission_date": pd.to_datetime('now').isoformat(),
        "data": st.session_state.get('current_evaluation', {})
    }
    
    hub_owner_email = st.session_state.get('hub_owner_email')
    evaluated_member = st.session_state.get('evaluated_member_name')

    if hub_owner_email and evaluated_member:
        owner_hub_data = get_user_product_hub_data(hub_owner_email)
        owner_hub_data.setdefault('avaliacoes', {})[evaluated_member] = submission_data
        save_user_product_hub_data(hub_owner_email, owner_hub_data)
        mark_token_as_used(st.session_state['token'])
        
        st.success("✅ Avaliação enviada com sucesso! Obrigado pela sua participação.")
        st.balloons()
        
        for key_to_del in ['token', 'hub_owner_email', 'evaluated_member_name', 'current_evaluation', 'competency_framework']:
            if key_to_del in st.session_state:
                del st.session_state[key_to_del]
        
        st.info("Pode fechar esta página com segurança.")
    else:
        st.error("❌ Ocorreu um erro: não foi possível identificar o destinatário da avaliação. O token pode ser inválido.")
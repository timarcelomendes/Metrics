# pages/13_🔖_Product Hub.py - CÓDIGO COMPLETO E CORRIGIDO

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from security import *
from pathlib import Path
from config import SESSION_TIMEOUT_MINUTES
import uuid
from streamlit_option_menu import option_menu
from utils import get_ai_team_performance_analysis

# --- Configuração da Página ---
st.set_page_config(page_title="Gauge Product Hub", page_icon="🚀", layout="wide")

st.markdown("""
<style>
/* Estilos gerais do card de avaliação */
.evaluation-card {
    border: 1px solid #e1e4e8;
    border-radius: 10px;
    padding: 20px;
    margin-bottom: 20px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.04);
}

/* --- A SOLUÇÃO DE LAYOUT E ALINHAMENTO DEFINITIVA --- */

/* 1. Cria a nossa linha de layout personalizada */
.pill-button-row {
    display: flex;
    justify-content: space-between; /* Pills à esquerda, botão à direita */
    align-items: center;            /* Alinha-os verticalmente ao centro */
    gap: 1rem;                      /* Adiciona um pequeno espaço entre eles */
}

/* 2. Garante que as pílulas ocupam o espaço necessário */
.pill-button-row > div:first-child {
    flex-grow: 1;
}

/* 3. Garante que a coluna do botão não encolhe */
.pill-button-row > div:last-child {
    flex-shrink: 0;
}
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# --- DEFINIÇÕES ESTRUTURANTIS E FUNÇÕES AUXILIARES ---
# ==============================================================================
SKILL_LEVELS = {
    0: {"name": "Não Avaliado", "desc": "Ainda não foi definido um nível para esta competência."},
    1: {"name": "Iniciante", "desc": "Possui conhecimento teórico, mas precisa de supervisão constante para aplicar na prática."},
    2: {"name": "Iniciante Avançado", "desc": "Consegue aplicar a competência em tarefas simples e com alguma supervisão. Segue processos definidos."},
    3: {"name": "Proficiente", "desc": "Atua de forma autônoma na maioria das situações. Contribui ativamente e pode orientar os menos experientes."},
    4: {"name": "Avançado", "desc": "Domina a competência em cenários complexos. É uma referência para o time e propõe melhorias nos processos."},
    5: {"name": "Especialista", "desc": "É uma referência na empresa. Inova, cria novas práticas e mentora outros, influenciando a estratégia."}
}

def get_all_competencies_from_framework(framework):
    all_competencies = []
    all_competencies.extend(framework.get('hard_skills', []))
    all_competencies.extend(framework.get('soft_skills', []))
    return all_competencies

def sync_evaluations_with_framework():
    if 'competency_framework' not in st.session_state or 'membros' not in st.session_state or st.session_state.membros.empty:
        return
    framework = st.session_state.get('competency_framework', {})
    all_competencies = get_all_competencies_from_framework(framework)
    current_competency_names = {comp.get('Competência') for comp in all_competencies if comp.get('Competência')}
    
    for member_name in st.session_state.membros['Nome'].tolist():
        if member_name not in st.session_state.avaliacoes:
            st.session_state.avaliacoes[member_name] = {}
        
        eval_data_container = st.session_state.avaliacoes[member_name]
        eval_data = eval_data_container.get('data', eval_data_container)

        for comp_name in current_competency_names:
            if comp_name not in eval_data:
                eval_data[comp_name] = {"leader": {"level": 0, "pdi": ""}, "member": {"level": 0, "pdi": ""}}
        
        for comp_name in list(eval_data.keys()):
            if comp_name not in current_competency_names:
                del eval_data[comp_name]

def save_and_rerun(message: str = "✅ Dados guardados com sucesso!"):
    """Guarda todos os dados do hub, agenda uma mensagem toast e reinicia a página."""
    user_hub_data = {
        'membros': st.session_state.membros.to_dict('records'),
        'avaliacoes': st.session_state.avaliacoes,
        'one_on_ones': st.session_state.one_on_ones,
    }
    save_user_product_hub_data(st.session_state['email'], user_hub_data)
    
    st.session_state.toast_message = message
    st.rerun()

def load_data():
    if 'hub_data_loaded' in st.session_state:
        return
    try:
        get_global_configs.clear()
    except Exception:
        pass
    
    global_configs = get_global_configs() or {}
    st.session_state.playbooks = global_configs.get('playbooks', {})
    st.session_state.competency_framework = global_configs.get('competency_framework', {})
    
    user_roles_raw = global_configs.get('user_roles', [])
    migrated_roles = [{"id": str(uuid.uuid4()), "name": role, "description": ""} if isinstance(role, str) else role for role in user_roles_raw if (isinstance(role, dict) and 'id' in role) or isinstance(role, str)]
    st.session_state.user_roles = migrated_roles

    user_hub_data = get_user_product_hub_data(st.session_state['email'])
    st.session_state.membros = pd.DataFrame(user_hub_data.get('membros', []), columns=["Nome", "Papel", "Email"])
    st.session_state.avaliacoes = user_hub_data.get('avaliacoes', {})
    st.session_state.one_on_ones = user_hub_data.get('one_on_ones', {})
          
    sync_evaluations_with_framework()
    st.session_state['hub_data_loaded'] = True

if 'toast_message' in st.session_state:
    st.toast(st.session_state.toast_message, duration="long")
    del st.session_state.toast_message 

# ==============================================================================
# --- ESTRUTURA PRINCIPAL DA PÁGINA ---
# ==============================================================================

st.markdown("<h1 style='text-align: center; color: #262730;'>🚀 Gauge Product Hub</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; font-size: 1.1rem; color: #525f7f;'>Bem-vindo ao centro de conhecimento e padrões do seu produto.</p>", unsafe_allow_html=True)
st.markdown("---")

if 'email' not in st.session_state:
    st.warning("⚠️ Por favor, faça login para acessar."); st.page_link("0_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑"); st.stop()

if check_session_timeout():
    st.warning(f"Sua sessão expirou por inatividade de {SESSION_TIMEOUT_MINUTES} minutos. Por favor, faça login novamente.")
    st.page_link("0_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑")
    st.stop()

if 'jira_client' not in st.session_state:
    user_connections = get_users_collection(st.session_state['email'])
    if not user_connections:
        st.warning("Nenhuma conexão Jira foi configurada ainda.", icon="🔌"); st.page_link("pages/8_🔗_Conexões_Jira.py", label="Configurar sua Primeira Conexão", icon="🔗"); st.stop()
    else:
        st.warning("Nenhuma conexão Jira está ativa para esta sessão.", icon="⚡"); st.page_link("pages/8_🔗_Conexões_Jira.py", label="Ativar uma Conexão", icon="🔗"); st.stop()

load_data()

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
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.switch_page("0_🔑_Autenticação.py")

# --- ABAS PRINCIPAIS ---
selected_main_tab = option_menu(
    menu_title=None,
    options=["Playbook", "Papéis", "Competências", "Gestão de Pessoas"],
    icons=['book', 'person-badge', 'gear', 'people-fill'],
    key='main_tab_selection',
    orientation="horizontal",
    styles={
        "container": {"padding": "0!important", "background-color": "#fafafa"},
        "icon": {"color": "orange", "font-size": "25px"}, 
        "nav-link": {
            "font-size": "16px",
            "text-align": "left",
            "margin":"0px",
            "--hover-color": "#eee"
        },
        "nav-link-selected": {
            "background-color": "#0d6efd", # Cor primária do seu tema
            "font-weight": "bold",
            "color": "white"
        },
    }
)

if selected_main_tab == "Playbook":
    st.markdown('<p class="section-header">O Playbook de Produto</p>', unsafe_allow_html=True)
    playbooks_to_show = st.session_state.get('playbooks', {})
    
    if not playbooks_to_show:
        st.info("Nenhum playbook foi configurado ainda. Peça a um administrador para adicionar conteúdo.")
    else:
        playbook_titles = list(playbooks_to_show.keys())
        sub_tabs = st.tabs([f"**{title}**" for title in playbook_titles])
        
        for i, tab in enumerate(sub_tabs):
            with tab:
                playbook_title = playbook_titles[i]
                playbook_content = playbooks_to_show[playbook_title]
                st.markdown(playbook_content, unsafe_allow_html=True)

elif selected_main_tab == "Papéis":
    st.markdown('<p class="section-header">Papéis e Responsabilidades</p>', unsafe_allow_html=True)
    roles_from_admin = st.session_state.get('user_roles', [])
    if not roles_from_admin:
        st.warning("Nenhum papel cadastrado na área de Administração.", icon="👑")
    else:
        for role_data in roles_from_admin:
            with st.expander(f"**{role_data['name']}**", expanded=False):
                st.markdown(role_data.get('description', 'Nenhuma descrição.'), unsafe_allow_html=True)

elif selected_main_tab == "Competências":
    st.markdown('<p class="section-header">Framework de Competências</p>', unsafe_allow_html=True)
    framework = st.session_state.get('competency_framework', {})
    
    if not framework or (not framework.get('hard_skills') and not framework.get('soft_skills')):
        st.info("O Framework de Competências ainda não foi definido. Peça a um administrador para o configurar.")
    else:
        tab_hard, tab_soft = st.tabs(["**🛠️ Hard Skills**", "**🧠 Soft Skills**"])

        def display_skills(skills_list):
            if not skills_list:
                st.info("Nenhuma competência deste tipo foi definida.")
                return
            
            for skill in skills_list:
                with st.expander(f"**{skill.get('Competência', 'N/A')}**"):
                    st.caption(skill.get('Descrição', 'Nenhuma descrição fornecida.'))

        with tab_hard:
            display_skills(framework.get('hard_skills', []))

        with tab_soft:
            display_skills(framework.get('soft_skills', []))

elif selected_main_tab == "Gestão de Pessoas":
    st.markdown('<p class="section-header">Gestão de Pessoas (Chapter)</p>', unsafe_allow_html=True)
    
    # Nova estrutura de abas para melhor usabilidade
    selected_gestao_tab = option_menu(
        menu_title=None,
        options=["Time", "Avaliação", "Performance", "1-on-1s", "Enviar"],
        icons=['people', 'pencil-square', 'bar-chart-line', 'chat-dots', 'send'],
        default_index=0,
        orientation="horizontal",
        key='gestao_tab_selection'
    )
    
    # Aba 1: Gestão dos membros da equipe
    if selected_gestao_tab == "Time":
        role_names = [role['name'] for role in st.session_state.get('user_roles', [])]

        with st.expander("➕ Adicionar Novo Membro"):
            with st.form("novo_membro_form", clear_on_submit=True):
                nome = st.text_input("Nome do Membro*")
                papel = st.selectbox("Papel", role_names if role_names else ["Nenhum papel cadastrado"])
                email = st.text_input("Email do Membro*", placeholder="exemplo@dominio.com")

                if st.form_submit_button("Adicionar Membro", type="primary"):
                    nome_clean = nome.strip()
                    email_clean = email.strip()

                    if not nome_clean:
                        st.warning("O campo 'Nome do Membro' é obrigatório.")
                    elif not email_clean or '@' not in email_clean:
                        st.warning("Por favor, insira um 'Email do Membro' que seja válido.")
                    elif nome_clean in st.session_state.membros['Nome'].tolist():
                        st.warning(f"O membro '{nome_clean}' já existe na equipa.")
                    else:
                        novo_membro = pd.DataFrame([{"Nome": nome_clean, "Papel": papel, "Email": email_clean}])
                        st.session_state.membros = pd.concat([st.session_state.membros, novo_membro], ignore_index=True)
                        sync_evaluations_with_framework()
                        st.success(f"Membro '{nome_clean}' adicionado com sucesso!")
                        save_and_rerun()
        st.divider()
        st.subheader("Gerir Equipe")
        if not st.session_state.membros.empty:
            for index, row in st.session_state.membros.iterrows():
                with st.container(border=True):
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.markdown(f"**{row['Nome']}**")
                        st.caption(f"Papel: {row.get('Papel', 'N/A')} | Email: {row.get('Email', 'N/A')}")
                    with col2:
                        if st.button("Remover", key=f"delete_{index}", use_container_width=True, type="secondary"):
                            st.session_state.avaliacoes.pop(row['Nome'], None)
                            st.session_state.one_on_ones.pop(row['Nome'], None)
                            st.session_state.membros.drop(index, inplace=True)
                            save_and_rerun()
                    with st.expander("Editar detalhes"):
                        with st.form(key=f"edit_form_{index}"):
                            st.text_input("Nome", value=row['Nome'], disabled=True)
                            current_role_index = role_names.index(row['Papel']) if row['Papel'] in role_names else 0
                            novo_papel = st.selectbox("Novo Papel", options=role_names, index=current_role_index, key=f"role_{index}")
                            novo_email = st.text_input("Novo Email", value=row['Email'], key=f"email_{index}")
                            if st.form_submit_button("Salvar Alteração", type="primary"):
                                if '@' in novo_email:
                                    st.session_state.membros.loc[index, 'Papel'] = novo_papel
                                    st.session_state.membros.loc[index, 'Email'] = novo_email
                                    save_and_rerun()
                                else:
                                    st.error("O e-mail fornecido não é válido.")
        else:
            st.info("Nenhum membro na equipa para gerir.")

    # Aba 2: Focada apenas em preencher a avaliação
    elif selected_gestao_tab == "Avaliação":
        st.subheader("Preencher Avaliação e PDI")
        if st.session_state.membros.empty:
            st.warning("Adicione membros ao time na aba 'Time' para começar.")
        else:
            membro_selecionado_aval = st.selectbox(
                "Selecione um membro para avaliar:",
                st.session_state.membros['Nome'].tolist(),
                key="aval_member_select"
            )
            
            if membro_selecionado_aval:
                sync_evaluations_with_framework()
                
                full_evaluation_data = st.session_state.avaliacoes.get(membro_selecionado_aval, {})

                # Lógica para ler tanto rascunhos quanto avaliações submetidas via link
                dados_para_ui = full_evaluation_data.get('data', full_evaluation_data)

                # Exibe uma mensagem informativa se a avaliação já foi submetida
                if 'responder_name' in full_evaluation_data:
                    submission_date = pd.to_datetime(full_evaluation_data.get('submission_date')).strftime('%d/%m/%Y às %H:%M')
                    st.success(f"Avaliação submetida por **{full_evaluation_data.get('responder_name')}** em {submission_date}. As alterações aqui serão guardadas como um novo rascunho.")

                aval_lider, aval_membro = st.tabs(["Avaliação do Líder", "Autoavaliação"])
                framework = st.session_state.competency_framework
                hard_skills = framework.get('hard_skills', [])
                soft_skills = framework.get('soft_skills', [])

                # Função para renderizar a UI de avaliação
                def render_evaluation_ui_gestao(eval_type, skills_list, member_name):
                    if not skills_list:
                        st.info("Nenhuma competência deste tipo foi definida.")
                        return
                    
                    skill_icon = "🛠️" if eval_type == 'leader' else "🧠"

                    for skill in skills_list:
                        with st.container(border=True):
                            comp = skill['Competência']
                            comp_data = dados_para_ui.setdefault(comp, {"leader": {"level": 0, "pdi": ""}, "member": {"level": 0, "pdi": ""}})
                            eval_data = comp_data.get(eval_type, {"level": 0, "pdi": ""})
                            
                            st.markdown(f"<h5>{skill_icon} {comp}</h5>", unsafe_allow_html=True)
                            st.caption(skill.get('Descrição', ''))

                            comment_visibility_key = f"comment_visible_{eval_type}_{member_name}_{comp}"
                            
                            col1, col2 = st.columns([2, 0.4])

                            with col1:
                                pill_options = [SKILL_LEVELS[level]['name'] for level in SKILL_LEVELS]
                                current_level_index = eval_data.get('level', 0)
                                default_selection = pill_options[current_level_index]

                                selected_pill = st.pills(
                                    "Nível",
                                    options=pill_options,
                                    default=default_selection,
                                    key=f"pills_{eval_type}_{member_name}_{comp}",
                                    label_visibility="collapsed"
                                )
                                level = pill_options.index(selected_pill)

                            with col2:
                                is_comment_visible = st.session_state.get(comment_visibility_key, False)
                                has_existing_comment = bool(eval_data.get('pdi', ''))

                                if is_comment_visible:
                                    # Botão "Ocultar" como 'primary' (destacado, azul)
                                    if st.button("✖️ Ocultar", key=f"btn_hide_{eval_type}_{member_name}_{comp}", use_container_width=True, type="primary"):
                                        st.session_state[comment_visibility_key] = False
                                        st.rerun()
                                elif has_existing_comment:
                                    # Botão "Editar" como 'secondary' (subtil, cinzento)
                                    if st.button("📝 Editar", key=f"btn_edit_{eval_type}_{member_name}_{comp}", use_container_width=True, type="secondary"):
                                        st.session_state[comment_visibility_key] = True
                                        st.rerun()
                                else:
                                    # Botão "Adicionar" como 'secondary' (subtil, cinzento)
                                    if st.button("💬 Adicionar", key=f"btn_add_{eval_type}_{member_name}_{comp}", use_container_width=True, type="secondary"):
                                        st.session_state[comment_visibility_key] = True
                                        st.rerun()

                            if st.session_state.get(comment_visibility_key, False):
                                pdi = st.text_area(
                                    "Comentário", 
                                    value=eval_data.get('pdi', ''), 
                                    key=f"pdi_{eval_type}_{member_name}_{comp}", 
                                    height=120,
                                    label_visibility="collapsed"
                                )
                            else:
                                pdi = eval_data.get('pdi', '')

                            st.info(f"**{SKILL_LEVELS[level]['name']}:** {SKILL_LEVELS[level]['desc']}")
                                                        
                            dados_para_ui[comp][eval_type] = {'level': level, 'pdi': pdi}

            with aval_lider:
                lider_hard, lider_soft = st.tabs(["🛠️ Hard Skills", "🧠 Soft Skills"])
                with lider_hard: render_evaluation_ui_gestao('leader', hard_skills, membro_selecionado_aval)
                with lider_soft: render_evaluation_ui_gestao('leader', soft_skills, membro_selecionado_aval)

            with aval_membro:
                membro_hard, membro_soft = st.tabs(["🛠️ Hard Skills", "🧠 Soft Skills"])
                with membro_hard: render_evaluation_ui_gestao('member', hard_skills, membro_selecionado_aval)
                with membro_soft: render_evaluation_ui_gestao('member', soft_skills, membro_selecionado_aval)
            
            # Atualiza o dicionário principal com os dados corretos antes de salvar
            st.session_state.avaliacoes[membro_selecionado_aval] = dados_para_ui

            if st.button("Salvar Rascunho da Avaliação", key=f"save_draft_{membro_selecionado_aval}", use_container_width=True, type="primary"):
                save_and_rerun()

    # Aba 3: Focada apenas em analisar os dados
    if selected_gestao_tab == "Performance":
        st.subheader("Análise de Performance e Competências")
        if st.session_state.membros.empty:
            st.warning("Adicione membros e realize avaliações para visualizar os dados.")
        else:
            analise_ind, analise_time = st.tabs(["Análise Individual", "Visão Geral do Time"])

            with analise_ind:
                membro_selecionado_analise = st.selectbox(
                    "Selecione um membro para analisar:",
                    st.session_state.membros['Nome'].tolist(),
                    key="analise_member_select"
                )
                if membro_selecionado_analise:
                    full_evaluation_data = st.session_state.avaliacoes.get(membro_selecionado_analise, {})
                    competency_data = full_evaluation_data.get('data', full_evaluation_data)

                    if 'responder_name' in full_evaluation_data:
                        submission_date = pd.to_datetime(full_evaluation_data.get('submission_date')).strftime('%d/%m/%Y às %H:%M')
                        st.success(f"Avaliação preenchida por **{full_evaluation_data.get('responder_name')}** em {submission_date}.")

                    all_competencies = get_all_competencies_from_framework(st.session_state.competency_framework)
                    if not all_competencies:
                        st.info("Nenhuma competência para exibir.")
                    else:
                        st.markdown(f"#### Comparativo de Avaliações: {membro_selecionado_analise}")
                        competencies_list = [c['Competência'] for c in all_competencies]
                        levels_leader = [competency_data.get(comp, {}).get('leader', {}).get('level', 0) for comp in competencies_list]
                        levels_member = [competency_data.get(comp, {}).get('member', {}).get('level', 0) for comp in competencies_list]
                        fig = go.Figure()
                        fig.add_trace(go.Scatterpolar(r=levels_leader, theta=competencies_list, fill='toself', name='Avaliação do Líder'))
                        fig.add_trace(go.Scatterpolar(r=levels_member, theta=competencies_list, fill='toself', name='Autoavaliação'))
                        fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 5])), showlegend=True)
                        st.plotly_chart(fig, use_container_width=True)
                        st.divider()
                        st.markdown("#### Plano de Desenvolvimento Individual (PDI) e Comentários")
                        for comp_name in competencies_list:
                            comp_data = competency_data.get(comp_name)
                            if comp_data:
                                with st.expander(f"**{comp_name}**"):
                                    st.markdown("##### Comentários do Líder")
                                    pdi_leader = comp_data.get('leader', {}).get('pdi', '').strip()
                                    if pdi_leader: st.info(pdi_leader)
                                    else: st.caption("Nenhum comentário do líder.")
                                    st.markdown("##### Comentários do Membro (Autoavaliação)")
                                    pdi_member = comp_data.get('member', {}).get('pdi', '').strip()
                                    if pdi_member: st.warning(pdi_member)
                                    else: st.caption("Nenhum comentário do membro.")

            with analise_time:
                st.subheader("Dashboard de Competências do Time")
                
                dados_completos = []
                for membro, avaliacao_completa in st.session_state.avaliacoes.items():
                    avaliacoes = avaliacao_completa.get('data', avaliacao_completa)
                    for comp, data in avaliacoes.items():
                        if 'leader' in data:
                            # Usamos 'get' para segurança, caso o nível não exista
                            dados_completos.append({
                                "Membro": membro, 
                                "Competência": comp, 
                                "Nível (Líder)": data['leader'].get('level')
                            })
                
                if not dados_completos:
                    st.info("Nenhuma avaliação registada ainda para gerar uma análise.")
                else:
                    df_completo = pd.DataFrame(dados_completos)

                    st.divider()
                    st.markdown("#### 🔮 Análise com Inteligência Artificial")
                    if st.button("Analisar Performance do Time com IA", type="primary", use_container_width=True):
                        with st.spinner("A IA está a analisar os dados..."):
                            # Adicionamos aqui a extração completa de dados para a IA
                            df_ai_analysis = pd.DataFrame([
                                {
                                    "Membro": m, 
                                    "Competência": c, 
                                    "Nível (Líder)": av.get('data', av).get(c, {}).get('leader', {}).get('level'),
                                    "Comentário (Líder)": av.get('data', av).get(c, {}).get('leader', {}).get('pdi', ''),
                                    "Nível (Autoavaliação)": av.get('data', av).get(c, {}).get('member', {}).get('level'),
                                    "Comentário (Autoavaliação)": av.get('data', av).get(c, {}).get('member', {}).get('pdi', '')
                                }
                                for m, av in st.session_state.avaliacoes.items()
                                for c in av.get('data', av).keys()
                            ])
                            resposta_ai = get_ai_team_performance_analysis(df_ai_analysis)
                            st.markdown(resposta_ai)
                    st.divider()

                    st.markdown("#### Distribuição de Níveis por Competência")
                    competencias_list = df_completo['Competência'].unique().tolist()
                    comp_selecionada = st.selectbox("Selecione a Competência", competencias_list, key="dashboard_competency_select")
                    if comp_selecionada:
                        dados_filtrados = df_completo[df_completo['Competência'] == comp_selecionada]
                        niveis_contagem = dados_filtrados['Nível (Líder)'].value_counts().sort_index()
                        niveis_contagem.index = niveis_contagem.index.map(lambda x: SKILL_LEVELS.get(int(x), {}).get('name', 'N/A'))
                        fig_bar = px.bar(niveis_contagem, x=niveis_contagem.index, y=niveis_contagem.values, labels={"x": "Nível", "y": "Nº de Pessoas"}, text_auto=True)
                        st.plotly_chart(fig_bar, use_container_width=True)
                    
                    st.markdown("#### Mapa de Calor de Competências")
                    if not df_completo.empty:
                        df_pivot = df_completo.pivot_table(index="Membro", columns="Competência", values="Nível (Líder)")
                        fig_heatmap = go.Figure(data=go.Heatmap(z=df_pivot.values, x=df_pivot.columns, y=df_pivot.index, colorscale='Viridis'))
                        st.plotly_chart(fig_heatmap, use_container_width=True)

    # Aba 4: Registro de 1-on-1s
    if selected_gestao_tab == "1-on-1s":
        st.subheader("Acompanhamento Individual")
        if not st.session_state.membros.empty:
            membro_1on1 = st.selectbox("Selecione o membro:", st.session_state.membros['Nome'], key="1on1_membro")
            with st.form("form_1on1", clear_on_submit=True):
                data_1on1 = st.date_input("Data da Conversa")
                anotacoes = st.text_area("Pontos discutidos, ações e próximos passos:", height=200)
                if st.form_submit_button("Salvar Registro", type="primary"):
                    if anotacoes and membro_1on1:
                        if membro_1on1 not in st.session_state.one_on_ones:
                            st.session_state.one_on_ones[membro_1on1] = []
                        registro = {"data": str(data_1on1), "anotacoes": anotacoes}
                        st.session_state.one_on_ones[membro_1on1].append(registro)
                        save_and_rerun()
            if membro_1on1:
                st.subheader(f"Histórico de {membro_1on1}")
                if membro_1on1 in st.session_state.one_on_ones and st.session_state.one_on_ones[membro_1on1]:
                    for registro in sorted(st.session_state.one_on_ones[membro_1on1], key=lambda x: x['data'], reverse=True):
                        with st.expander(f"**Data:** {registro['data']}"):
                            st.write(registro['anotacoes'])
                else:
                    st.info(f"Nenhum registro de 1-on-1 para {membro_1on1} ainda.")
        else:
            st.warning("Adicione membros ao time primeiro.")
            
    # Aba 5: Envio de links de avaliação
    if selected_gestao_tab == "Enviar":
        st.subheader("Gerar e Enviar Links para Autoavaliação")
        st.info("Selecione os membros da equipa para quem deseja gerar um link de avaliação. Pode gerar o link para copiar manualmente ou enviá-lo diretamente por e-mail.")

        if st.session_state.membros.empty:
            st.warning("Nenhum membro encontrado. Adicione membros na aba 'Time' primeiro.")
        else:
            df_membros = st.session_state.membros.copy()
            df_membros['Email'] = df_membros['Email'].astype(str)
            all_member_names = df_membros['Nome'].tolist()
            selected_members = st.multiselect("Selecione um ou mais membros:", options=all_member_names)
            st.divider()
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Apenas Gerar Links", use_container_width=True, disabled=not selected_members):
                    try: get_global_configs.clear()
                    except Exception: pass
                    global_configs = get_global_configs()
                    base_url = global_configs.get("app_base_url")
                    if not base_url:
                        st.error("A URL base da aplicação não está configurada. Por favor, vá a '👑 Administração' e configure-a.")
                    else:
                        with st.spinner("A gerar links..."):
                            hub_owner_email = st.session_state['email']
                            st.success("Links gerados com sucesso!")
                            for member_name in selected_members:
                                token = generate_assessment_token(hub_owner_email=hub_owner_email, evaluated_email=member_name)
                                assessment_url = f"{base_url.rstrip('/')}/Avaliacao?token={token}"
                                st.markdown(f"**Link para {member_name}:**")
                                st.code(assessment_url, language=None)
            with col2:
                if st.button("Gerar e Enviar por E-mail", type="primary", use_container_width=True, disabled=not selected_members):
                    try: get_global_configs.clear()
                    except Exception: pass
                    global_configs = get_global_configs()
                    base_url = global_configs.get("app_base_url")
                    smtp_config = global_configs.get("smtp_settings")
                    if not base_url or not smtp_config:
                        st.error("A URL base ou as configurações de SMTP não estão definidas. Verifique em '👑 Administração'.")
                    else:
                        hub_owner_email = st.session_state['email']
                        # Busca os dados do utilizador para obter o nome mais recente
                        user_data = find_user(hub_owner_email) 
                        # Usa o nome se existir, caso contrário, usa o e-mail
                        hub_owner_name = user_data.get('name', hub_owner_email) if user_data else hub_owner_email

                        with st.spinner("A gerar links e a enviar e-mails..."):
                            success_count = 0
                            for member_name in selected_members:
                                member_info = df_membros[df_membros['Nome'] == member_name]
                                if member_info.empty or '@' not in member_info['Email'].iloc[0]:
                                    st.warning(f"Não é possível enviar e-mail para '{member_name}' (e-mail inválido ou inexistente).")
                                    continue
                                member_email = member_info['Email'].iloc[0]
                                token = generate_assessment_token(hub_owner_email=hub_owner_email, evaluated_email=member_name)
                                assessment_url = f"{base_url.rstrip('/')}/Avaliacao?token={token}"
                                if send_assessment_email(recipient_email=member_email, recipient_name=member_name, sender_name=hub_owner_name, assessment_url=assessment_url, smtp_configs=smtp_config):
                                    st.success(f"✔️ E-mail de avaliação enviado para {member_name}!")
                                    success_count += 1
                                else:
                                    st.error(f"❌ Falha ao enviar e-mail para {member_name}.")
                            if success_count > 0:
                                st.balloons()
                            st.info(f"Processo concluído. {success_count} de {len(selected_members)} e-mails foram processados.")